#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漫画去重工具主入口
"""

import os
import sys

from loguru import logger
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from src import __version__
from src.core.config_manager import ConfigManager
from src.gui.main_window import MainWindow

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging():
    """设置日志配置"""
    logger.remove()  # 移除默认处理器

    # 控制台输出
    try:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )
    except Exception as e:
        logger.error(f"日志配置失败: {e}")

    # 文件输出
    logger.add(
        "logs/app.log",
        level="INFO",
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

    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName("Ex-漫画去重工具")
    app.setApplicationVersion(__version__)

    try:
        # 初始化配置管理器
        config_manager = ConfigManager()

        # 创建主窗口
        main_window = MainWindow(config_manager)
        main_window.show()

        logger.info("应用程序启动成功")

        # 运行应用程序
        sys.exit(app.exec_())

    except Exception:
        logger.exception("应用程序启动失败，详细错误信息:")
        sys.exit(1)


if __name__ == "__main__":
    main()
