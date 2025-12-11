# -*- coding: utf-8 -*-
"""
图片预览组件
用于显示选中漫画的图片预览
"""

from typing import List, Tuple, Union

import imagehash
from loguru import logger
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.utils.file_utils import natural_sort_key

from ..core.archive_reader import ArchiveReader
from ..core.config_manager import ConfigManager
from ..core.scanner import ComicInfo, DuplicateGroup


class ImageLoadThread(QThread):
    """图片加载线程"""

    image_loaded = pyqtSignal(
        int, str, QPixmap, str
    )  # index, image_hash, pixmap, filename
    load_error = pyqtSignal(int, str)  # index, error_message
    filename_error = pyqtSignal(str, str)  # filename, error_message

    def __init__(
        self,
        comic_path: str,
        comic_hashes: List[Tuple[str, str]],
        image_indices_or_names: Union[List[int], List[str]],
        max_size: tuple,
        load_by_name: bool = False,
    ):
        super().__init__()
        self.comic_path = comic_path
        self.comic_hashes = comic_hashes
        self.image_indices_or_names = image_indices_or_names
        self.max_size = max_size
        self.load_by_name = load_by_name
        self._stop_requested = False

    def run(self):
        """运行图片加载"""
        try:
            archive_reader = ArchiveReader()

            # 获取压缩包中的所有图片文件
            image_files = archive_reader.get_image_files(self.comic_path)
            if not image_files:
                logger.error(f"压缩包中没有图片文件: {self.comic_path}")
                return

            if self.load_by_name:
                self._load_by_filename(archive_reader, image_files)
            else:
                self._load_by_index(archive_reader, image_files)

        except Exception as e:
            logger.error(f"加载漫画图片失败: {e}")

    def _load_by_index(self, archive_reader, image_files):
        """按索引加载图片"""
        for index in self.image_indices_or_names:
            if self._stop_requested:
                break

            try:
                # 确保索引在有效范围内
                if index < 0 or index >= len(image_files):
                    logger.warning(
                        f"图片索引超出范围: {index}, 总图片数: {len(image_files)}"
                    )
                    continue

                # 读取图片数据
                image_filename = image_files[index]
                image_data = archive_reader.read_image(self.comic_path, image_filename)
                if not image_data:
                    continue

                # 创建QPixmap
                pixmap = QPixmap()
                if pixmap.loadFromData(image_data):
                    # 缩放图片
                    if self.max_size:
                        pixmap = pixmap.scaled(
                            self.max_size[0],
                            self.max_size[1],
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )

                    # 获取图片哈希值
                    image_hash_hex = self.comic_hashes[index][1]
                    self.image_loaded.emit(
                        index, image_hash_hex, pixmap, image_filename
                    )

            except Exception as e:
                logger.error(f"加载图片 {index} 失败: {e}")
                self.load_error.emit(index, str(e))

    def _load_by_filename(self, archive_reader: ArchiveReader, image_files: List[str]):
        """按文件名加载图片"""
        # 创建文件名到哈希的映射
        filename_to_hash = {
            filename: hash_hex for filename, hash_hex in self.comic_hashes
        }

        for filename in self.image_indices_or_names:
            if self._stop_requested:
                break

            try:
                # 检查文件是否存在
                if filename not in image_files:
                    logger.warning(f"图片文件不存在: {filename}")
                    self.filename_error.emit(filename, f"文件不存在: {filename}")
                    continue

                # 读取图片数据
                image_data = archive_reader.read_image(self.comic_path, filename)
                if not image_data:
                    continue

                # 创建QPixmap
                pixmap = QPixmap()
                if pixmap.loadFromData(image_data):
                    # 缩放图片
                    if self.max_size:
                        pixmap = pixmap.scaled(
                            self.max_size[0],
                            self.max_size[1],
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )

                    # 查找索引
                    index = image_files.index(filename)

                    # 获取图片哈希值
                    image_hash_hex = filename_to_hash.get(filename, "")
                    self.image_loaded.emit(index, image_hash_hex, pixmap, filename)

            except Exception as e:
                logger.error(f"加载图片 {filename} 失败: {e}")
                self.filename_error.emit(filename, str(e))

    def stop(self):
        """停止加载"""
        self._stop_requested = True


class ImagePreviewWidget(QWidget):
    """图片预览组件"""

    refresh_needed = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.current_comic = None
        self.current_group = None
        self.compare_comics = []  # 要对比的漫画列表
        self.image_pixmaps = {}  # {index: QPixmap} or {hash: QPixmap}
        self.load_thread = None
        self.show_duplicates_only = True  # 新增：是否只显示重复图片
        self.load_finished = False  # 新增：是否加载完成

        # 分批加载相关属性
        self.batch_size = 6  # 每批加载的图片数量
        self.loaded_count = 0  # 已加载的图片数量
        self.total_items = []  # 所有要加载的图片索引或文件名
        self.is_loading = False  # 是否正在加载
        self.load_by_name = False  # 是否按文件名加载

        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("图片预览")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 漫画信息
        self.info_label = QLabel("请选择一个漫画文件")
        self.info_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.info_label)

        # 控制面板
        control_layout = QHBoxLayout()

        # 显示模式切换
        from PyQt5.QtWidgets import QCheckBox

        self.duplicates_only_checkbox = QCheckBox("仅显示重复图片")
        self.duplicates_only_checkbox.setChecked(self.show_duplicates_only)
        self.duplicates_only_checkbox.toggled.connect(self.on_display_mode_changed)
        control_layout.addWidget(self.duplicates_only_checkbox)

        control_layout.addStretch()

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_preview)
        control_layout.addWidget(self.refresh_btn)

        layout.addLayout(control_layout)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 添加滚动监听
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self.on_scroll_changed
        )

        # 图片容器
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setSpacing(10)

        self.scroll_area.setWidget(self.image_container)
        layout.addWidget(self.scroll_area)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

    def set_comic(self, comic: ComicInfo, group: DuplicateGroup):
        """设置要预览的漫画"""
        if self.current_comic == comic:
            return

        self.current_comic = comic
        self.current_group = group

        # 更新信息显示
        self.update_info_display()

        # 加载预览图片
        self.load_preview_images()

    def set_compare_comics(self, comics: List[ComicInfo]):
        """设置要对比的漫画列表"""
        self.compare_comics = comics
        # 如果当前有选中的漫画和组，重新加载图片
        if self.current_comic and self.current_group:
            self.load_preview_images()

    def update_info_display(self):
        """更新漫画信息显示"""
        if not self.current_comic:
            self.info_label.setText("请选择一个漫画文件")
            return

        comic = self.current_comic
        size_str = self._format_file_size(comic.size)

        info_text = f"大小: {size_str} | 总图片数: {len(comic.image_hashes)}"
        self.info_label.setText(info_text)

    def load_preview_images(self):
        """加载预览图片"""
        if not self.current_comic or not self.current_group:
            self.clear_images()
            return

        # 停止之前的加载线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_finished = False
            self.load_thread.stop()
            self.load_thread.wait()
            while not self.load_finished:
                QApplication.processEvents()

        # 清空现有图片
        self.clear_images()

        # 重置分批加载状态
        self.loaded_count = 0
        self.total_items = []
        self.is_loading = False

        # 准备要加载的图片索引或文件名
        if self.show_duplicates_only:
            self._prepare_duplicate_indices()
        else:
            self._prepare_all_indices()

        # 开始加载第一批图片
        self._load_next_batch()

    def _prepare_duplicate_indices(self):
        """准备重复图片的文件名"""
        if not self.current_group or not self.current_group.similar_hash_groups:
            self.status_label.setText("该重复组没有相似图片")
            return

        # 收集当前漫画相关的重复图片哈希
        current_comic_hashes = set(
            image_hash[1] for image_hash in self.current_comic.image_hashes
        )
        target_hashes = []

        # 确定要对比的漫画
        other_comics = []
        if self.compare_comics:
            other_comics = [
                c
                for c in self.compare_comics
                if c != self.current_comic and c in self.current_group.comics
            ]

        if other_comics:
            # 使用imagehash和配置进行对比
            algo = self.config.get_hash_algorithm()
            threshold = self.config.get_similarity_threshold(algo)

            other_hashes = set()
            for c in other_comics:
                for _, h in c.image_hashes:
                    other_hashes.add(h)

            other_hash_objs = [imagehash.hex_to_hash(h) for h in other_hashes]

            for filename, hash_hex in self.current_comic.image_hashes:
                current_hash_obj = imagehash.hex_to_hash(hash_hex)
                is_similar = False
                for other_hash_obj in other_hash_objs:
                    if current_hash_obj - other_hash_obj <= threshold:
                        is_similar = True
                        break
                if is_similar:
                    target_hashes.append(hash_hex)
        else:
            for hash1, hash2, _similarity in self.current_group.similar_hash_groups:
                if hash1 in current_comic_hashes:
                    target_hashes.append(hash1)
                if hash2 in current_comic_hashes:
                    target_hashes.append(hash2)

        # 去重
        target_hashes = set(target_hashes)

        if not target_hashes:
            self.status_label.setText("当前漫画没有重复图片")
            return

        # 按漫画原顺序排序，收集文件名
        sorted_image_hashes = sorted(
            self.current_comic.image_hashes,
            key=lambda x: natural_sort_key(x[0]),
        )
        self.total_items = []
        for filename, hash_hex in sorted_image_hashes:
            if hash_hex in target_hashes:
                self.total_items.append(filename)

        # 设置按文件名加载
        self.load_by_name = True
        self.status_label.setText(f"找到 {len(self.total_items)} 张重复图片")

    def _prepare_all_indices(self):
        """准备全部图片的索引"""
        total_images = len(self.current_comic.image_hashes)

        if total_images == 0:
            self.status_label.setText("该漫画没有图片")
            return

        # 按顺序加载所有图片（使用索引）
        self.total_items = list(range(total_images))
        self.load_by_name = False
        self.status_label.setText(f"共 {len(self.total_items)} 张图片")

    def _load_next_batch(self):
        """加载下一批图片"""
        if self.is_loading or self.loaded_count >= len(self.total_items):
            return

        self.is_loading = True

        # 计算本批次要加载的图片索引或文件名
        start_index = self.loaded_count
        end_index = min(start_index + self.batch_size, len(self.total_items))
        batch_items = self.total_items[start_index:end_index]

        if not batch_items:
            self.is_loading = False
            return

        # 获取预览图片尺寸
        preview_size = self.config.get_preview_size()

        # 创建加载线程
        self.load_thread = ImageLoadThread(
            self.current_comic.path,
            self.current_comic.image_hashes,
            batch_items,
            preview_size,
            self.load_by_name,
        )

        # 连接信号
        self.load_thread.image_loaded.connect(self.on_image_loaded)
        if self.load_by_name:
            self.load_thread.filename_error.connect(self.on_filename_load_error)
        else:
            self.load_thread.load_error.connect(self.on_image_load_error)

        self.load_thread.finished.connect(self.on_batch_load_finished)

        # 显示加载状态
        self.status_label.setText(f"正在加载第 {start_index + 1}-{end_index} 张图片...")

        # 开始加载
        self.load_thread.start()

    def on_batch_load_finished(self):
        """处理批次加载完成"""
        self.loaded_count = len(self.image_pixmaps)
        total_count = len(self.total_items)

        if self.loaded_count >= total_count:
            self.status_label.setText(f"已加载全部 {self.loaded_count} 张图片")
        else:
            self.status_label.setText(
                f"已加载 {self.loaded_count}/{total_count} 张图片"
            )

        self.is_loading = False
        self.load_finished = True

    def on_scroll_changed(self, value):
        """滚动条变化时的处理"""
        if not self.total_items or self.is_loading:
            return

        # 检查是否滚动到底部附近（距离底部小于100像素时开始加载）
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() - value < 100 and self.loaded_count < len(
            self.total_items
        ):
            self._load_next_batch()

    def on_image_loaded(
        self, index: int, image_hash: str, pixmap: QPixmap, filename: str
    ):
        """处理图片加载完成"""
        self.image_pixmaps[index] = pixmap
        self.add_image_to_display(index, image_hash, pixmap, filename)

    def on_filename_loaded(
        self,
        index: int,
        filename: str,
        image_hash: str,
        pixmap: QPixmap,
        display_filename: str,
    ):
        """处理按文件名加载的图片完成"""
        self.image_pixmaps[filename] = pixmap
        self.add_filename_image_to_display(
            index, filename, image_hash, pixmap, display_filename
        )

    def on_filename_load_error(self, filename: str, error_message: str):
        """处理按文件名加载的图片错误"""
        logger.warning(f"图片文件 {filename} 加载失败: {error_message}")
        self.add_error_placeholder_for_filename(filename, error_message)

    def on_duplicate_image_load_error(self, image_hash: str, error_message: str):
        """处理重复图片加载错误"""
        logger.warning(f"重复图片 {image_hash} 加载失败: {error_message}")
        self.add_error_placeholder_for_hash(image_hash, error_message)

    def on_image_load_error(self, index: int, error_message: str):
        """处理图片加载错误"""
        logger.warning(f"图片 {index} 加载失败: {error_message}")
        self.add_error_placeholder(index, error_message)

    def add_image_to_display(
        self, index: int, image_hash: str, pixmap: QPixmap, filename: str
    ):
        """添加图片到显示区域"""
        # 创建图片框架
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(1)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)

        # 图片标签
        image_label = QLabel()
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setScaledContents(False)

        # 图片信息 （可选择复制）
        info_text = f"图片[{index + 1}]: {filename}\n哈希值: {image_hash}\n({pixmap.width()}x{pixmap.height()})"
        info_label = QLabel(info_text)
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 10px; color: gray;")

        frame_layout.addWidget(image_label)
        frame_layout.addWidget(info_label)

        # 按索引顺序插入
        inserted = False
        for i in range(self.image_layout.count()):
            widget = self.image_layout.itemAt(i).widget()
            if widget and hasattr(widget, "image_index"):
                if widget.image_index > index:
                    self.image_layout.insertWidget(i, frame)
                    inserted = True
                    break

        if not inserted:
            self.image_layout.addWidget(frame)

        # 存储索引信息
        frame.image_index = index

    def add_error_placeholder_for_filename(self, filename: str, error_message: str):
        """为按文件名加载添加错误占位符"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(1)
        frame.setStyleSheet("background-color: #ffebee;")

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)

        # 错误图标
        error_label = QLabel("❌")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("font-size: 24px;")

        # 错误信息
        info_text = f"图片: {filename}\n加载失败"
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 10px; color: red;")
        info_label.setToolTip(error_message)

        frame_layout.addWidget(error_label)
        frame_layout.addWidget(info_label)

        # 直接添加到末尾
        self.image_layout.addWidget(frame)

        # 存储文件名信息
        frame.image_filename = filename

    def add_error_placeholder(self, index: int, error_message: str):
        """添加错误占位符"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(1)
        frame.setStyleSheet("background-color: #ffebee;")

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)

        # 错误图标
        error_label = QLabel("❌")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("font-size: 24px;")

        # 错误信息
        info_text = f"图片 {index + 1}\n加载失败"
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 10px; color: red;")
        info_label.setToolTip(error_message)

        frame_layout.addWidget(error_label)
        frame_layout.addWidget(info_label)

        # 按索引顺序插入
        inserted = False
        for i in range(self.image_layout.count()):
            widget = self.image_layout.itemAt(i).widget()
            if widget and hasattr(widget, "image_index"):
                if widget.image_index > index:
                    self.image_layout.insertWidget(i, frame)
                    inserted = True
                    break

        if not inserted:
            self.image_layout.addWidget(frame)

        # 存储索引信息
        frame.image_index = index

    def add_error_placeholder_for_hash(self, image_hash: str, error_message: str):
        """为重复图片添加错误占位符"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(1)
        frame.setStyleSheet("background-color: #ffebee;")

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)

        # 错误图标
        error_label = QLabel("❌")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("font-size: 24px;")

        # 错误信息
        info_text = f"重复图片\n加载失败\n哈希: {image_hash[:8]}..."
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 10px; color: red;")
        info_label.setToolTip(error_message)

        frame_layout.addWidget(error_label)
        frame_layout.addWidget(info_label)

        # 直接添加到末尾
        self.image_layout.addWidget(frame)

        # 存储哈希信息
        frame.image_hash = image_hash

    def on_display_mode_changed(self, checked: bool):
        """显示模式改变时的处理"""
        self.show_duplicates_only = checked

        # 重新加载图片
        if self.current_comic and self.current_group:
            self.load_preview_images()

    def clear_images(self):
        """清空图片显示"""
        # 清空布局
        while self.image_layout.count():
            child = self.image_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 清空缓存
        self.image_pixmaps.clear()

        # 重置分批加载状态
        self.loaded_count = 0
        self.total_items = []
        self.is_loading = False

    def clear(self):
        """清空预览"""
        # 停止加载线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.stop()
            self.load_thread.wait()

        self.current_comic = None
        self.current_group = None
        self.clear_images()

        self.info_label.setText("请选择一个漫画文件")
        self.status_label.setText("")

    def refresh_preview(self):
        """刷新预览"""
        if self.current_comic:
            self.load_preview_images()

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
