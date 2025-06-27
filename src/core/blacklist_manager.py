# -*- coding: utf-8 -*-
"""
黑名单管理模块
负责管理需要排除的图片黑名单
"""

import os
from typing import Set, Dict, Any
from loguru import logger
from PIL import Image

from src.core.config_manager import ConfigManager
from src.utils.file_utils import is_supported_image
from .image_hash import ImageHasher
from .cache_manager import CacheManager


class BlacklistManager:
    """黑名单管理器"""

    def __init__(
        self,
        blacklist_folder: str,
        hasher: ImageHasher,
        config: ConfigManager,
        cache_manager: CacheManager,
    ):
        self.blacklist_folder = blacklist_folder
        self.config = config
        self.hasher = hasher
        self.cache_manager = cache_manager
        self.blacklist_hashes: Set[str] = set()
        self.load_blacklist()

    def load_blacklist(self) -> None:
        """从文件夹加载黑名单图片并生成哈希"""
        if os.path.exists(self.blacklist_folder) and os.path.isdir(
            self.blacklist_folder
        ):
            try:
                for filename in os.listdir(self.blacklist_folder):
                    file_path = os.path.join(self.blacklist_folder, filename)
                    file_mtime = os.path.getmtime(file_path)

                    # 检查缓存
                    cache_data = self.cache_manager.get_cache(
                        file_path, file_mtime, self.hasher.algorithm
                    )
                    if cache_data and "image_hash" in cache_data:
                        image_hash = cache_data["image_hash"]
                        self.blacklist_hashes.add(image_hash)
                        continue

                    # 检查是否为文件且为支持的图片格式
                    if os.path.isfile(file_path):
                        if is_supported_image(file_path):
                            try:
                                # 打开图片并计算哈希
                                with Image.open(file_path) as img:
                                    image_hash = self.hasher.calculate_hash(img)

                                    # 检查是否重复
                                    if image_hash in self.blacklist_hashes:
                                        logger.warning(f"黑名单图片重复: {filename}")
                                        continue

                                    # 添加到黑名单
                                    self.blacklist_hashes.add(image_hash)

                                    # 保存到缓存
                                    self.cache_manager.set_comic_cache(
                                        file_path,
                                        file_mtime,
                                        self.hasher.algorithm,
                                        {"image_hash": image_hash},
                                    )

                            except Exception as e:
                                logger.warning(f"处理黑名单图片失败 {filename}: {e}")
                        else:
                            logger.warning(
                                f"文件 {filename} 不在支持的图片格式列表中，已跳过"
                            )

                logger.info(f"黑名单加载成功: {len(self.blacklist_hashes)} 个项目")
            except Exception as e:
                logger.error(f"黑名单加载失败: {e}")
                self.blacklist_hashes = set()
        else:
            logger.info(f"黑名单文件夹不存在: {self.blacklist_folder}")
            # 创建黑名单文件夹
            try:
                os.makedirs(self.blacklist_folder, exist_ok=True)
                logger.info(f"已创建黑名单文件夹: {self.blacklist_folder}")
            except Exception as e:
                logger.error(f"创建黑名单文件夹失败: {e}")

    def get_all_hashes(self) -> Set[str]:
        """获取所有黑名单哈希值

        Returns:
            Set[str]: 哈希值集合
        """
        return self.blacklist_hashes.copy()

    def get_blacklist_count(self) -> int:
        """获取黑名单项目数量

        Returns:
            int: 项目数量
        """
        return len(self.blacklist_hashes)

    def clear_blacklist(self) -> None:
        """清空黑名单"""
        # 清空内存中的数据
        self.blacklist_hashes.clear()
        logger.info("黑名单已清空")

    def get_statistics(self) -> Dict[str, Any]:
        """获取黑名单统计信息

        Returns:
            Dict: 统计信息
        """
        # 统计文件夹中的实际图片文件数量
        folder_file_count = 0
        if os.path.exists(self.blacklist_folder) and os.path.isdir(
            self.blacklist_folder
        ):
            for filename in os.listdir(self.blacklist_folder):
                if os.path.isfile(os.path.join(self.blacklist_folder, filename)):
                    if is_supported_image(filename):
                        folder_file_count += 1

        return {
            "total_count": len(self.blacklist_hashes),
            "folder_path": self.blacklist_folder,
            "folder_file_count": folder_file_count,
        }
