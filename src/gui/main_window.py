# -*- coding: utf-8 -*-
"""
主窗口界面
应用程序的主要用户界面
"""

import os
import time
from typing import List
from datetime import timedelta
from PyQt5.QtWidgets import (
    QApplication,
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
    QToolButton,
    QFrame,
)
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QFont, QIcon
from loguru import logger
from send2trash import send2trash

from ..core.config_manager import ConfigManager
from ..core.scanner import Scanner, ScanProgress, DuplicateGroup, ComicInfo
from .settings_dialog import SettingsDialog
from .image_preview_widget import ImagePreviewWidget
from .duplicate_list_widget import DuplicateListWidget
from .about_dialog import AboutDialog


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
        self.load_settings()
        self.connect_signals()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Ex-漫画去重工具 v1.0.0")
        self.setWindowIcon(QIcon("resources/icon.png"))

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建菜单栏
        self.create_menu_bar()

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

        # 黑名单统计
        blacklist_action = QAction("黑名单统计(&B)", self)
        blacklist_action.triggered.connect(self.blacklist_statistics)
        tools_menu.addAction(blacklist_action)

        # 刷新黑名单
        refresh_blacklist_action = QAction("刷新黑名单(&R)", self)
        refresh_blacklist_action.triggered.connect(self.refresh_blacklist)
        tools_menu.addAction(refresh_blacklist_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """创建工具栏"""
        # 目录选择区域
        self.dir_group = QGroupBox("扫描目录")
        dir_layout = QHBoxLayout(self.dir_group)

        self.dir_label = QLabel("请选择要扫描的目录...")
        self.dir_label.setStyleSheet("color: gray; font-style: italic;")

        self.select_dir_btn = QPushButton("选择目录")
        self.select_dir_btn.clicked.connect(self.select_directory)

        dir_layout.addWidget(self.dir_label, 1)
        dir_layout.addWidget(self.select_dir_btn)

        # 控制按钮区域
        self.control_group = QGroupBox("扫描控制")
        control_layout = QHBoxLayout(self.control_group)

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
        self.progress_group = QGroupBox("扫描进度")
        progress_layout = QVBoxLayout(self.progress_group)

        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        # 可折叠内容框架
        self.collapsible_frame = QFrame()
        collapsible_layout = QVBoxLayout(self.collapsible_frame)
        collapsible_layout.setContentsMargins(0, 0, 0, 0)

        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(self.dir_group, 3)
        top_row_layout.addWidget(self.control_group, 1)

        collapsible_layout.addLayout(top_row_layout)
        collapsible_layout.addWidget(self.progress_group)

        # 工具栏主布局
        toolbar_main_layout = QVBoxLayout()
        toolbar_main_layout.setContentsMargins(0, 0, 0, 0)

        # 折叠按钮
        self.collapse_button = QToolButton()
        self.collapse_button.setArrowType(Qt.DownArrow)
        self.collapse_button.setText("工具栏")
        self.collapse_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.collapse_button.clicked.connect(self.toggle_groups_visibility)

        # 将折叠按钮和可折叠框架添加到主布局
        toolbar_main_layout.addWidget(self.collapse_button)
        toolbar_main_layout.addWidget(self.collapsible_frame)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_main_layout)

        return toolbar_widget

    def toggle_groups_visibility(self):
        """切换分组的可见性"""
        is_visible = not self.dir_group.isVisible()
        self.dir_group.setVisible(is_visible)
        self.control_group.setVisible(is_visible)
        self.progress_group.setVisible(is_visible)

    def create_main_content(self, main_layout):
        """创建主要内容区域"""
        # 创建工具栏
        self.toolbar_widget = self.create_toolbar()
        main_layout.addWidget(self.toolbar_widget)

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
        self.status_bar.addWidget(self.status_label, 1)

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

        # 加载窗口大小
        width, height = self.config.get_window_geometry()
        self.resize(width, height)

        # 加载上次扫描的目录
        last_dir = self.config.get("last_scanned_directory")
        if last_dir and os.path.isdir(last_dir):
            self.dir_label.setText(last_dir)
            self.dir_label.setStyleSheet("color: black; font-style: normal;")
            self.scan_btn.setEnabled(True)

    def select_directory(self):
        """选择扫描目录"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择漫画目录",
            self.config.get("last_scanned_directory", ""),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )

        if directory:
            directory = directory.replace("/", "\\")
            self.dir_label.setText(directory)
            self.dir_label.setStyleSheet("color: black; font-style: normal;")
            self.scan_btn.setEnabled(True)
            self.config.set("last_scanned_directory", directory)
            self.config.save_config()
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
        if progress.stage == "scanning":
            progress_text = "扫描中"
            self.progress_group.setTitle("扫描进度")
        else:
            progress_text = "处理中"
            self.progress_group.setTitle("处理进度")
        self.progress_label.setText(
            f"{progress_text} ({progress.processed_files}/{progress.total_files}): {progress.current_file}"
        )

        # 计算并显示经过时间和预计剩余时间
        elapsed_time = max(time.time() - progress.start_time, 1.0)
        elapsed_str = str(timedelta(seconds=int(elapsed_time)))

        if progress.stage == "scanning":
            processed_text = "已扫描"
            duplicates_text = ""
        else:
            processed_text = "已处理"
            duplicates_text = f"，找到 {progress.duplicates_found} 组重复"

        # 更新进度历史，只保留最近的数据
        current_time = time.time()
        if progress.history is None:
            progress.history = []
        progress.history.append((current_time, progress.processed_files))

        # 移除超过10分钟的旧数据
        progress.history = [
            (t, p) for t, p in progress.history if current_time - t <= 60 * 10
        ]

        files_per_second_window = 0
        if len(progress.history) > 1:
            # 计算最近时段内的处理速度
            time_window_start = progress.history[0][0]
            files_processed_window_start = progress.history[0][1]
            time_window_end = progress.history[-1][0]
            files_processed_window_end = progress.history[-1][1]

            time_diff = time_window_end - time_window_start
            files_diff = files_processed_window_end - files_processed_window_start

            if time_diff > 0:
                files_per_second_window = files_diff / time_diff

        remaining_files = progress.total_files - progress.processed_files

        if files_per_second_window > 0 and remaining_files > 0:
            remaining_time = remaining_files / files_per_second_window
            remaining_str = str(timedelta(seconds=int(remaining_time)))
            self.status_label.setText(
                f"{processed_text} {progress.processed_files} 个文件{duplicates_text} | 耗时: {elapsed_str} | 预计剩余: {remaining_str}"
            )
        else:
            self.status_label.setText(
                f"{processed_text} {progress.processed_files} 个文件{duplicates_text} | 耗时: {elapsed_str}"
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

        QApplication.alert(self)
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
        info_text = f"文件路径: {comic_info.path.replace('/', '\\')}\n"
        info_text += f"文件大小: {comic_info.size / 1024 / 1024:.2f} MB\n"
        info_text += f"图片数量: {len(comic_info.image_hashes)}\n"
        info_text += f"重复图片数量: {duplicate_count}\n"
        info_text += f"修改时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(comic_info.mtime))}\n"

        if duplicate_group:
            info_text += "\n重复组信息:\n"
            info_text += f"相似图片组数: {len(duplicate_group.similar_hash_groups)}\n"
            info_text += f"组内漫画数量: {len(duplicate_group.comics)}\n"

        self.info_text.setText(info_text)

        # 显示图片预览
        self.image_preview.set_comic(comic_info, duplicate_group)

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
                    send2trash(comic_path.replace("/", "\\"))
                    success_count += 1
                    logger.info(f"已删除漫画: {comic_path}")
                    deleted_comic_paths.append(comic_path)
                except Exception as e:
                    error_count += 1
                    logger.error(f"删除漫画失败 {comic_path}: {e}")

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
                        f.write(f"相似图片数量: {len(group.similar_hash_groups)}\n")
                        f.write("包含的漫画文件:\n")

                        for comic in group.comics:
                            f.write(f"  - {comic.path}\n")
                            f.write(f"    大小: {comic.size / 1024 / 1024:.2f} MB\n")
                            f.write(f"    图片数量: {len(comic.image_hashes)}\n")

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

    def blacklist_statistics(self):
        """黑名单统计"""
        # 这里可以打开黑名单统计对话框
        stats = self.scanner.blacklist_manager.get_statistics()
        QMessageBox.information(
            self,
            "黑名单统计",
            f"当前黑名单包含 {stats['total_count']} 个图片",
        )

    def refresh_blacklist(self):
        """刷新黑名单"""
        try:
            self.scanner.blacklist_manager.clear_blacklist()
            self.scanner.blacklist_manager.load_blacklist()
            QMessageBox.information(self, "刷新完成", "黑名单已刷新！")
            logger.info("黑名单已刷新")
        except Exception as e:
            QMessageBox.critical(self, "刷新失败", f"黑名单刷新失败: {e}")
            logger.error(f"黑名单刷新失败: {e}")

    def show_about(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec_()

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
