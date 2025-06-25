# -*- coding: utf-8 -*-
"""
图片预览组件
用于显示选中漫画的图片预览
"""

from typing import List, Tuple
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QSpinBox,
    QFrame,
    QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QFont
from loguru import logger

from src.utils.file_utils import natural_sort_key

from ..core.config_manager import ConfigManager
from ..core.scanner import ComicInfo, DuplicateGroup
from ..core.archive_reader import ArchiveReader


class ImageLoadThread(QThread):
    """图片加载线程"""

    image_loaded = pyqtSignal(
        int, str, QPixmap, str
    )  # index, image_hash, pixmap, filename
    load_error = pyqtSignal(int, str)  # index, error_message

    def __init__(
        self,
        comic_path: str,
        comic_hashes: List[Tuple[str, str]],
        image_indices: List[int],
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
        try:
            archive_reader = ArchiveReader()

            # 获取压缩包中的所有图片文件
            image_files = archive_reader.get_image_files(self.comic_path)
            if not image_files:
                logger.error(f"压缩包中没有图片文件: {self.comic_path}")
                return

            for index in self.image_indices:
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
                    image_data = archive_reader.read_image(
                        self.comic_path, image_filename
                    )
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

        except Exception as e:
            logger.error(f"加载漫画图片失败: {e}")

    def stop(self):
        """停止加载"""
        self._stop_requested = True


class ImagePreviewWidget(QWidget):
    """图片预览组件"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.current_comic = None
        self.current_group = None
        self.image_pixmaps = {}  # {index: QPixmap} or {hash: QPixmap}
        self.load_thread = None
        self.show_duplicates_only = True  # 新增：是否只显示重复图片
        self.load_finished = False  # 新增：是否加载完成

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

        # 图片数量控制（0表示无限制）
        control_layout.addWidget(QLabel("显示图片数 (0表示无限制):"))

        self.image_count_spinbox = QSpinBox()
        self.image_count_spinbox.setRange(0, 2147483647)
        self.image_count_spinbox.setValue(6)
        self.image_count_spinbox.valueChanged.connect(self.on_image_count_changed)
        control_layout.addWidget(self.image_count_spinbox)

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

        # 获取预览图片尺寸
        preview_size = self.config.get_preview_size()

        if self.show_duplicates_only:
            # 仅显示重复图片模式
            self._load_duplicate_images(preview_size)
        else:
            # 显示全部图片模式
            self._load_all_images(preview_size)

    def _load_duplicate_images(self, preview_size):
        """加载重复图片"""
        if not self.current_group or not self.current_group.similar_hash_groups:
            self.status_label.setText("该重复组没有相似图片")
            return

        # 收集当前漫画相关的重复图片哈希
        current_comic_hashes = set(
            image_hash[1] for image_hash in self.current_comic.image_hashes
        )
        target_hashes = []

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

        # 按漫画原顺序排序
        sorted_image_hashes = sorted(
            self.current_comic.image_hashes,
            key=lambda x: natural_sort_key(x[0]),
        )
        indices = []
        for index, sorted_image_hash in enumerate(sorted_image_hashes):
            hash_hex = sorted_image_hash[1]
            if hash_hex in target_hashes:
                indices.append(index)

        # 取前N张图片索引
        image_count = self.image_count_spinbox.value()
        if image_count > 0:
            indices = indices[:image_count]

        # 创建重复图片加载线程
        self.load_thread = ImageLoadThread(
            self.current_comic.path,
            self.current_comic.image_hashes,
            indices,
            preview_size,
        )
        self.load_thread.image_loaded.connect(self.on_image_loaded)
        self.load_thread.load_error.connect(self.on_image_load_error)
        self.load_thread.finished.connect(self.on_load_finished)

        # 显示加载状态
        self.status_label.setText(f"正在加载 {len(indices)} 张重复图片...")

        # 开始加载
        self.load_thread.start()

    def _load_all_images(self, preview_size):
        """加载全部图片"""
        # 计算要加载的图片索引
        image_count = self.image_count_spinbox.value()
        total_images = len(self.current_comic.image_hashes)

        if total_images == 0:
            self.status_label.setText("该漫画没有图片")
            return

        # 均匀分布选择图片索引
        if image_count == 0 or image_count >= total_images:
            indices = list(range(total_images))
        else:
            step = total_images / image_count
            indices = [int(i * step) for i in range(image_count)]

        # 创建加载线程
        self.load_thread = ImageLoadThread(
            self.current_comic.path,
            self.current_comic.image_hashes,
            indices,
            preview_size,
        )
        self.load_thread.image_loaded.connect(self.on_image_loaded)
        self.load_thread.load_error.connect(self.on_image_load_error)
        self.load_thread.finished.connect(self.on_load_finished)

        # 显示加载状态
        self.status_label.setText(f"正在加载 {len(indices)} 张图片...")

        # 开始加载
        self.load_thread.start()

    def on_image_loaded(
        self, index: int, image_hash: str, pixmap: QPixmap, filename: str
    ):
        """处理图片加载完成"""
        self.image_pixmaps[index] = pixmap
        self.add_image_to_display(index, image_hash, pixmap, filename)

    def on_duplicate_image_load_error(self, image_hash: str, error_message: str):
        """处理重复图片加载错误"""
        logger.warning(f"重复图片 {image_hash} 加载失败: {error_message}")
        self.add_error_placeholder_for_hash(image_hash, error_message)

    def on_image_load_error(self, index: int, error_message: str):
        """处理图片加载错误"""
        logger.warning(f"图片 {index} 加载失败: {error_message}")
        self.add_error_placeholder(index, error_message)

    def on_load_finished(self):
        """处理加载完成"""
        loaded_count = len(self.image_pixmaps)
        self.status_label.setText(f"已加载 {loaded_count} 张图片")
        self.load_finished = True

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

    def on_image_count_changed(self, value: int):
        """图片数量改变时的处理"""
        if self.current_comic:
            # 延迟刷新，避免频繁操作
            if hasattr(self, "_refresh_timer"):
                self._refresh_timer.stop()

            self._refresh_timer = QTimer()
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(self.refresh_preview)
            self._refresh_timer.start(500)  # 500ms延迟

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
