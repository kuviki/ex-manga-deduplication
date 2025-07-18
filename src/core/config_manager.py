# -*- coding: utf-8 -*-
"""
配置管理器
负责管理应用程序的所有配置参数
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from loguru import logger
from enum import Enum


class HashAlgorithm(Enum):
    """图片哈希算法枚举"""

    AVERAGE = "average"
    PERCEPTUAL = "perceptual"
    DIFFERENCE = "difference"
    WAVELET = "wavelet"


class ErrorHandling(Enum):
    """错误处理方式枚举"""

    ASK = "ask"
    SKIP = "skip"
    ABORT = "abort"


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config = self._load_default_config()
        self.load_config()

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            # 图片哈希设置
            "hash_algorithm": HashAlgorithm.PERCEPTUAL.value,
            "similarity_thresholds": {
                HashAlgorithm.AVERAGE.value: 5,
                HashAlgorithm.PERCEPTUAL.value: 5,
                HashAlgorithm.DIFFERENCE.value: 5,
                HashAlgorithm.WAVELET.value: 5,
            },
            # 重复检测设置
            "min_similar_images": 5,
            "min_image_resolution": {"width": 100, "height": 100},
            "comic_image_count_range": {
                "min": 1,
                "max": None,
            },  # 参与去重的漫画图片数量范围，max为None表示无限制
            # 应用程序设置
            "comic_viewer_path": "",
            "error_handling": ErrorHandling.SKIP.value,
            # 扫描设置
            "max_workers": 4,
            # 缓存设置
            "enable_cache": True,
            "cache_dir": "cache",
            # 界面设置
            "window_geometry": {"width": 1200, "height": 800},
            "preview_size": {"width": 200, "height": 200},
            # 黑名单设置
            "blacklist_folder": "blacklist",
            # 上次扫描目录
            "last_scanned_directory": "",
            # 已检查漫画路径
            "checked_comic_paths": [],
            # 筛选设置
            "filter_settings": {
                "created_time_enabled": False,
                "created_after": None,
                "created_before": None,
                "modified_time_enabled": False,
                "modified_after": None,
                "modified_before": None,
                "name_filter_enabled": False,
                "name_filter_regex": "",
            },
        }

    def load_config(self) -> None:
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}
                    self.config.update(file_config)
                logger.info(f"配置文件加载成功: {self.config_file}")
            except Exception as e:
                logger.error(f"配置文件加载失败: {e}")
        else:
            logger.info("配置文件不存在，使用默认配置")
            self.save_config()

    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(self.config_file) or ".", exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"配置文件保存成功: {self.config_file}")
        except Exception as e:
            logger.error(f"配置文件保存失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_hash_algorithm(self) -> HashAlgorithm:
        """获取当前哈希算法"""
        algo_str = self.get("hash_algorithm", HashAlgorithm.PERCEPTUAL.value)
        try:
            return HashAlgorithm(algo_str)
        except ValueError:
            logger.warning(f"未知的哈希算法: {algo_str}，使用默认算法")
            return HashAlgorithm.PERCEPTUAL

    def get_similarity_threshold(
        self, algorithm: Optional[HashAlgorithm] = None
    ) -> int:
        """获取相似度阈值"""
        if algorithm is None:
            algorithm = self.get_hash_algorithm()

        return self.get(f"similarity_thresholds.{algorithm.value}", 5)

    def get_error_handling(self) -> ErrorHandling:
        """获取错误处理方式"""
        handling_str = self.get("error_handling", ErrorHandling.SKIP.value)
        try:
            return ErrorHandling(handling_str)
        except ValueError:
            logger.warning(f"未知的错误处理方式: {handling_str}，使用默认方式")
            return ErrorHandling.SKIP

    def get_min_similar_images(self) -> int:
        """获取最小相似图片数量"""
        return self.get("min_similar_images", 3)

    def get_min_image_resolution(self) -> tuple:
        """获取最小图片分辨率"""
        resolution = self.get("min_image_resolution", {"width": 100, "height": 100})
        return resolution.get("width", 100), resolution.get("height", 100)

    def is_cache_enabled(self) -> bool:
        """是否启用缓存"""
        return self.get("enable_cache", True)

    def get_cache_dir(self) -> str:
        """获取缓存目录"""
        return self.get("cache_dir", "cache")

    def get_comic_viewer_path(self) -> str:
        """获取漫画查看器路径"""
        return self.get("comic_viewer_path", "")

    def get_max_workers(self) -> int:
        """获取最大工作线程数"""
        return self.get("max_workers", 4)

    def get_window_geometry(self) -> tuple:
        """获取窗口几何信息"""
        geometry = self.get("window_geometry", {"width": 1200, "height": 800})
        return geometry.get("width", 1200), geometry.get("height", 800)

    def get_preview_size(self) -> tuple:
        """获取预览图片大小"""
        size = self.get("preview_size", {"width": 200, "height": 200})
        return size.get("width", 200), size.get("height", 200)

    def get_checked_comic_paths(self) -> List[str]:
        """获取已检查漫画路径列表"""
        return self.get("checked_comic_paths", [])

    def set_checked_comic_paths(self, paths: List[str]):
        """设置已检查漫画路径列表"""
        self.set("checked_comic_paths", paths)

    def get_blacklist_folder(self) -> str:
        """获取黑名单文件路径"""
        return self.get("blacklist_folder", "blacklist")

    def get_comic_image_count_range(self) -> tuple:
        """获取参与去重的漫画图片数量范围"""
        range_config = self.get("comic_image_count_range", {"min": 1, "max": None})
        min_count = range_config.get("min", 1)
        max_count = range_config.get("max", None)
        return min_count, max_count

    def get_filter_settings(self) -> Dict[str, Any]:
        """获取筛选设置"""
        return self.get("filter_settings", {
            "created_time_enabled": False,
            "created_after": None,
            "created_before": None,
            "modified_time_enabled": False,
            "modified_after": None,
            "modified_before": None,
            "name_filter_enabled": False,
            "name_filter_regex": "",
        })

    def set_filter_settings(self, settings: Dict[str, Any]):
        """设置筛选设置"""
        self.set("filter_settings", settings)
