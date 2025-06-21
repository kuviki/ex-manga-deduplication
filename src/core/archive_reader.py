# -*- coding: utf-8 -*-
"""
压缩包读取模块
负责读取和解析漫画压缩包（ZIP、RAR）
"""

import os
import zipfile
import rarfile
from typing import List, Dict, Generator, Tuple, Optional
from io import BytesIO
from loguru import logger
from PIL import Image
from ..utils.file_utils import natural_sort_key


class ArchiveReader:
    """压缩包读取器"""

    def __init__(self, supported_image_formats: List[str] = None):
        if supported_image_formats is None:
            supported_image_formats = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]

        self.supported_image_formats = [fmt.lower() for fmt in supported_image_formats]

        # 设置RAR工具路径（如果需要）
        # rarfile.UNRAR_TOOL = "path/to/unrar.exe"  # Windows

    def is_supported_archive(self, file_path: str) -> bool:
        """检查是否为支持的压缩包格式

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否支持
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in [".zip", ".rar", ".cbr", ".cbz"]

    def is_image_file(self, filename: str) -> bool:
        """检查是否为图片文件

        Args:
            filename: 文件名

        Returns:
            bool: 是否为图片文件
        """
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_image_formats

    def get_image_files(self, archive_path: str) -> List[str]:
        """获取压缩包中的所有图片文件列表

        Args:
            archive_path: 压缩包路径

        Returns:
            List[str]: 图片文件名列表（按自然排序）
        """
        try:
            image_files = []

            if archive_path.lower().endswith((".zip", ".cbz")):
                with zipfile.ZipFile(archive_path, "r") as archive:
                    for filename in archive.namelist():
                        if self.is_image_file(filename) and not filename.endswith("/"):
                            image_files.append(filename)

            elif archive_path.lower().endswith((".rar", ".cbr")):
                with rarfile.RarFile(archive_path, "r") as archive:
                    for filename in archive.namelist():
                        if self.is_image_file(filename) and not filename.endswith("/"):
                            image_files.append(filename)

            # 自然排序
            image_files.sort(key=natural_sort_key)
            return image_files

        except Exception as e:
            logger.error(f"获取压缩包图片列表失败 {archive_path}: {e}")
            return []

    def read_image(self, archive_path: str, image_filename: str) -> Optional[bytes]:
        """从压缩包中读取指定图片

        Args:
            archive_path: 压缩包路径
            image_filename: 图片文件名

        Returns:
            Optional[bytes]: 图片数据，失败时返回None
        """
        try:
            if archive_path.lower().endswith((".zip", ".cbz")):
                with zipfile.ZipFile(archive_path, "r") as archive:
                    return archive.read(image_filename)

            elif archive_path.lower().endswith((".rar", ".cbr")):
                with rarfile.RarFile(archive_path, "r") as archive:
                    return archive.read(image_filename)

            return None

        except Exception as e:
            logger.error(f"读取压缩包图片失败 {archive_path}/{image_filename}: {e}")
            return None

    def read_all_images(
        self, archive_path: str
    ) -> Generator[Tuple[str, bytes], None, None]:
        """读取压缩包中的所有图片

        Args:
            archive_path: 压缩包路径

        Yields:
            Tuple[str, bytes]: (文件名, 图片数据)
        """
        image_files = self.get_image_files(archive_path)

        for filename in image_files:
            image_data = self.read_image(archive_path, filename)
            if image_data:
                yield filename, image_data

    def get_archive_info(self, archive_path: str) -> Dict[str, any]:
        """获取压缩包信息

        Args:
            archive_path: 压缩包路径

        Returns:
            Dict: 压缩包信息
        """
        try:
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
            logger.error(f"获取压缩包信息失败 {archive_path}: {e}")
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
