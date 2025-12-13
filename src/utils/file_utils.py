# -*- coding: utf-8 -*-
"""
文件工具模块
提供文件操作相关的实用函数
"""

import os


def is_supported_archive(file_path: str) -> bool:
    """检查文件是否为支持的压缩格式"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [".zip", ".rar", ".cbz", ".cbr"]


def is_comic_folder(folder_path: str) -> bool:
    """检查文件夹是否为漫画文件夹（包含图片文件）"""
    if not os.path.isdir(folder_path):
        return False

    # 检查文件夹中是否有图片文件
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and is_supported_image(file):
            return True

    return False


def is_supported_image(file_path: str) -> bool:
    """检查文件是否为支持的图片格式"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [
        ".jpg",
        ".jpeg",
        ".jpe",
        ".jif",
        ".jfif",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
    ]


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
