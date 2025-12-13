# -*- coding: utf-8 -*-
"""
图片预览组件
用于显示选中漫画的图片预览
"""

import os
import shlex
import subprocess

import imagehash
from loguru import logger
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.archive_reader import ArchiveReader
from ..core.config_manager import ConfigManager
from ..core.scanner import ComicInfo, DuplicateGroup
from ..utils.file_utils import format_file_size


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
        comic_hashes: list[tuple[str, str]],
        image_indices: list[int],
        max_size: tuple,
    ):
        super().__init__()
        self.comic_path = comic_path
        self.comic_hashes = comic_hashes
        self.image_indices = image_indices
        self.max_size = max_size
        self._stop_requested = False

    def run(self):
        """运行图片加载"""
        # 检查是否有图片需要加载
        if not self.image_indices:
            return

        try:
            archive_reader = ArchiveReader()

            # 获取压缩包中的所有图片文件
            image_files = archive_reader.get_image_files(self.comic_path)
            if not image_files:
                logger.error(f"压缩包中没有图片文件: {self.comic_path}")
                return

            self._load_by_index(archive_reader, image_files, self.image_indices)

        except Exception as e:
            logger.error(f"加载漫画图片失败: {e}")

    def _load_by_index(
        self,
        archive_reader: ArchiveReader,
        image_files: list[str],
        image_indices: list[int],
    ):
        """按索引加载图片"""
        for index in image_indices:
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

    def stop(self):
        """停止加载"""
        self._stop_requested = True


class ImagePreviewWidget(QWidget):
    """图片预览组件"""

    refresh_needed = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.current_comic: ComicInfo | None = None
        self.current_group: DuplicateGroup | None = None
        self.compare_comics: list[ComicInfo] = []  # 要对比的漫画列表
        self.image_pixmaps = {}  # {index: QPixmap} or {hash: QPixmap}
        self.load_thread = None
        self.show_duplicates_only = True  # 是否只显示重复图片
        self.load_finished = False  # 是否加载完成

        # 分批加载相关属性
        self.batch_size = 6  # 每批加载的图片数量
        self.loaded_count = 0  # 已加载的图片数量
        self.total_items: list[int] = []  # 所有要加载的图片索引
        self.is_loading = False  # 是否正在加载

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

    def set_compare_comics(self, comics: list[ComicInfo]):
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
        size_str = format_file_size(comic.size)

        info_text = f"大小: {size_str} | 总图片数: {len(comic.all_image_names)} | 💡双击打开图片"
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
        if not self.current_comic or not self.current_group:
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
            # 检查是否有漫画不在当前重复组中
            compare_comics_not_in_group = [
                c for c in self.compare_comics if c not in self.current_group.comics
            ]
            if compare_comics_not_in_group:
                self.status_label.setText("当前漫画没有重复图片")
                return

            # 排除当前漫画
            other_comics = [c for c in self.compare_comics if c != self.current_comic]

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

        # 按漫画原顺序排序，收集文件索引
        self.total_items = []
        image_hashes_dict = dict(self.current_comic.image_hashes)
        for index, filename in enumerate(self.current_comic.all_image_names):
            if (
                filename in image_hashes_dict
                and image_hashes_dict[filename] in target_hashes
            ):
                self.total_items.append(index)

        # 按顺序加载重复图片
        self.status_label.setText(f"找到 {len(self.total_items)} 张重复图片")

    def _prepare_all_indices(self):
        """准备全部图片的索引"""
        if not self.current_comic:
            return

        total_images = len(self.current_comic.all_image_names)

        if total_images == 0:
            self.status_label.setText("该漫画没有图片")
            return

        # 按顺序加载所有图片
        self.total_items = list(range(total_images))
        self.status_label.setText(f"共 {len(self.total_items)} 张图片")

    def _load_next_batch(self):
        """加载下一批图片"""
        if (
            not self.current_comic
            or self.is_loading
            or self.loaded_count >= len(self.total_items)
        ):
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
        )

        # 连接信号
        self.load_thread.image_loaded.connect(self.on_image_loaded)
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
        if scrollbar is None:
            return
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

        # 启用鼠标跟踪并设置双击事件
        image_label.setMouseTracking(True)
        image_label.mouseDoubleClickEvent = (
            lambda event, idx=index, name=filename: self.on_image_double_click(
                event, idx, name
            )
        )

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
            if child:
                widget = child.widget()
                if widget:
                    widget.deleteLater()

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

    def on_image_double_click(self, _event, index: int, filename: str):
        """处理图片双击事件"""
        if not self.current_comic:
            return

        try:
            # 获取漫画查看器路径
            viewer_path = self.config.get_comic_viewer_path()

            if viewer_path:
                # 使用指定的漫画查看器打开
                self._open_with_viewer(viewer_path, index, filename)
            else:
                # 根据漫画存储类型决定打开方式
                if os.path.isdir(self.current_comic.path):
                    # 文件夹形式，直接打开图片文件
                    self._open_image_file(filename)
                else:
                    # 压缩包形式，打开压缩包文件
                    self._open_archive_file()

        except Exception as e:
            logger.exception("打开图片失败，详细错误信息: ")
            QMessageBox.critical(self, "错误", f"打开图片失败: {e}")

    def _open_with_viewer(self, viewer_path: str, image_index: int, filename: str):
        """使用指定的漫画查看器打开"""
        if not self.current_comic:
            return

        try:
            if os.path.isdir(self.current_comic.path):
                # 文件夹形式，打开具体的图片文件
                image_path = os.path.join(self.current_comic.path, filename)
                if os.path.exists(image_path):
                    subprocess.Popen([viewer_path, image_path])
                else:
                    QMessageBox.warning(self, "警告", f"图片文件不存在: {filename}")
            else:
                # 压缩包形式，打开压缩包文件
                # 获取漫画查看器参数
                viewer_args = self.config.get_comic_viewer_args()

                if viewer_args:
                    cmd = [viewer_path]
                    # 使用format方法替换占位符，正确处理包含空格的路径
                    viewer_args = viewer_args.format(
                        file=self.current_comic.path,
                        page=image_index + 1,
                        page_index=image_index,
                    )
                    # 使用shlex.split正确处理包含空格的参数
                    cmd.extend(shlex.split(viewer_args))
                    print(cmd)
                    subprocess.Popen(cmd)
                else:
                    subprocess.Popen([viewer_path, self.current_comic.path])
        except Exception as e:
            raise Exception(f"使用漫画查看器打开失败: {e}")

    def _open_image_file(self, filename: str):
        """打开文件夹中的图片文件"""
        if not self.current_comic:
            return

        try:
            image_path = os.path.join(self.current_comic.path, filename)
            if os.path.exists(image_path):
                os.startfile(image_path)  # Windows系统默认程序打开
            else:
                QMessageBox.warning(self, "警告", f"图片文件不存在: {filename}")
        except Exception as e:
            raise Exception(f"打开图片文件失败: {e}")

    def _open_archive_file(self):
        """打开压缩包文件"""
        if not self.current_comic:
            return

        try:
            if os.path.exists(self.current_comic.path):
                os.startfile(self.current_comic.path)  # Windows系统默认程序打开
            else:
                QMessageBox.warning(
                    self, "警告", f"漫画文件不存在: {self.current_comic.path}"
                )
        except Exception as e:
            raise Exception(f"打开压缩包失败: {e}")
