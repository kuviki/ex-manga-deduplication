# -*- coding: utf-8 -*-
"""
黑名单管理对话框
用于管理图片黑名单
"""

import os
from typing import List
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QFileDialog,
    QTextEdit,
    QSplitter,
    QGroupBox,
    QProgressBar,
    QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from loguru import logger

from ..core.config_manager import ConfigManager
from ..core.blacklist_manager import BlacklistManager
from ..core.image_hash import ImageHasher


class HashCalculationThread(QThread):
    """哈希计算线程"""

    progress_updated = pyqtSignal(int, int)  # current, total
    hash_calculated = pyqtSignal(str, str)  # file_path, hash_value
    finished_signal = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, image_files: List[str], hasher: ImageHasher):
        super().__init__()
        self.image_files = image_files
        self.hasher = hasher
        self._stop_requested = False

    def run(self):
        """运行哈希计算"""
        try:
            total = len(self.image_files)

            for i, file_path in enumerate(self.image_files):
                if self._stop_requested:
                    break

                try:
                    # 读取图片数据
                    with open(file_path, "rb") as f:
                        image_data = f.read()

                    # 计算哈希
                    hash_value = self.hasher.calculate_hash(image_data)
                    if hash_value:
                        self.hash_calculated.emit(file_path, hash_value)

                    self.progress_updated.emit(i + 1, total)

                except Exception as e:
                    logger.error(f"计算文件 {file_path} 哈希失败: {e}")

            self.finished_signal.emit()

        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        """停止计算"""
        self._stop_requested = True


class BlacklistDialog(QDialog):
    """黑名单管理对话框"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.blacklist_manager = BlacklistManager(config_manager)
        self.hasher = ImageHasher(config_manager)
        self.hash_thread = None

        self.setWindowTitle("黑名单管理")
        self.setModal(True)
        self.resize(800, 600)

        self.init_ui()
        self.load_blacklist()

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：黑名单列表
        left_widget = self.create_blacklist_panel()
        splitter.addWidget(left_widget)

        # 右侧：详细信息和操作
        right_widget = self.create_details_panel()
        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([400, 400])

        layout.addWidget(splitter)

        # 底部按钮
        button_layout = QHBoxLayout()

        self.import_btn = QPushButton("导入图片")
        self.import_btn.clicked.connect(self.import_images)

        self.export_btn = QPushButton("导出黑名单")
        self.export_btn.clicked.connect(self.export_blacklist)

        self.import_blacklist_btn = QPushButton("导入黑名单")
        self.import_blacklist_btn.clicked.connect(self.import_blacklist)

        self.clear_btn = QPushButton("清空黑名单")
        self.clear_btn.clicked.connect(self.clear_blacklist)
        self.clear_btn.setStyleSheet(
            "QPushButton { background-color: #ff6b6b; color: white; }"
        )

        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.import_blacklist_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def create_blacklist_panel(self):
        """创建黑名单面板"""
        group = QGroupBox("黑名单列表")
        layout = QVBoxLayout(group)

        # 统计信息
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.stats_label)

        # 黑名单列表
        self.blacklist_widget = QListWidget()
        self.blacklist_widget.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.blacklist_widget)

        # 列表操作按钮
        list_button_layout = QHBoxLayout()

        self.remove_btn = QPushButton("移除选中")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setEnabled(False)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_blacklist)

        list_button_layout.addWidget(self.remove_btn)
        list_button_layout.addStretch()
        list_button_layout.addWidget(self.refresh_btn)

        layout.addLayout(list_button_layout)

        return group

    def create_details_panel(self):
        """创建详细信息面板"""
        group = QGroupBox("详细信息")
        layout = QVBoxLayout(group)

        # 哈希值显示
        self.hash_label = QLabel("选择一个黑名单项查看详细信息")
        self.hash_label.setWordWrap(True)
        self.hash_label.setStyleSheet(
            "font-family: monospace; background-color: #f5f5f5; padding: 5px;"
        )
        layout.addWidget(self.hash_label)

        # 来源信息
        self.source_text = QTextEdit()
        self.source_text.setMaximumHeight(150)
        self.source_text.setReadOnly(True)
        layout.addWidget(QLabel("来源信息:"))
        layout.addWidget(self.source_text)

        # 添加说明
        info_label = QLabel(
            "说明:\n"
            "• 黑名单用于排除不需要检测的图片\n"
            "• 可以导入图片文件自动计算哈希值\n"
            "• 支持导入/导出黑名单文件\n"
            "• 黑名单在扫描时会自动应用"
        )
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        layout.addStretch()

        return group

    def load_blacklist(self):
        """加载黑名单"""
        try:
            # 清空列表
            self.blacklist_widget.clear()

            # 获取黑名单数据
            blacklist_data = self.blacklist_manager.get_blacklist_info()

            # 添加到列表
            for hash_value, info in blacklist_data.items():
                item = QListWidgetItem()

                # 显示文本
                display_text = f"{hash_value[:16]}..."
                if "source" in info:
                    display_text += f" ({info['source']})"

                item.setText(display_text)
                item.setData(Qt.UserRole, {"hash": hash_value, "info": info})

                self.blacklist_widget.addItem(item)

            # 更新统计信息
            count = len(blacklist_data)
            self.stats_label.setText(f"共 {count} 个黑名单项")

        except Exception as e:
            logger.error(f"加载黑名单失败: {e}")
            QMessageBox.critical(self, "错误", f"加载黑名单失败: {e}")

    def on_selection_changed(self):
        """处理选择变化"""
        current_item = self.blacklist_widget.currentItem()

        if current_item:
            data = current_item.data(Qt.UserRole)
            hash_value = data["hash"]
            info = data["info"]

            # 显示哈希值
            self.hash_label.setText(f"哈希值: {hash_value}")

            # 显示来源信息
            source_info = []
            if "source" in info:
                source_info.append(f"来源: {info['source']}")
            if "added_time" in info:
                source_info.append(f"添加时间: {info['added_time']}")
            if "file_path" in info:
                source_info.append(f"文件路径: {info['file_path']}")

            self.source_text.setText("\n".join(source_info))

            self.remove_btn.setEnabled(True)
        else:
            self.hash_label.setText("选择一个黑名单项查看详细信息")
            self.source_text.clear()
            self.remove_btn.setEnabled(False)

    def import_images(self):
        """导入图片文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.webp);;所有文件 (*)",
        )

        if not file_paths:
            return

        # 过滤有效的图片文件
        valid_files = []
        for file_path in file_paths:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                valid_files.append(file_path)

        if not valid_files:
            QMessageBox.warning(self, "警告", "没有找到有效的图片文件")
            return

        # 确认导入
        reply = QMessageBox.question(
            self,
            "确认导入",
            f"确定要导入 {len(valid_files)} 个图片文件到黑名单吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # 开始计算哈希
        self.start_hash_calculation(valid_files)

    def start_hash_calculation(self, image_files: List[str]):
        """开始哈希计算"""
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(image_files))
        self.progress_bar.setValue(0)

        # 禁用按钮
        self.import_btn.setEnabled(False)

        # 创建计算线程
        self.hash_thread = HashCalculationThread(image_files, self.hasher)
        self.hash_thread.progress_updated.connect(self.on_hash_progress)
        self.hash_thread.hash_calculated.connect(self.on_hash_calculated)
        self.hash_thread.finished_signal.connect(self.on_hash_finished)
        self.hash_thread.error_occurred.connect(self.on_hash_error)

        # 开始计算
        self.hash_thread.start()

    def on_hash_progress(self, current: int, total: int):
        """更新哈希计算进度"""
        self.progress_bar.setValue(current)
        QApplication.processEvents()

    def on_hash_calculated(self, file_path: str, hash_value: str):
        """处理哈希计算完成"""
        try:
            # 添加到黑名单
            self.blacklist_manager.add_to_blacklist(
                hash_value, source="手动导入", file_path=file_path
            )
        except Exception as e:
            logger.error(f"添加哈希到黑名单失败: {e}")

    def on_hash_finished(self):
        """哈希计算完成"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 启用按钮
        self.import_btn.setEnabled(True)

        # 刷新列表
        self.load_blacklist()

        QMessageBox.information(self, "完成", "图片导入完成")

    def on_hash_error(self, error_message: str):
        """哈希计算错误"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 启用按钮
        self.import_btn.setEnabled(True)

        QMessageBox.critical(self, "错误", f"计算哈希时发生错误: {error_message}")

    def remove_selected(self):
        """移除选中的黑名单项"""
        current_item = self.blacklist_widget.currentItem()
        if not current_item:
            return

        data = current_item.data(Qt.UserRole)
        hash_value = data["hash"]

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要从黑名单中移除这个项目吗？\n\n哈希值: {hash_value}",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                self.blacklist_manager.remove_from_blacklist(hash_value)
                self.load_blacklist()
                QMessageBox.information(self, "完成", "已从黑名单中移除")
            except Exception as e:
                logger.error(f"移除黑名单项失败: {e}")
                QMessageBox.critical(self, "错误", f"移除失败: {e}")

    def export_blacklist(self):
        """导出黑名单"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出黑名单", "blacklist.json", "JSON文件 (*.json);;所有文件 (*)"
        )

        if file_path:
            try:
                self.blacklist_manager.export_blacklist(file_path)
                QMessageBox.information(self, "完成", f"黑名单已导出到: {file_path}")
            except Exception as e:
                logger.error(f"导出黑名单失败: {e}")
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def import_blacklist(self):
        """导入黑名单"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入黑名单", "", "JSON文件 (*.json);;所有文件 (*)"
        )

        if file_path:
            try:
                imported_count = self.blacklist_manager.import_blacklist(file_path)
                self.load_blacklist()
                QMessageBox.information(
                    self, "完成", f"成功导入 {imported_count} 个黑名单项"
                )
            except Exception as e:
                logger.error(f"导入黑名单失败: {e}")
                QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def clear_blacklist(self):
        """清空黑名单"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空整个黑名单吗？\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                self.blacklist_manager.clear_blacklist()
                self.load_blacklist()
                QMessageBox.information(self, "完成", "黑名单已清空")
            except Exception as e:
                logger.error(f"清空黑名单失败: {e}")
                QMessageBox.critical(self, "错误", f"清空失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        # 停止哈希计算线程
        if self.hash_thread and self.hash_thread.isRunning():
            self.hash_thread.stop()
            self.hash_thread.wait()

        event.accept()
