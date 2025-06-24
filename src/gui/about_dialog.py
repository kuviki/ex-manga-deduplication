# -*- coding: utf-8 -*-
"""
关于对话框
显示应用程序信息
"""

import sys
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QTabWidget,
    QWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QBrush

from .. import __version__, __author__


class AboutDialog(QDialog):
    """关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 漫画去重工具")
        self.setModal(True)
        self.setFixedSize(500, 400)

        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 创建选项卡
        tab_widget = QTabWidget()

        # 关于选项卡
        about_tab = self.create_about_tab()
        tab_widget.addTab(about_tab, "关于")

        # 系统信息选项卡
        system_tab = self.create_system_tab()
        tab_widget.addTab(system_tab, "系统信息")

        # 许可证选项卡
        license_tab = self.create_license_tab()
        tab_widget.addTab(license_tab, "许可证")

        layout.addWidget(tab_widget)

        # 关闭按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_about_tab(self):
        """创建关于选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # 应用图标和标题
        header_layout = QHBoxLayout()

        # 创建应用图标
        icon_label = QLabel()
        icon_pixmap = self.create_app_icon(64)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)

        # 应用信息
        info_layout = QVBoxLayout()

        title_label = QLabel("漫画去重工具")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)

        version_label = QLabel(f"版本 {__version__}")
        version_label.setStyleSheet("color: gray;")

        author_label = QLabel(f"作者: {__author__}")
        author_label.setStyleSheet("color: gray;")

        info_layout.addWidget(title_label)
        info_layout.addWidget(version_label)
        info_layout.addWidget(author_label)
        info_layout.addStretch()

        header_layout.addWidget(icon_label)
        header_layout.addLayout(info_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 描述信息
        description = QLabel(
            "一个功能强大的漫画重复文件检测工具，支持多种压缩格式和图像哈希算法。\n\n"
            "主要功能：\n"
            "• 支持 ZIP/RAR/CBR/CBZ 格式的漫画文件\n"
            "• 多种图像哈希算法（感知哈希、差异哈希等）\n"
            "• 可配置的相似度阈值\n"
            "• 图片预览和详细信息显示\n"
            "• 黑名单管理功能\n"
            "• 扫描结果缓存\n"
            "• 支持暂停和恢复扫描\n"
            "• 模块化设计，易于扩展"
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignTop)

        layout.addWidget(description)
        layout.addStretch()

        return widget

    def create_system_tab(self):
        """创建系统信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 系统信息文本
        system_info = QTextEdit()
        system_info.setReadOnly(True)
        system_info.setFont(QFont("Consolas", 9))

        # 收集系统信息
        info_text = self.get_system_info()
        system_info.setPlainText(info_text)

        layout.addWidget(system_info)

        return widget

    def create_license_tab(self):
        """创建许可证选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 许可证文本
        license_text = QTextEdit()
        license_text.setReadOnly(True)

        license_content = """
GPL v3 License

Copyright (c) 2025 漫画去重工具

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

第三方库许可证：

本软件使用了以下第三方库：
• PyQt5 - GPL v3 License
• Pillow - HPND License
• imagehash - BSD 2-Clause License
• rarfile - ISC License
• loguru - MIT License

感谢这些优秀的开源项目！
"""

        license_text.setPlainText(license_content)

        layout.addWidget(license_text)

        return widget

    def create_app_icon(self, size: int) -> QPixmap:
        """创建应用图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景圆形
        painter.setBrush(QBrush(QColor("#4CAF50")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # 绘制文字
        painter.setPen(QColor("white"))
        font = QFont("Arial", size // 4, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "漫")

        painter.end()

        return pixmap

    def get_system_info(self) -> str:
        """获取系统信息"""
        try:
            import platform
            import psutil
            from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

            info_lines = [
                "=== 系统信息 ===",
                f"操作系统: {platform.system()} {platform.release()}",
                f"架构: {platform.machine()}",
                f"处理器: {platform.processor()}",
                "",
                "=== Python 信息 ===",
                f"Python 版本: {sys.version}",
                f"Python 路径: {sys.executable}",
                "",
                "=== Qt 信息 ===",
                f"Qt 版本: {QT_VERSION_STR}",
                f"PyQt5 版本: {PYQT_VERSION_STR}",
                "",
                "=== 硬件信息 ===",
                f"CPU 核心数: {psutil.cpu_count(logical=False)} 物理 / {psutil.cpu_count(logical=True)} 逻辑",
                f"内存: {psutil.virtual_memory().total / (1024**3):.1f} GB",
                "",
                "=== 应用信息 ===",
                f"应用版本: {__version__}",
                f"作者: {__author__}",
            ]

            # 添加已安装的包信息
            try:
                import pkg_resources

                info_lines.extend(["", "=== 主要依赖包 ==="])

                key_packages = [
                    "PyQt5",
                    "Pillow",
                    "imagehash",
                    "rarfile",
                    "loguru",
                    "psutil",
                    "diskcache",
                    "natsort",
                ]

                for package in key_packages:
                    try:
                        version = pkg_resources.get_distribution(package).version
                        info_lines.append(f"{package}: {version}")
                    except pkg_resources.DistributionNotFound:
                        info_lines.append(f"{package}: 未安装")

            except ImportError:
                pass

            return "\n".join(info_lines)

        except Exception as e:
            return f"获取系统信息时发生错误: {e}"
