# -*- coding: utf-8 -*-
"""
主窗口界面
应用程序的主要用户界面
"""

import os
import time
from typing import List
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QGroupBox,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QAction,
    QStatusBar,
)
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QFont
from loguru import logger
from send2trash import send2trash

from ..core.config_manager import ConfigManager
from ..core.scanner import Scanner, ScanProgress, DuplicateGroup, ComicInfo
from .settings_dialog import SettingsDialog
from .image_preview_widget import ImagePreviewWidget
from .duplicate_list_widget import DuplicateListWidget


class ScanThread(QThread):
    """扫描线程"""

    def __init__(self, scanner: Scanner, directory: str):
        super().__init__()
        self.scanner = scanner
        self.directory = directory

    def run(self):
        """运行扫描"""
        self.scanner.scan_directory(self.directory)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config = config_manager
        self.scanner = Scanner(self.config)
        self.scan_thread = None
        self.current_duplicates = []

        self.init_ui()
        self.connect_signals()
        self.load_settings()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Ex-漫画去重工具 v1.0.0")

        # 设置窗口大小
        width, height = self.config.get_window_geometry()
        self.resize(width, height)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建工具栏
        self.create_toolbar()

        # 创建主要内容区域
        self.create_main_content(main_layout)

        # 创建状态栏
        self.create_status_bar()

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 选择目录
        select_dir_action = QAction("选择扫描目录(&O)", self)
        select_dir_action.setShortcut("Ctrl+O")
        select_dir_action.triggered.connect(self.select_directory)
        file_menu.addAction(select_dir_action)

        file_menu.addSeparator()

        # 导出结果
        export_action = QAction("导出结果(&E)", self)
        export_action.triggered.connect(self.export_results)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        # 退出
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")

        # 设置
        settings_action = QAction("设置(&S)", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)

        tools_menu.addSeparator()

        # 清理缓存
        clear_cache_action = QAction("清理缓存(&C)", self)
        clear_cache_action.triggered.connect(self.clear_cache)
        tools_menu.addAction(clear_cache_action)

        # 黑名单管理
        blacklist_action = QAction("黑名单管理(&B)", self)
        blacklist_action.triggered.connect(self.manage_blacklist)
        tools_menu.addAction(blacklist_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """创建工具栏"""
        # 目录选择区域
        dir_group = QGroupBox("扫描目录")
        dir_layout = QHBoxLayout(dir_group)

        self.dir_label = QLabel("请选择要扫描的目录...")
        self.dir_label.setStyleSheet("color: gray; font-style: italic;")

        self.select_dir_btn = QPushButton("选择目录")
        self.select_dir_btn.clicked.connect(self.select_directory)

        dir_layout.addWidget(self.dir_label, 1)
        dir_layout.addWidget(self.select_dir_btn)

        # 控制按钮区域
        control_group = QGroupBox("扫描控制")
        control_layout = QHBoxLayout(control_group)

        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.clicked.connect(self.start_scan)
        self.scan_btn.setEnabled(False)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.pause_scan)
        self.pause_btn.setEnabled(False)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_scan)
        self.stop_btn.setEnabled(False)

        control_layout.addWidget(self.scan_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()

        # 进度显示区域
        progress_group = QGroupBox("扫描进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        # 工具栏布局
        toolbar_layout = QVBoxLayout()

        # 创建水平布局容器，放置扫描目录和扫描控制
        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(dir_group, 3)  # 扫描目录占更多空间
        top_row_layout.addWidget(control_group, 1)  # 扫描控制占较少空间

        # 将水平布局和进度组添加到主布局
        top_row_container = QWidget()
        top_row_container.setLayout(top_row_layout)
        toolbar_layout.addWidget(top_row_container)
        toolbar_layout.addWidget(progress_group)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)

        return toolbar_widget

    def create_main_content(self, main_layout):
        """创建主要内容区域"""
        # 添加工具栏
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：重复漫画列表和详情
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 重复漫画列表
        self.duplicate_list = DuplicateListWidget(self.config)
        self.duplicate_list.comic_selected.connect(self.on_comic_selected)
        self.duplicate_list.comics_to_delete.connect(self.delete_comics)

        # 详情信息
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(150)
        self.info_text.setReadOnly(True)

        left_layout.addWidget(self.duplicate_list, 3)
        title_label = QLabel("详情信息")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(title_label)
        left_layout.addWidget(self.info_text, 1)

        # 右侧：图片预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 图片预览
        self.image_preview = ImagePreviewWidget(self.config)
        self.image_preview.image_blacklisted.connect(self.on_image_blacklisted)

        right_layout.addWidget(self.image_preview)

        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 400])  # 设置初始大小比例

        main_layout.addWidget(splitter, 1)

    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

        # 统计信息
        self.stats_label = QLabel("")
        self.status_bar.addPermanentWidget(self.stats_label)

    def connect_signals(self):
        """连接信号"""
        # 扫描器信号
        self.scanner.progress_updated.connect(self.on_progress_updated)
        self.scanner.scan_completed.connect(self.on_scan_completed)
        self.scanner.scan_error.connect(self.on_scan_error)
        self.scanner.scan_paused.connect(self.on_scan_paused)
        self.scanner.scan_resumed.connect(self.on_scan_resumed)

    def load_settings(self):
        """加载设置"""
        # 这里可以加载一些界面相关的设置
        pass

    def select_directory(self):
        """选择扫描目录"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择漫画目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )

        if directory:
            self.dir_label.setText(directory)
            self.dir_label.setStyleSheet("color: black; font-style: normal;")
            self.scan_btn.setEnabled(True)
            logger.info(f"选择扫描目录: {directory}")

    def start_scan(self):
        """开始扫描"""
        directory = self.dir_label.text()
        if not directory or directory == "请选择要扫描的目录...":
            QMessageBox.warning(self, "警告", "请先选择要扫描的目录")
            return

        if not os.path.exists(directory):
            QMessageBox.warning(self, "警告", "选择的目录不存在")
            return

        # 清空之前的结果
        self.current_duplicates.clear()
        self.duplicate_list.clear()
        self.image_preview.clear()
        self.info_text.clear()

        # 更新界面状态
        self.scan_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.select_dir_btn.setEnabled(False)

        # 启动扫描线程
        self.scan_thread = ScanThread(self.scanner, directory)
        self.scan_thread.start()

        logger.info(f"开始扫描: {directory}")

    def pause_scan(self):
        """暂停/恢复扫描"""
        if self.scanner.is_paused:
            self.scanner.resume_scan()
        else:
            self.scanner.pause_scan()

    def stop_scan(self):
        """停止扫描"""
        if self.scanner.is_scanning:
            self.scanner.stop_scan()

            # 等待线程结束
            if self.scan_thread and self.scan_thread.isRunning():
                self.scan_thread.wait(3000)  # 等待3秒

            self.reset_scan_ui()

    def reset_scan_ui(self):
        """重置扫描界面状态"""
        self.scan_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.select_dir_btn.setEnabled(True)
        self.pause_btn.setText("暂停")

        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")
        self.status_label.setText("就绪")

    def on_progress_updated(self, progress: ScanProgress):
        """处理进度更新"""
        # 更新进度条
        self.progress_bar.setValue(int(progress.file_progress))

        # 更新进度标签
        self.progress_label.setText(
            f"处理中: {progress.current_file} ({progress.processed_files}/{progress.total_files})"
        )

        # 更新状态栏
        self.status_label.setText(
            f"已处理 {progress.processed_files} 个文件，找到 {progress.duplicates_found} 组重复"
        )

    def on_scan_completed(self, duplicate_groups: List[DuplicateGroup]):
        """处理扫描完成"""
        self.current_duplicates = duplicate_groups
        self.duplicate_list.set_duplicates(duplicate_groups)

        # 更新统计信息
        total_comics = sum(len(group.comics) for group in duplicate_groups)
        self.stats_label.setText(
            f"找到 {len(duplicate_groups)} 组重复漫画，共 {total_comics} 个文件"
        )

        self.reset_scan_ui()

        if duplicate_groups:
            QMessageBox.information(
                self,
                "扫描完成",
                f"扫描完成！\n找到 {len(duplicate_groups)} 组重复漫画，共 {total_comics} 个文件。",
            )
        else:
            QMessageBox.information(self, "扫描完成", "扫描完成！未找到重复漫画。")

    def on_scan_error(self, error_message: str):
        """处理扫描错误"""
        QMessageBox.critical(self, "扫描错误", f"扫描过程中发生错误：\n{error_message}")
        self.reset_scan_ui()

    def on_scan_paused(self):
        """处理扫描暂停"""
        self.pause_btn.setText("恢复")
        self.status_label.setText("扫描已暂停")

    def on_scan_resumed(self):
        """处理扫描恢复"""
        self.pause_btn.setText("暂停")
        self.status_label.setText("扫描进行中...")

    def on_comic_selected(
        self,
        comic_info: ComicInfo,
        duplicate_group: DuplicateGroup,
        duplicate_count: int,
    ):
        """处理漫画选择"""
        # 显示漫画信息
        info_text = f"文件路径: {comic_info.path}\n"
        info_text += f"文件大小: {comic_info.size / 1024 / 1024:.2f} MB\n"
        info_text += f"图片数量: {comic_info.image_count}\n"
        info_text += f"重复图片数量: {duplicate_count}\n"
        info_text += f"修改时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(comic_info.mtime))}\n"

        if duplicate_group:
            info_text += "\n重复组信息:\n"
            info_text += f"相似图片组数: {duplicate_group.similarity_count}\n"
            info_text += f"组内漫画数量: {len(duplicate_group.comics)}\n"

        self.info_text.setText(info_text)

        # 显示图片预览
        self.image_preview.set_comic(comic_info, duplicate_group)

    def on_image_blacklisted(self, image_hash: str):
        """处理图片加入黑名单"""
        # 重新计算重复结果（这里简化处理，实际应该重新扫描）
        QMessageBox.information(
            self, "黑名单", "图片已加入黑名单。\n建议重新扫描以更新结果。"
        )

    def delete_comics(self, comic_paths: List[str]):
        """删除选中的漫画"""
        if not comic_paths:
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(comic_paths)} 个漫画文件吗？\n\n"
            "文件将被移动到回收站，可以恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            success_count = 0
            error_count = 0

            deleted_comic_paths = []
            for comic_path in comic_paths:
                try:
                    comic_path = comic_path.replace("/", "\\")
                    send2trash(comic_path)
                    success_count += 1
                    logger.info(f"已删除漫画: {comic_path}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"删除漫画失败 {comic_path}: {e}")
                    deleted_comic_paths.append(comic_path)

            # 显示结果
            if error_count == 0:
                QMessageBox.information(
                    self, "删除完成", f"成功删除 {success_count} 个漫画文件。"
                )
            else:
                QMessageBox.warning(
                    self,
                    "删除完成",
                    f"成功删除 {success_count} 个文件，{error_count} 个文件删除失败。",
                )

            # 刷新列表
            self.duplicate_list.refresh_after_deletion(deleted_comic_paths)

    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == SettingsDialog.Accepted:
            # 重新加载配置
            self.config.load_config()
            logger.info("设置已更新")

    def export_results(self):
        """导出扫描结果"""
        if not self.current_duplicates:
            QMessageBox.information(self, "提示", "没有可导出的结果")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", "duplicate_results.txt", "文本文件 (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("漫画重复检测结果\n")
                    f.write("=" * 50 + "\n\n")

                    for i, group in enumerate(self.current_duplicates, 1):
                        f.write(f"重复组 {i}:\n")
                        f.write(f"相似图片数量: {group.similarity_count}\n")
                        f.write("包含的漫画文件:\n")

                        for comic in group.comics:
                            f.write(f"  - {comic.path}\n")
                            f.write(f"    大小: {comic.size / 1024 / 1024:.2f} MB\n")
                            f.write(f"    图片数量: {comic.image_count}\n")

                        f.write("\n")

                QMessageBox.information(self, "导出完成", f"结果已导出到: {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出失败: {e}")

    def clear_cache(self):
        """清理缓存"""
        reply = QMessageBox.question(
            self,
            "确认清理",
            "确定要清理所有缓存吗？\n\n这将删除所有扫描结果缓存。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if self.scanner.cache_manager.clear_cache():
                QMessageBox.information(self, "清理完成", "缓存已清理")
            else:
                QMessageBox.warning(self, "清理失败", "缓存清理失败")

    def manage_blacklist(self):
        """管理黑名单"""
        # 这里可以打开黑名单管理对话框
        stats = self.scanner.blacklist_manager.get_statistics()
        QMessageBox.information(
            self,
            "黑名单统计",
            f"当前黑名单包含 {stats['total_count']} 个图片\n"
            f"涉及 {len(stats['archives'])} 个压缩包",
        )

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 Ex-漫画去重工具",
            "Ex-漫画去重工具 v1.0.0\n\n"
            "智能的漫画重复检测和管理工具\n"
            "帮助您轻松整理大量的漫画收藏\n\n"
            "特色功能：\n"
            "• 支持多种图片哈希算法\n"
            "• 黑名单过滤\n"
            "• 结果缓存\n"
            "• 扫描暂停/恢复\n"
            "• 纯内存读取\n\n"
            "系统要求：\n"
            "• Python 3.9+\n"
            "• Windows 10/11\n"
            "• 2GB+ 内存",
        )

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 如果正在扫描，询问是否确认关闭
        if self.scanner.is_scanning:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "正在扫描中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

            # 停止扫描
            self.scanner.stop_scan()
            if self.scan_thread and self.scan_thread.isRunning():
                self.scan_thread.wait(3000)

        # 保存配置
        self.config.save_config()

        event.accept()
