# -*- coding: utf-8 -*-
"""
缓存管理模块
负责管理扫描结果的缓存，提高重复扫描的效率
"""

import os
import pickle
import hashlib
from typing import Dict, List, Tuple, Any, Optional
from loguru import logger
from numpy.typing import NDArray
from .config_manager import HashAlgorithm


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
        self._memory_cache = {}  # 内存缓存

    def _ensure_cache_dir(self) -> None:
        """确保缓存目录存在"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"创建缓存目录失败: {e}")

    def get_cache_key(
        self, file_path: str, mtime: float, algorithm: HashAlgorithm
    ) -> str:
        """生成缓存键

        Args:
            file_path: 文件路径
            mtime: 修改时间
            algorithm: 哈希算法

        Returns:
            str: 缓存键
        """
        # 使用文件路径、修改时间和算法生成唯一键
        key_string = f"{file_path}:{mtime}:{algorithm.value}"
        return hashlib.md5(key_string.encode("utf-8")).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.cache")

    def get_comic_cache(
        self, file_path: str, mtime: float, algorithm: HashAlgorithm
    ) -> Optional[List[Tuple[str, str, NDArray]]]:
        """获取漫画文件的缓存数据

        Args:
            file_path: 漫画文件路径
            mtime: 文件修改时间
            algorithm: 哈希算法

        Returns:
            Optional[Dict]: 缓存数据，如果不存在则返回None
        """
        try:
            cache_key = self.get_cache_key(file_path, mtime, algorithm)

            # 先检查内存缓存
            if cache_key in self._memory_cache:
                logger.debug(f"从内存缓存获取数据: {file_path}")
                return self._memory_cache[cache_key]

            # 检查文件缓存
            cache_file = self._get_cache_file_path(cache_key)
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    cache_data = pickle.load(f)

                # 验证缓存数据
                if self._validate_cache_data(cache_data, file_path, mtime, algorithm):
                    # 加载到内存缓存
                    self._memory_cache[cache_key] = cache_data["data"]
                    logger.debug(f"从文件缓存获取数据: {file_path}")
                    return cache_data["data"]
                else:
                    # 缓存数据无效，删除文件
                    os.remove(cache_file)
                    logger.warning(f"缓存数据无效，已删除: {cache_file}")

            return None

        except Exception as e:
            logger.error(f"获取缓存数据失败: {e}")
            return None

    def set_comic_cache(
        self,
        file_path: str,
        mtime: float,
        algorithm: HashAlgorithm,
        data: List[Tuple[str, str, NDArray]],
    ) -> bool:
        """设置漫画文件的缓存数据

        Args:
            file_path: 漫画文件路径
            mtime: 文件修改时间
            algorithm: 哈希算法
            data: 要缓存的数据

        Returns:
            bool: 是否成功设置缓存
        """
        try:
            cache_key = self.get_cache_key(file_path, mtime, algorithm)

            # 准备缓存数据
            cache_data = {
                "file_path": file_path,
                "mtime": mtime,
                "algorithm": algorithm.value,
                "data": data,
                "cache_version": "1.0",
            }

            # 保存到内存缓存
            self._memory_cache[cache_key] = data

            # 保存到文件缓存
            cache_file = self._get_cache_file_path(cache_key)
            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.debug(f"缓存数据已保存: {file_path}")
            return True

        except Exception as e:
            logger.error(f"保存缓存数据失败: {e}")
            return False

    def _validate_cache_data(
        self,
        cache_data: Dict[str, Any],
        file_path: str,
        mtime: float,
        algorithm: HashAlgorithm,
    ) -> bool:
        """验证缓存数据的有效性

        Args:
            cache_data: 缓存数据
            file_path: 文件路径
            mtime: 修改时间
            algorithm: 哈希算法

        Returns:
            bool: 是否有效
        """
        try:
            # 检查必要字段
            required_fields = ["file_path", "mtime", "algorithm", "data"]
            if not all(field in cache_data for field in required_fields):
                return False

            # 检查文件路径
            if cache_data["file_path"] != file_path:
                return False

            # 检查修改时间
            if abs(cache_data["mtime"] - mtime) > 1:  # 允许1秒误差
                return False

            # 检查算法
            if cache_data["algorithm"] != algorithm.value:
                return False

            # 检查数据结构
            data = cache_data["data"]
            if not isinstance(data, dict):
                return False

            if "image_hashes" not in data:
                return False

            return True

        except Exception as e:
            logger.error(f"验证缓存数据失败: {e}")
            return False

    def clear_cache(self) -> bool:
        """清空所有缓存

        Returns:
            bool: 是否成功清空
        """
        try:
            # 清空内存缓存
            self._memory_cache.clear()

            # 清空文件缓存
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(".cache"):
                        file_path = os.path.join(self.cache_dir, filename)
                        os.remove(file_path)

            logger.info("缓存已清空")
            return True

        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return False

    def remove_cache(self, file_path: str) -> bool:
        """移除指定文件的所有缓存

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否成功移除
        """
        try:
            removed_count = 0

            # 从内存缓存中移除
            for key in self._memory_cache.keys():
                # 这里需要反向查找，比较复杂，暂时跳过内存缓存的精确移除
                pass

            # 从文件缓存中移除
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(".cache"):
                        cache_file = os.path.join(self.cache_dir, filename)
                        try:
                            with open(cache_file, "rb") as f:
                                cache_data = pickle.load(f)

                            if cache_data.get("file_path") == file_path:
                                os.remove(cache_file)
                                removed_count += 1

                        except Exception:
                            # 如果读取失败，可能是损坏的缓存文件，直接删除
                            os.remove(cache_file)
                            removed_count += 1

            if removed_count > 0:
                logger.info(f"已移除 {removed_count} 个缓存文件: {file_path}")

            return True

        except Exception as e:
            logger.error(f"移除缓存失败: {e}")
            return False

    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            Dict: 统计信息
        """
        try:
            stats = {
                "memory_cache_count": len(self._memory_cache),
                "file_cache_count": 0,
                "total_cache_size": 0,
                "cache_dir": self.cache_dir,
            }

            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(".cache"):
                        stats["file_cache_count"] += 1
                        file_path = os.path.join(self.cache_dir, filename)
                        stats["total_cache_size"] += os.path.getsize(file_path)

            return stats

        except Exception as e:
            logger.error(f"获取缓存统计信息失败: {e}")
            return {
                "memory_cache_count": 0,
                "file_cache_count": 0,
                "total_cache_size": 0,
                "cache_dir": self.cache_dir,
                "error": str(e),
            }

    def cleanup_old_cache(self, max_age_days: int = 30) -> int:
        """清理过期的缓存文件

        Args:
            max_age_days: 最大保留天数

        Returns:
            int: 清理的文件数量
        """
        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            removed_count = 0

            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(".cache"):
                        file_path = os.path.join(self.cache_dir, filename)
                        file_mtime = os.path.getmtime(file_path)

                        if current_time - file_mtime > max_age_seconds:
                            os.remove(file_path)
                            removed_count += 1

            if removed_count > 0:
                logger.info(f"已清理 {removed_count} 个过期缓存文件")

            return removed_count

        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0
