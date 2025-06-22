#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漫画去重工具主入口
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui.main_window import MainWindow
from src.core.config_manager import ConfigManager


def setup_logging():
    """设置日志配置"""
    logger.remove()  # 移除默认处理器

    # 控制台输出
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 文件输出
    logger.add(
        "logs/app.log",
        level="WARNING",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )


def main():
    """主函数"""
    # 设置日志
    setup_logging()
    logger.info("启动漫画去重工具")

    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName("Ex-漫画去重工具")
    app.setApplicationVersion("1.0.0")

    # 设置高DPI支持
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    try:
        # 初始化配置管理器
        config_manager = ConfigManager()

        # 创建主窗口
        main_window = MainWindow(config_manager)
        main_window.show()

        logger.info("应用程序启动成功")

        # 运行应用程序
        sys.exit(app.exec_())

    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
