# -*- coding: utf-8 -*-
"""
图片预览组件
用于显示选中漫画的图片预览
"""

import os
from typing import Optional, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QSlider, QSpinBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QFont, QPainter, QPen
from loguru import logger

from ..core.config_manager import ConfigManager
from ..core.scanner import ComicInfo, DuplicateGroup
from ..core.archive_reader import ArchiveReader

class ImageLoadThread(QThread):
    """图片加载线程"""
    
    image_loaded = pyqtSignal(int, QPixmap)  # index, pixmap
    load_error = pyqtSignal(int, str)  # index, error_message
    
    def __init__(self, comic_path: str, image_indices: List[int], max_size: tuple):
        super().__init__()
        self.comic_path = comic_path
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
                        logger.warning(f"图片索引超出范围: {index}, 总图片数: {len(image_files)}")
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
                                self.max_size[0], self.max_size[1],
                                Qt.KeepAspectRatio, Qt.SmoothTransformation
                            )
                        
                        self.image_loaded.emit(index, pixmap)
                    
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
    
    # 信号定义
    image_blacklisted = pyqtSignal(str)  # 图片被加入黑名单信号
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.current_comic = None
        self.current_group = None
        self.image_pixmaps = {}  # {index: QPixmap}
        self.load_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        self.title_label = QLabel("图片预览")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.title_label)
        
        # 漫画信息
        self.info_label = QLabel("请选择一个漫画文件")
        self.info_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.info_label)
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        # 图片数量控制
        control_layout.addWidget(QLabel("显示图片数:"))
        
        self.image_count_spinbox = QSpinBox()
        self.image_count_spinbox.setMinimum(1)
        self.image_count_spinbox.setMaximum(20)
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
            self.title_label.setText("图片预览")
            return
        
        comic = self.current_comic
        filename = os.path.basename(comic.path)
        size_str = self._format_file_size(comic.size)
        
        info_text = f"文件: {filename}\n大小: {size_str} | 图片数: {comic.image_count}"
        self.info_label.setText(info_text)
        
        self.title_label.setText(f"图片预览 - {filename}")
    
    def load_preview_images(self):
        """加载预览图片"""
        if not self.current_comic:
            self.clear_images()
            return
        
        # 停止之前的加载线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.stop()
            self.load_thread.wait()
        
        # 清空现有图片
        self.clear_images()
        
        # 计算要加载的图片索引
        image_count = self.image_count_spinbox.value()
        total_images = self.current_comic.image_count
        
        if total_images == 0:
            self.status_label.setText("该漫画没有图片")
            return
        
        # 均匀分布选择图片索引
        if image_count >= total_images:
            indices = list(range(total_images))
        else:
            step = total_images / image_count
            indices = [int(i * step) for i in range(image_count)]
        
        # 获取预览图片尺寸
        preview_size = self.config.get_preview_size()
        
        # 创建加载线程
        self.load_thread = ImageLoadThread(
            self.current_comic.path, indices, preview_size
        )
        self.load_thread.image_loaded.connect(self.on_image_loaded)
        self.load_thread.load_error.connect(self.on_image_load_error)
        self.load_thread.finished.connect(self.on_load_finished)
        
        # 显示加载状态
        self.status_label.setText(f"正在加载 {len(indices)} 张图片...")
        
        # 开始加载
        self.load_thread.start()
    
    def on_image_loaded(self, index: int, pixmap: QPixmap):
        """处理图片加载完成"""
        self.image_pixmaps[index] = pixmap
        self.add_image_to_display(index, pixmap)
    
    def on_image_load_error(self, index: int, error_message: str):
        """处理图片加载错误"""
        logger.warning(f"图片 {index} 加载失败: {error_message}")
        self.add_error_placeholder(index, error_message)
    
    def on_load_finished(self):
        """处理加载完成"""
        loaded_count = len(self.image_pixmaps)
        self.status_label.setText(f"已加载 {loaded_count} 张图片")
    
    def add_image_to_display(self, index: int, pixmap: QPixmap):
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
        
        # 图片信息
        info_text = f"图片 {index + 1} ({pixmap.width()}x{pixmap.height()})"
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 10px; color: gray;")
        
        frame_layout.addWidget(image_label)
        frame_layout.addWidget(info_label)
        
        # 按索引顺序插入
        inserted = False
        for i in range(self.image_layout.count()):
            widget = self.image_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'image_index'):
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
            if widget and hasattr(widget, 'image_index'):
                if widget.image_index > index:
                    self.image_layout.insertWidget(i, frame)
                    inserted = True
                    break
        
        if not inserted:
            self.image_layout.addWidget(frame)
        
        # 存储索引信息
        frame.image_index = index
    
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
        self.title_label.setText("图片预览")
        self.status_label.setText("")
    
    def refresh_preview(self):
        """刷新预览"""
        if self.current_comic:
            self.load_preview_images()
    
    def on_image_count_changed(self, value: int):
        """图片数量改变时的处理"""
        if self.current_comic:
            # 延迟刷新，避免频繁操作
            if hasattr(self, '_refresh_timer'):
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