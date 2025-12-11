# -*- coding: utf-8 -*-
"""
重复漫画列表组件
用于显示和管理重复的漫画
"""

import os
import subprocess
from typing import Dict, List, Optional, Set

from loguru import logger
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QShortcut,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from win32com.shell import shell

from ..core.config_manager import ConfigManager
from ..core.scanner import DuplicateGroup


class DuplicateListWidget(QWidget):
    """重复漫画列表组件"""

    # 信号定义
    comic_selected = pyqtSignal(
        object, object, int
    )  # ComicInfo, DuplicateGroup, duplicate_count
    comics_to_delete = pyqtSignal(list)  # List[str] - comic paths
    multi_selection_changed = pyqtSignal(list)  # List[ComicInfo]

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.duplicate_groups = []
        self._checked_comic_paths = set(
            self.config.get_checked_comic_paths()
        )  # 加载已检查的漫画路径
        self._show_only_unchecked_groups = True  # 是否仅显示存在未检查的重复组
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 标题和统计信息
        header_layout = QHBoxLayout()

        self.title_label = QLabel("重复漫画列表")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: gray;")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.stats_label)

        layout.addLayout(header_layout)

        # 过滤选项
        filter_layout = QHBoxLayout()
        self.show_unchecked_checkbox = QCheckBox("仅显示未检查组")
        self.show_unchecked_checkbox.setChecked(self._show_only_unchecked_groups)
        self.show_unchecked_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.show_unchecked_checkbox)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 树形控件
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(
            ["漫画文件", "大小", "图片数 (重复图片)", "相似度", "操作"]
        )
        self.tree_widget.setRootIsDecorated(True)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)

        # 设置列宽和排序
        header = self.tree_widget.header()
        self.tree_widget.setColumnWidth(0, 330)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionsMovable(True)
        header.setSortIndicatorShown(True)
        header.setStretchLastSection(True)

        # 连接信号
        self.tree_widget.itemClicked.connect(self.on_item_clicked)
        self.tree_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.tree_widget)

        # 添加全局空格键快捷键，用于切换选中项的勾选状态
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self.tree_widget)
        self.space_shortcut.activated.connect(self._toggle_selected_items_check_state)

        # 控制按钮
        button_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all)

        self.select_none_btn = QPushButton("取消全选")
        self.select_none_btn.clicked.connect(self.select_none)

        self.select_duplicates_btn = QPushButton("选择重复项")
        self.select_duplicates_btn.clicked.connect(self.select_duplicates)

        self.delete_selected_btn = QPushButton("删除选中")
        self.delete_selected_btn.clicked.connect(self.delete_selected)
        self.delete_selected_btn.setStyleSheet(
            "QPushButton { background-color: #ff6b6b; color: white; }"
        )

        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.select_none_btn)
        button_layout.addWidget(self.select_duplicates_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_selected_btn)

        layout.addLayout(button_layout)

    def set_duplicates(self, duplicate_groups: List[DuplicateGroup]):
        """设置重复漫画数据"""
        self.duplicate_groups = duplicate_groups
        self.refresh_list()

    def _on_filter_changed(self, state):
        """处理过滤选项改变"""
        self._show_only_unchecked_groups = state == Qt.Checked
        self.refresh_list()

    def refresh_list(self):
        """刷新列表显示"""
        self.tree_widget.clear()

        if not self.duplicate_groups:
            self.stats_label.setText("未找到重复漫画")
            return

        total_comics = 0
        visible_groups = 0

        # 预先创建样式对象，避免重复创建
        bold_font = QFont()
        bold_font.setBold(True)
        group_background = QBrush(QColor(240, 240, 240))
        checked_background = QBrush(QColor(220, 255, 220))
        unchecked_background = QBrush(QColor(255, 255, 255))

        # 临时禁用UI更新以提高性能
        self.tree_widget.setUpdatesEnabled(False)

        try:
            for i, group in enumerate(self.duplicate_groups, 1):
                # 检查是否需要过滤此组（仅显示存在未检查的重复组）
                if self._show_only_unchecked_groups:
                    # 检查组中是否存在未检查的漫画
                    has_unchecked = any(
                        comic.path not in self._checked_comic_paths
                        for comic in group.comics
                    )
                    if not has_unchecked:
                        continue  # 跳过此组，因为所有漫画都已检查

                # 创建组节点
                group_item = QTreeWidgetItem(self.tree_widget)
                group_item.setText(0, f"重复组 {i} ({len(group.comics)} 个文件)")
                group_item.setText(3, f"{len(group.similar_hash_groups)} 组相似图片")
                visible_groups += 1

                # 设置组节点样式
                group_item.setFont(0, bold_font)
                group_item.setBackground(0, group_background)

                # 存储组数据
                group_item.setData(0, Qt.UserRole, {"type": "group", "group": group})

                # 预处理哈希数据，避免内层循环重复计算
                group_image_hashes = set()

                # 收集所有哈希值
                for hash1, hash2, _similarity in group.similar_hash_groups:
                    group_image_hashes.add(hash1)
                    group_image_hashes.add(hash2)

                # 为每个漫画预计算重复图片数量
                comic_duplicate_counts = []
                for comic_idx, comic in enumerate(group.comics):
                    duplicate_count = 0
                    comic_hash_set = set(hash[1] for hash in comic.image_hashes)
                    # 使用集合交集计算，比逐个判断更高效
                    duplicate_count = len(comic_hash_set & group_image_hashes)
                    comic_duplicate_counts.append(duplicate_count)

                # 添加漫画节点
                for comic_idx, comic in enumerate(group.comics):
                    comic_item = QTreeWidgetItem(group_item)
                    comic_item.setText(0, os.path.basename(comic.path))
                    comic_item.setText(1, self._format_file_size(comic.size))
                    comic_item.setText(
                        2,
                        f"{len(comic.image_hashes)} ({comic_duplicate_counts[comic_idx]})",
                    )

                    # 设置工具提示
                    comic_item.setToolTip(0, comic.path)

                    # 存储漫画数据
                    comic_item.setData(
                        0,
                        Qt.UserRole,
                        {
                            "type": "comic",
                            "comic": comic,
                            "group": group,
                            "duplicate_count": comic_duplicate_counts[comic_idx],
                        },
                    )

                    # 添加复选框
                    comic_item.setFlags(comic_item.flags() | Qt.ItemIsUserCheckable)
                    comic_item.setCheckState(0, Qt.Unchecked)

                    # 根据 checked 状态设置背景色
                    if comic.path in self._checked_comic_paths:
                        comic_item.setBackground(0, checked_background)
                        comic.checked = True
                    else:
                        comic_item.setBackground(0, unchecked_background)
                        comic.checked = False

                    total_comics += 1

                # 展开组节点
                group_item.setExpanded(True)

        finally:
            # 重新启用UI更新
            self.tree_widget.setUpdatesEnabled(True)

        # 更新统计信息
        if self._show_only_unchecked_groups:
            self.stats_label.setText(
                f"显示 {visible_groups}/{len(self.duplicate_groups)} 组重复，共 {total_comics} 个文件"
            )
        else:
            self.stats_label.setText(
                f"{len(self.duplicate_groups)} 组重复，共 {total_comics} 个文件"
            )

    def _create_action_buttons(self, item, comic) -> QWidget:
        """为漫画项目创建操作按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # 通用按钮样式
        button_style = """
            QPushButton {
                background-color: transparent;
                border: 0;
                border-radius: 3px;
                padding: 2px 2px;
                margin: 0 2px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #aaaaaa;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QPushButton:disabled {
                color: #999999;
                border: 1px solid #dddddd;
            }
        """

        # 打开文件位置
        open_location_btn = QPushButton("📁")
        open_location_btn.setStyleSheet(button_style)
        open_location_btn.setToolTip("打开文件位置")
        open_location_btn.clicked.connect(lambda: self.open_file_location(comic.path))
        layout.addWidget(open_location_btn)

        # 用默认程序打开
        open_default_btn = QPushButton("📄")
        open_default_btn.setStyleSheet(button_style)
        open_default_btn.setToolTip("用默认程序打开")
        open_default_btn.clicked.connect(lambda: self.open_with_default(comic.path))
        layout.addWidget(open_default_btn)

        # 用漫画查看器打开
        open_viewer_btn = QPushButton("🖼️")
        open_viewer_btn.setStyleSheet(button_style)
        open_viewer_btn.setToolTip("用漫画查看器打开")
        open_viewer_btn.clicked.connect(lambda: self.open_with_viewer(comic.path))
        viewer_path = self.config.get_comic_viewer_path()
        if not viewer_path or not os.path.exists(viewer_path):
            open_viewer_btn.setDisabled(True)
        layout.addWidget(open_viewer_btn)

        # 标记/取消标记
        check_mark_btn = QPushButton("✅")
        check_mark_btn.setStyleSheet(button_style)
        check_mark_btn.setToolTip("切换已检查标记")
        check_mark_btn.clicked.connect(
            lambda: self._update_comic_checked_state(item, comic, not comic.checked)
        )
        layout.addWidget(check_mark_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """处理项目点击事件"""
        # 点击事件现在由 on_selection_changed 统一处理
        pass

    def on_selection_changed(self):
        """处理选择变化事件（支持鼠标点击、右键、键盘方向键等）"""
        # 先清除所有现有的操作按钮
        self._clear_all_action_buttons()

        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return

        # 获取第一个选中的项目
        item = selected_items[0]
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if data["type"] == "comic":
            # 创建并添加操作按钮
            action_widget = self._create_action_buttons(item, data["comic"])
            self.tree_widget.setItemWidget(item, 4, action_widget)

            # 发射漫画选择信号
            self.comic_selected.emit(
                data["comic"], data["group"], data["duplicate_count"]
            )

        # 处理多选变化
        selected_comics = []
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and data["type"] == "comic":
                selected_comics.append(data["comic"])
        self.multi_selection_changed.emit(selected_comics)

    def _clear_all_action_buttons(self):
        """清除所有操作按钮"""
        # 遍历所有项目
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                comic_item = group_item.child(j)
                # 清除操作按钮
                self.tree_widget.setItemWidget(comic_item, 4, None)

    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.tree_widget.itemAt(position)
        if not item:
            return

        data = item.data(0, Qt.UserRole)
        if not data or data["type"] != "comic":
            return

        comic = data["comic"]

        menu = QMenu(self)

        # 打开文件位置
        open_location_action = menu.addAction("打开文件位置")
        open_location_action.triggered.connect(
            lambda: self.open_file_location(comic.path)
        )

        # 用默认程序打开
        open_default_action = menu.addAction("用默认程序打开")
        open_default_action.triggered.connect(
            lambda: self.open_with_default(comic.path)
        )

        # 用漫画查看器打开
        open_viewer_action = menu.addAction("用漫画查看器打开")
        open_viewer_action.triggered.connect(lambda: self.open_with_viewer(comic.path))
        viewer_path = self.config.get_comic_viewer_path()
        if not viewer_path or not os.path.exists(viewer_path):
            open_viewer_action.setDisabled(True)

        menu.addSeparator()

        # 标记操作 - 同时显示两个选项
        selected_items = self._get_selected_comic_items()
        if len(selected_items) > 1:
            # 批量标记操作
            check_mark_action = menu.addAction(
                f"标记为已检查 ({len(selected_items)}个文件)"
            )
            check_mark_action.triggered.connect(
                lambda: self._batch_update_checked_state(selected_items, True)
            )

            uncheck_mark_action = menu.addAction(
                f"取消标记 ({len(selected_items)}个文件)"
            )
            uncheck_mark_action.triggered.connect(
                lambda: self._batch_update_checked_state(selected_items, False)
            )
        else:
            # 单个文件标记操作
            check_mark_action = menu.addAction("标记为已检查")
            check_mark_action.triggered.connect(
                lambda: self._update_comic_checked_state(item, comic, True)
            )

            uncheck_mark_action = menu.addAction("取消标记")
            uncheck_mark_action.triggered.connect(
                lambda: self._update_comic_checked_state(item, comic, False)
            )

        menu.addSeparator()

        # 选择/取消选择
        if item.checkState(0) == Qt.Checked:
            uncheck_action = menu.addAction("取消选择")
            uncheck_action.triggered.connect(
                lambda: item.setCheckState(0, Qt.Unchecked)
            )
        else:
            check_action = menu.addAction("选择")
            check_action.triggered.connect(lambda: item.setCheckState(0, Qt.Checked))

        # 选择同组其他文件
        select_group_action = menu.addAction("选择同组文件")
        select_group_action.triggered.connect(
            lambda: self.select_group_items(data["group"], True)
        )

        # 取消选择同组其他文件
        unselect_group_action = menu.addAction("取消选择同组文件")
        unselect_group_action.triggered.connect(
            lambda: self.select_group_items(data["group"], False)
        )

        menu.addSeparator()

        # 删除文件
        delete_action = menu.addAction("删除此文件")
        delete_action.triggered.connect(lambda: self.delete_comic(comic.path))

        # 切换选中项勾选状态
        toggle_check_action = menu.addAction("切换选中项勾选状态")
        toggle_check_action.triggered.connect(self._toggle_selected_items_check_state)

        # 创建快捷键
        shortcuts = {
            "L": open_location_action,
            "O": open_default_action,
            "V": open_viewer_action,
            "M": check_mark_action if len(selected_items) <= 1 else check_mark_action,
            "U": uncheck_mark_action,
            "Space": toggle_check_action,
            "A": select_group_action,
            "Shift+A": unselect_group_action,
            "Delete": delete_action,
        }

        # 为菜单添加快捷键
        for key, action in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), menu)
            action.setShortcut(key)
            shortcut.activated.connect(action.trigger)
            shortcut.activated.connect(menu.close)

        # 显示菜单
        menu.exec_(self.tree_widget.mapToGlobal(position))

    def open_file_location(self, file_path: str):
        """打开文件位置"""

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", "文件不存在")
            return

        try:
            # 获取文件所在的目录
            folder_path = os.path.dirname(file_path)
            # 获取文件名
            file_name = os.path.basename(file_path)

            # 创建PIDL
            folder_pidl, _ = shell.SHILCreateFromPath(folder_path, 0)
            desktop = shell.SHGetDesktopFolder()
            folder = desktop.BindToObject(folder_pidl, None, shell.IID_IShellFolder)

            # 获取文件项的PIDL
            item_pidl = folder.ParseDisplayName(0, None, file_name)[1]

            # 调用SHOpenFolderAndSelectItems
            shell.SHOpenFolderAndSelectItems(folder_pidl, (item_pidl,), 0)
        except Exception as e:
            logger.error(f"打开文件位置失败: {e}")
            QMessageBox.critical(self, "错误", f"打开文件位置失败: {e}")

    def open_with_viewer(self, file_path: str):
        """用指定漫画查看器打开"""
        try:
            viewer_path = self.config.get_comic_viewer_path()
            if viewer_path and os.path.exists(viewer_path):
                subprocess.Popen([viewer_path, file_path])
            else:
                QMessageBox.warning(self, "警告", "漫画查看器程序不存在")
        except Exception as e:
            logger.error(f"打开漫画查看器失败: {e}")
            QMessageBox.critical(self, "错误", f"打开漫画查看器失败: {e}")

    def open_with_default(self, file_path: str):
        """用默认程序打开"""
        try:
            if os.path.exists(file_path):
                os.startfile(file_path)  # Windows
            else:
                QMessageBox.warning(self, "警告", "文件不存在")
        except Exception as e:
            logger.error(f"打开文件失败: {e}")
            QMessageBox.critical(self, "错误", f"打开文件失败: {e}")

    def select_all(self):
        """全选所有漫画"""
        self._set_all_check_state(Qt.Checked)

    def select_none(self):
        """取消全选"""
        self._set_all_check_state(Qt.Unchecked)

    def select_duplicates(self):
        """智能选择重复项（每组保留一个）"""
        self.select_none()

        for group_index in range(self.tree_widget.topLevelItemCount()):
            group_item = self.tree_widget.topLevelItem(group_index)

            # 跳过第一个文件，选择其余文件
            for child_index in range(1, group_item.childCount()):
                child_item = group_item.child(child_index)
                child_item.setCheckState(0, Qt.Checked)

    def select_group_items(self, target_group: DuplicateGroup, check: bool):
        """选择指定组的所有项目"""
        for group_index in range(self.tree_widget.topLevelItemCount()):
            group_item = self.tree_widget.topLevelItem(group_index)
            data = group_item.data(0, Qt.UserRole)

            if data and data["type"] == "group" and data["group"] == target_group:
                for child_index in range(group_item.childCount()):
                    child_item = group_item.child(child_index)
                    child_item.setCheckState(0, Qt.Checked if check else Qt.Unchecked)
                break

    def delete_selected(self):
        """删除选中的漫画"""
        selected_paths = self._get_selected_comic_paths()

        if not selected_paths:
            QMessageBox.information(self, "提示", "请先选择要删除的漫画")
            return

        self.comics_to_delete.emit(selected_paths)

    def delete_comic(self, comic_path: str):
        """删除单个漫画"""
        self.comics_to_delete.emit([comic_path])

    def refresh_after_deletion(self, deleted_paths: List[str]):
        """删除文件后刷新列表"""
        # 从重复组中移除已删除的漫画
        for group in self.duplicate_groups:
            group.comics = [
                comic for comic in group.comics if comic.path not in deleted_paths
            ]

        # 如果组中只剩一个漫画，移除整个组
        self.duplicate_groups = [
            group for group in self.duplicate_groups if len(group.comics) > 1
        ]

        # 从重复组中移除无效的图片哈希对
        for group in self.duplicate_groups:
            valid_hashes: Dict[str, Set[int]] = dict()

            # 收集当前组中的所有哈希值
            for idx, comic in enumerate(group.comics):
                for hash in comic.image_hashes:
                    if hash[1] in valid_hashes:
                        valid_hashes[hash[1]].add(idx)
                    else:
                        valid_hashes[hash[1]] = {idx}

            group.similar_hash_groups = {
                (h1, h2, sim)
                for h1, h2, sim in group.similar_hash_groups
                if h1 in valid_hashes
                and h2 in valid_hashes
                and len(valid_hashes[h1].union(valid_hashes[h2])) > 1
            }

        # 从重复组中移除无重复的漫画
        for group in self.duplicate_groups:
            similar_hashes = set()
            for hash in group.similar_hash_groups:
                similar_hashes.add(hash[0])
                similar_hashes.add(hash[1])

            # 移除不在相似哈希中的漫画
            group.comics = [
                comic
                for comic in group.comics
                if any(h[1] in similar_hashes for h in comic.image_hashes)
            ]

        # 如果组中只剩一个漫画，移除整个组
        self.duplicate_groups = [
            group for group in self.duplicate_groups if len(group.comics) > 1
        ]

        # 刷新显示
        self.refresh_list()

    def clear(self):
        """清空列表"""
        self.duplicate_groups.clear()
        self.tree_widget.clear()
        self.stats_label.setText("")

    def _set_all_check_state(self, state: Qt.CheckState):
        """设置所有项目的选中状态"""
        for group_index in range(self.tree_widget.topLevelItemCount()):
            group_item = self.tree_widget.topLevelItem(group_index)

            for child_index in range(group_item.childCount()):
                child_item = group_item.child(child_index)
                child_item.setCheckState(0, state)

    def _toggle_selected_items_check_state(self):
        """切换所有选中项的勾选状态"""
        selected_items = self._get_selected_comic_items()
        if not selected_items:
            return

        # 切换每个选中项的状态
        for item in selected_items:
            current_state = item.checkState(0)
            new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
            item.setCheckState(0, new_state)

    def _get_selected_comic_paths(self) -> List[str]:
        """获取选中的漫画路径列表"""
        selected_paths = []

        for group_index in range(self.tree_widget.topLevelItemCount()):
            group_item = self.tree_widget.topLevelItem(group_index)

            for child_index in range(group_item.childCount()):
                child_item = group_item.child(child_index)

                if child_item.checkState(0) == Qt.Checked:
                    data = child_item.data(0, Qt.UserRole)
                    if data and data["type"] == "comic":
                        selected_paths.append(data["comic"].path)

        return selected_paths

    def _get_selected_comic_items(self) -> List[QTreeWidgetItem]:
        """获取当前选中的漫画项目列表"""

        comic_items = []
        for item in self.tree_widget.selectedItems():
            # 过滤出类型为"comic"的项
            data = item.data(0, Qt.UserRole)
            if data and data["type"] == "comic":
                comic_items.append(item)
        return comic_items

    def _batch_update_checked_state(
        self, selected_items: List[QTreeWidgetItem], checked: bool
    ):
        """批量更新漫画的已检查状态"""
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and data["type"] == "comic":
                comic = data["comic"]
                comic.checked = checked

                if comic.checked:
                    self._checked_comic_paths.add(comic.path)
                    item.setBackground(0, QBrush(QColor(220, 255, 220)))  # 浅绿色背景
                else:
                    self._checked_comic_paths.discard(comic.path)
                    item.setBackground(0, QBrush(QColor(255, 255, 255)))  # 白色背景

        # 持久化已检查的漫画路径
        self.config.set_checked_comic_paths(list(self._checked_comic_paths))
        self.config.save_config()

    def _update_comic_checked_state(
        self, item: QTreeWidgetItem, comic: object, checked: Optional[bool] = None
    ):
        """更新漫画的已检查状态并持久化"""
        if checked is None:
            # 如果未指定checked状态，则切换当前状态
            comic.checked = not comic.checked
        else:
            comic.checked = checked

        if comic.checked:
            self._checked_comic_paths.add(comic.path)
            item.setBackground(0, QBrush(QColor(220, 255, 220)))  # 浅绿色背景
        else:
            self._checked_comic_paths.discard(comic.path)
            item.setBackground(0, QBrush(QColor(255, 255, 255)))  # 白色背景

        # 持久化已检查的漫画路径
        self.config.set_checked_comic_paths(list(self._checked_comic_paths))
        self.config.save_config()

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
