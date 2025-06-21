#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图片预览组件的重复图片显示功能
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from src.gui.image_preview_widget import ImagePreviewWidget
from src.core.config_manager import ConfigManager
from src.core.scanner import ComicInfo, DuplicateGroup


def test_preview_widget():
    """测试预览组件"""
    app = QApplication(sys.argv)

    # 创建配置管理器
    config = ConfigManager()

    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("图片预览组件测试")
    window.setGeometry(100, 100, 800, 600)

    # 创建中央部件
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)

    # 创建预览组件
    preview_widget = ImagePreviewWidget(config)
    layout.addWidget(preview_widget)

    window.setCentralWidget(central_widget)

    # 创建测试数据
    comic1 = ComicInfo(
        path="test.zip",
        size=1024000,
        mtime=1234567890,
        image_count=10,
        image_hashes={"000.jpg": "hash1", "001.jpg": "hash2", "002.jpg": "hash3"},
    )

    comic2 = ComicInfo(
        path="test.rar",
        size=2048000,
        mtime=1234567891,
        image_count=8,
        image_hashes={
            "1.jpg": "hash1",  # 与comic1重复
            "2.jpg": "hash4",
            "3.jpg": "hash2",  # 与comic1重复
        },
    )

    duplicate_group = DuplicateGroup(
        comics=[comic1, comic2],
        similar_images=[
            ("hash1", "hash1", 0),  # 完全相同
            ("hash2", "hash2", 0),  # 完全相同
        ],
        similarity_count=2,
    )

    # 设置测试数据
    preview_widget.set_comic(comic1, duplicate_group)

    window.show()

    print("测试窗口已打开")
    print("功能说明:")
    print("1. 勾选'仅显示重复图片'复选框可切换显示模式")
    print("2. 重复图片会显示橙色边框")
    print("3. 图片信息会显示来源漫画")
    print("4. 在仅显示重复图片模式下，图片数量控件会被禁用")

    return app.exec_()


if __name__ == "__main__":
    test_preview_widget()
