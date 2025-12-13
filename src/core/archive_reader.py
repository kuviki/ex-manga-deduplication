# -*- coding: utf-8 -*-
"""
压缩包读取模块
负责读取和解析漫画压缩包（ZIP、RAR）
"""

import os
import zipfile
from io import BytesIO
from typing import Dict, Generator, List, Optional, Tuple

import rarfile
from loguru import logger
from natsort import os_sorted
from PIL import Image

from ..utils.file_utils import is_supported_image


class ArchiveReader:
    """压缩包读取器"""

    def __init__(self):
        pass

        # 设置RAR工具路径（如果需要）
        # rarfile.UNRAR_TOOL = "path/to/unrar.exe"  # Windows

    def get_image_files(self, archive_path: str) -> List[str]:
        """获取压缩包或文件夹中的所有图片文件列表

        Args:
            archive_path: 压缩包路径或文件夹路径

        Returns:
            List[str]: 图片文件名列表（按自然排序）
        """
        try:
            image_files = []

            # 处理文件夹
            if os.path.isdir(archive_path):
                for filename in os.listdir(archive_path):
                    file_path = os.path.join(archive_path, filename)
                    if os.path.isfile(file_path) and is_supported_image(filename):
                        image_files.append(filename)

            # 处理压缩包
            elif archive_path.lower().endswith((".zip", ".cbz")):
                with zipfile.ZipFile(archive_path, "r") as archive:
                    for filename in archive.namelist():
                        if is_supported_image(filename) and not filename.endswith("/"):
                            image_files.append(filename)

            elif archive_path.lower().endswith((".rar", ".cbr")):
                with rarfile.RarFile(archive_path, "r") as archive:
                    for filename in archive.namelist():
                        if is_supported_image(filename) and not filename.endswith("/"):
                            image_files.append(filename)

            # 按操作系统排序
            image_files = os_sorted(image_files)
            return image_files

        except Exception as e:
            logger.error(f"获取图片列表失败 {archive_path}: {e}")
            return []

    def read_image(self, archive_path: str, image_filename: str) -> Optional[bytes]:
        """从压缩包或文件夹中读取指定图片

        Args:
            archive_path: 压缩包路径或文件夹路径
            image_filename: 图片文件名

        Returns:
            Optional[bytes]: 图片数据，失败时返回None
        """
        try:
            # 处理文件夹
            if os.path.isdir(archive_path):
                image_path = os.path.join(archive_path, image_filename)
                if os.path.isfile(image_path):
                    with open(image_path, "rb") as f:
                        return f.read()
                return None

            # 处理压缩包
            elif archive_path.lower().endswith((".zip", ".cbz")):
                with zipfile.ZipFile(archive_path, "r") as archive:
                    return archive.read(image_filename)

            elif archive_path.lower().endswith((".rar", ".cbr")):
                with rarfile.RarFile(archive_path, "r") as archive:
                    return archive.read(image_filename)

            return None

        except Exception as e:
            logger.error(f"读取图片失败 {archive_path}/{image_filename}: {e}")
            return None

    def read_all_images(
        self, archive_path: str
    ) -> Generator[Tuple[str, bytes], None, None]:
        """读取压缩包或文件夹中的所有图片

        Args:
            archive_path: 压缩包路径或文件夹路径

        Yields:
            Tuple[str, bytes]: (文件名, 图片数据)
        """
        image_files = self.get_image_files(archive_path)

        for filename in image_files:
            image_data = self.read_image(archive_path, filename)
            if image_data:
                yield filename, image_data

    def get_archive_info(self, archive_path: str) -> Dict[str, any]:
        """获取压缩包或文件夹信息

        Args:
            archive_path: 压缩包路径或文件夹路径

        Returns:
            Dict: 压缩包或文件夹信息
        """
        try:
            # 处理文件夹
            if os.path.isdir(archive_path):
                # 计算文件夹大小
                total_size = 0
                total_files = 0
                for root, dirs, files in os.walk(archive_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            total_size += os.path.getsize(file_path)
                            total_files += 1
                        except (OSError, IOError):
                            pass

                info = {
                    "path": archive_path,
                    "size": total_size,
                    "mtime": os.path.getmtime(archive_path),
                    "total_files": total_files,
                    "image_files": 0,
                    "image_list": [],
                }
            else:
                # 处理压缩包
                info = {
                    "path": archive_path,
                    "size": os.path.getsize(archive_path),
                    "mtime": os.path.getmtime(archive_path),
                    "total_files": 0,
                    "image_files": 0,
                    "image_list": [],
                }

                if archive_path.lower().endswith((".zip", ".cbz")):
                    with zipfile.ZipFile(archive_path, "r") as archive:
                        all_files = archive.namelist()
                        info["total_files"] = len(
                            [f for f in all_files if not f.endswith("/")]
                        )

                elif archive_path.lower().endswith((".rar", ".cbr")):
                    with rarfile.RarFile(archive_path, "r") as archive:
                        all_files = archive.namelist()
                        info["total_files"] = len(
                            [f for f in all_files if not f.endswith("/")]
                        )

            # 获取图片文件信息
            image_files = self.get_image_files(archive_path)
            info["image_files"] = len(image_files)
            info["image_list"] = image_files

            return info

        except Exception as e:
            logger.error(f"获取信息失败 {archive_path}: {e}")
            return {
                "path": archive_path,
                "size": 0,
                "mtime": 0,
                "total_files": 0,
                "image_files": 0,
                "image_list": [],
                "error": str(e),
            }

    def validate_image(self, image_data: bytes) -> bool:
        """验证图片数据是否有效

        Args:
            image_data: 图片数据

        Returns:
            bool: 是否有效
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                # 尝试获取图片基本信息
                _ = img.size
                _ = img.mode
                return True
        except Exception:
            return False


class ArchiveCache:
    """压缩包信息缓存"""

    def __init__(self):
        self._cache = {}

    def get_cache_key(self, archive_path: str, mtime: float) -> str:
        """生成缓存键"""
        return f"{archive_path}:{mtime}"

    def get(self, archive_path: str, mtime: float) -> Optional[Dict]:
        """获取缓存的压缩包信息"""
        key = self.get_cache_key(archive_path, mtime)
        return self._cache.get(key)

    def set(self, archive_path: str, mtime: float, info: Dict) -> None:
        """设置缓存的压缩包信息"""
        key = self.get_cache_key(archive_path, mtime)
        self._cache[key] = info

    def has(self, archive_path: str, mtime: float) -> bool:
        """检查是否存在缓存"""
        key = self.get_cache_key(archive_path, mtime)
        return key in self._cache

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def remove_old_entries(self, archive_path: str) -> None:
        """移除指定压缩包的旧缓存条目"""
        keys_to_remove = [
            key for key in self._cache.keys() if key.startswith(f"{archive_path}:")
        ]
        for key in keys_to_remove:
            del self._cache[key]
