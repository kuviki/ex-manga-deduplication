# -*- coding: utf-8 -*-
"""
图片哈希处理模块
负责计算和比较图片的哈希值
"""

import imagehash
from PIL import Image
import numpy as np
from typing import Union, Tuple
from loguru import logger
from .config_manager import HashAlgorithm


class ImageHasher:
    """图片哈希计算器"""

    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.PERCEPTUAL):
        self.algorithm = algorithm
        self._hash_functions = {
            HashAlgorithm.AVERAGE: imagehash.average_hash,
            HashAlgorithm.PERCEPTUAL: imagehash.phash,
            HashAlgorithm.DIFFERENCE: imagehash.dhash,
            HashAlgorithm.WAVELET: imagehash.whash,
        }

    def calculate_hash(self, image: Union[Image.Image, np.ndarray, bytes]) -> str:
        """计算图片哈希值

        Args:
            image: PIL Image对象、numpy数组或字节数据

        Returns:
            str: 哈希值的十六进制字符串
        """
        try:
            # 转换为PIL Image
            if isinstance(image, bytes):
                from io import BytesIO

                image = Image.open(BytesIO(image))
            elif isinstance(image, np.ndarray):
                image = Image.fromarray(image)
            elif not isinstance(image, Image.Image):
                raise ValueError(f"不支持的图片类型: {type(image)}")

            # 处理GIF动图，取第一帧
            if hasattr(image, "is_animated") and image.is_animated:
                image.seek(0)  # 跳转到第一帧
                image = image.copy()  # 复制当前帧

            # 转换为RGB模式（如果需要）
            if image.mode not in ("RGB", "L"):
                if image.mode == "RGBA":
                    # 创建白色背景
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    background.paste(
                        image, mask=image.split()[-1]
                    )  # 使用alpha通道作为mask
                    image = background
                else:
                    image = image.convert("RGB")

            # 计算哈希
            hash_func = self._hash_functions[self.algorithm]
            hash_value = hash_func(image)

            return str(hash_value)

        except Exception as e:
            logger.error(f"计算图片哈希失败: {e}")
            raise

    def calculate_similarity(self, hash1: str, hash2: str) -> int:
        """计算两个哈希值的相似度（汉明距离）

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值

        Returns:
            int: 汉明距离（0表示完全相同）
        """
        try:
            # 将字符串转换为imagehash对象
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)

            # 计算汉明距离
            return h1 - h2

        except Exception as e:
            logger.error(f"计算哈希相似度失败: {e}")
            return float("inf")  # 返回无穷大表示完全不相似

    def is_similar(self, hash1: str, hash2: str, threshold: int = 5) -> bool:
        """判断两个哈希值是否相似

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值
            threshold: 相似度阈值

        Returns:
            bool: 是否相似
        """
        distance = self.calculate_similarity(hash1, hash2)
        return distance <= threshold

    def get_image_info(self, image: Union[Image.Image, bytes]) -> Tuple[int, int, str]:
        """获取图片基本信息

        Args:
            image: PIL Image对象或字节数据

        Returns:
            Tuple[int, int, str]: (宽度, 高度, 格式)
        """
        try:
            if isinstance(image, bytes):
                from io import BytesIO

                image = Image.open(BytesIO(image))

            return image.width, image.height, image.format or "UNKNOWN"

        except Exception as e:
            logger.error(f"获取图片信息失败: {e}")
            return 0, 0, "UNKNOWN"

    def is_valid_image_size(
        self,
        image: Union[Image.Image, bytes],
        min_width: int = 100,
        min_height: int = 100,
    ) -> bool:
        """检查图片尺寸是否符合要求

        Args:
            image: PIL Image对象或字节数据
            min_width: 最小宽度
            min_height: 最小高度

        Returns:
            bool: 是否符合尺寸要求
        """
        width, height, _ = self.get_image_info(image)
        return width >= min_width and height >= min_height


class ImageHashCache:
    """图片哈希缓存"""

    def __init__(self):
        self._cache = {}

    def get(self, key: str) -> str:
        """获取缓存的哈希值"""
        return self._cache.get(key)

    def set(self, key: str, hash_value: str) -> None:
        """设置缓存的哈希值"""
        self._cache[key] = hash_value

    def has(self, key: str) -> bool:
        """检查是否存在缓存"""
        return key in self._cache

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)
