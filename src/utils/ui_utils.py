# -*- coding: utf-8 -*-
"""
UI工具模块
提供用户界面相关的实用函数
"""

import os
from typing import Optional, Tuple, List
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMessageBox,
    QFileDialog,
    QProgressDialog,
    QDesktopWidget,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QColor, QBrush, QFont
from loguru import logger


def center_window(window: QWidget, parent: Optional[QWidget] = None):
    """将窗口居中显示"""
    try:
        if parent:
            # 相对于父窗口居中
            parent_geometry = parent.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - window.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - window.height()) // 2
        else:
            # 相对于屏幕居中
            desktop = QDesktopWidget()
            screen_geometry = desktop.screenGeometry()
            x = (screen_geometry.width() - window.width()) // 2
            y = (screen_geometry.height() - window.height()) // 2

        window.move(max(0, x), max(0, y))

    except Exception as e:
        logger.error(f"窗口居中失败: {e}")


def show_error_message(
    parent: Optional[QWidget],
    title: str,
    message: str,
    detailed_text: Optional[str] = None,
):
    """显示错误消息对话框"""
    try:
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)

        if detailed_text:
            msg_box.setDetailedText(detailed_text)

        msg_box.exec_()

    except Exception as e:
        logger.error(f"显示错误消息失败: {e}")


def show_warning_message(parent: Optional[QWidget], title: str, message: str) -> bool:
    """显示警告消息对话框，返回用户是否确认"""
    try:
        reply = QMessageBox.warning(
            parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return reply == QMessageBox.Yes

    except Exception as e:
        logger.error(f"显示警告消息失败: {e}")
        return False


def show_info_message(parent: Optional[QWidget], title: str, message: str):
    """显示信息消息对话框"""
    try:
        QMessageBox.information(parent, title, message)

    except Exception as e:
        logger.error(f"显示信息消息失败: {e}")


def show_question_dialog(parent: Optional[QWidget], title: str, message: str) -> bool:
    """显示问题对话框，返回用户是否确认"""
    try:
        reply = QMessageBox.question(
            parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return reply == QMessageBox.Yes

    except Exception as e:
        logger.error(f"显示问题对话框失败: {e}")
        return False


def select_directory(
    parent: Optional[QWidget], title: str = "选择目录", start_dir: str = ""
) -> Optional[str]:
    """选择目录对话框"""
    try:
        directory = QFileDialog.getExistingDirectory(
            parent,
            title,
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        return directory.replace("/", "\\") if directory else None

    except Exception as e:
        logger.error(f"选择目录失败: {e}")
        return None


def select_file(
    parent: Optional[QWidget],
    title: str = "选择文件",
    start_dir: str = "",
    file_filter: str = "所有文件 (*)",
) -> Optional[str]:
    """选择文件对话框"""
    try:
        file_path, _ = QFileDialog.getOpenFileName(
            parent, title, start_dir, file_filter
        )
        return file_path.replace("/", "\\") if file_path else None

    except Exception as e:
        logger.error(f"选择文件失败: {e}")
        return None


def select_files(
    parent: Optional[QWidget],
    title: str = "选择文件",
    start_dir: str = "",
    file_filter: str = "所有文件 (*)",
) -> List[str]:
    """选择多个文件对话框"""
    try:
        file_paths, _ = QFileDialog.getOpenFileNames(
            parent, title, start_dir, file_filter
        )
        return [path.replace("/", "\\") for path in file_paths]

    except Exception as e:
        logger.error(f"选择文件失败: {e}")
        return []


def save_file(
    parent: Optional[QWidget],
    title: str = "保存文件",
    start_dir: str = "",
    file_filter: str = "所有文件 (*)",
) -> Optional[str]:
    """保存文件对话框"""
    try:
        file_path, _ = QFileDialog.getSaveFileName(
            parent, title, start_dir, file_filter
        )
        return file_path.replace("/", "\\") if file_path else None

    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        return None


def create_progress_dialog(
    parent: Optional[QWidget], title: str, label_text: str, maximum: int = 100
) -> QProgressDialog:
    """创建进度对话框"""
    try:
        progress = QProgressDialog(label_text, "取消", 0, maximum, parent)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        return progress

    except Exception as e:
        logger.error(f"创建进度对话框失败: {e}")
        return None


def set_window_icon(window: QWidget, icon_path: Optional[str] = None):
    """设置窗口图标"""
    try:
        if icon_path and os.path.exists(icon_path):
            window.setWindowIcon(QIcon(icon_path))
        else:
            # 创建默认图标
            pixmap = create_default_icon(32)
            window.setWindowIcon(QIcon(pixmap))

    except Exception as e:
        logger.error(f"设置窗口图标失败: {e}")


def create_default_icon(size: int = 32) -> QPixmap:
    """创建默认应用图标"""
    try:
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
        font = QFont("Arial", size // 3, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "漫")

        painter.end()

        return pixmap

    except Exception as e:
        logger.error(f"创建默认图标失败: {e}")
        return QPixmap()


def apply_dark_theme(app: QApplication):
    """应用暗色主题"""
    try:
        dark_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: "Segoe UI", Arial, sans-serif;
        }
        
        QMainWindow {
            background-color: #2b2b2b;
        }
        
        QMenuBar {
            background-color: #3c3c3c;
            border-bottom: 1px solid #555555;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #4a4a4a;
        }
        
        QMenu {
            background-color: #3c3c3c;
            border: 1px solid #555555;
        }
        
        QMenu::item:selected {
            background-color: #4a4a4a;
        }
        
        QToolBar {
            background-color: #3c3c3c;
            border: none;
            spacing: 2px;
        }
        
        QPushButton {
            background-color: #4a4a4a;
            border: 1px solid #666666;
            padding: 6px 12px;
            border-radius: 3px;
        }
        
        QPushButton:hover {
            background-color: #5a5a5a;
        }
        
        QPushButton:pressed {
            background-color: #3a3a3a;
        }
        
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #3c3c3c;
            border: 1px solid #666666;
            padding: 4px;
            border-radius: 3px;
        }
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border-color: #0078d4;
        }
        
        QTreeWidget, QListWidget {
            background-color: #3c3c3c;
            border: 1px solid #666666;
            alternate-background-color: #404040;
        }
        
        QTreeWidget::item:selected, QListWidget::item:selected {
            background-color: #0078d4;
        }
        
        QHeaderView::section {
            background-color: #4a4a4a;
            border: 1px solid #666666;
            padding: 4px;
        }
        
        QScrollBar:vertical {
            background-color: #3c3c3c;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #666666;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #777777;
        }
        
        QScrollBar:horizontal {
            background-color: #3c3c3c;
            height: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #666666;
            border-radius: 6px;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #777777;
        }
        
        QProgressBar {
            background-color: #3c3c3c;
            border: 1px solid #666666;
            border-radius: 3px;
            text-align: center;
        }
        
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 2px;
        }
        
        QStatusBar {
            background-color: #3c3c3c;
            border-top: 1px solid #555555;
        }
        
        QTabWidget::pane {
            border: 1px solid #666666;
            background-color: #3c3c3c;
        }
        
        QTabBar::tab {
            background-color: #4a4a4a;
            border: 1px solid #666666;
            padding: 6px 12px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #0078d4;
        }
        
        QGroupBox {
            border: 1px solid #666666;
            border-radius: 3px;
            margin-top: 10px;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        """

        app.setStyleSheet(dark_stylesheet)

    except Exception as e:
        logger.error(f"应用暗色主题失败: {e}")


def apply_light_theme(app: QApplication):
    """应用亮色主题"""
    try:
        # 恢复默认样式
        app.setStyleSheet("")

    except Exception as e:
        logger.error(f"应用亮色主题失败: {e}")


def get_screen_geometry() -> Tuple[int, int, int, int]:
    """获取屏幕几何信息 (x, y, width, height)"""
    try:
        desktop = QDesktopWidget()
        screen_geometry = desktop.screenGeometry()
        return (
            screen_geometry.x(),
            screen_geometry.y(),
            screen_geometry.width(),
            screen_geometry.height(),
        )

    except Exception as e:
        logger.error(f"获取屏幕几何信息失败: {e}")
        return (0, 0, 1920, 1080)  # 默认值


def is_dark_theme_preferred() -> bool:
    """检测系统是否偏好暗色主题"""
    try:
        # Windows 10/11 暗色主题检测
        if os.name == "nt":
            try:
                import winreg

                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(
                    registry,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return value == 0  # 0 表示暗色主题
            except (ImportError, OSError, FileNotFoundError):
                pass

        return False  # 默认返回亮色主题

    except Exception as e:
        logger.error(f"检测主题偏好失败: {e}")
        return False


def delayed_call(func, delay_ms: int = 100):
    """延迟调用函数"""
    try:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(func)
        timer.start(delay_ms)
        return timer

    except Exception as e:
        logger.error(f"延迟调用失败: {e}")
        return None


def format_time_duration(seconds: float) -> str:
    """格式化时间持续时间"""
    try:
        if seconds < 60:
            return f"{seconds:.1f} 秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes} 分 {remaining_seconds:.1f} 秒"
        else:
            hours = int(seconds // 3600)
            remaining_minutes = int((seconds % 3600) // 60)
            remaining_seconds = seconds % 60
            return f"{hours} 小时 {remaining_minutes} 分 {remaining_seconds:.1f} 秒"

    except Exception as e:
        logger.error(f"格式化时间失败: {e}")
        return "未知"


def format_number(number: int) -> str:
    """格式化数字显示（添加千位分隔符）"""
    try:
        return f"{number:,}"

    except Exception as e:
        logger.error(f"格式化数字失败: {e}")
        return str(number)
