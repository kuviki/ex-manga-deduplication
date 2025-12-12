# -*- coding: utf-8 -*-
"""
工具模块
包含各种实用工具函数和类
"""

from typing import TypeGuard

__all__ = ["file_utils", "image_utils", "ui_utils"]


def is_str_list(obj) -> TypeGuard[list[str]]:
    """检查对象是否为字符串列表"""
    return isinstance(obj, list) and all(isinstance(item, str) for item in obj)


def is_int_list(obj) -> TypeGuard[list[int]]:
    """检查对象是否为整数列表"""
    return isinstance(obj, list) and all(isinstance(item, int) for item in obj)
