# -*- coding: utf-8 -*-
"""
黑名单管理模块
负责管理需要排除的图片黑名单
"""

import os
import yaml
import shutil
from typing import Set, List, Dict, Any
from loguru import logger
from PIL import Image
from .image_hash import ImageHasher


class BlacklistManager:
    """黑名单管理器"""

    def __init__(self, blacklist_folder: str = "blacklist"):
        self.blacklist_folder = blacklist_folder
        self.blacklist_hashes: Set[str] = set()
        self.blacklist_info: Dict[str, Dict[str, Any]] = {}
        self.hasher = ImageHasher()
        self.load_blacklist()

    def load_blacklist(self) -> None:
        """从文件夹加载黑名单图片并生成哈希"""
        if os.path.exists(self.blacklist_folder) and os.path.isdir(
            self.blacklist_folder
        ):
            try:
                # 支持的图片格式
                supported_formats = {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp",
                    ".gif",
                    ".tiff",
                    ".webp",
                }

                for filename in os.listdir(self.blacklist_folder):
                    file_path = os.path.join(self.blacklist_folder, filename)

                    # 检查是否为文件且为支持的图片格式
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(filename.lower())
                        if ext in supported_formats:
                            try:
                                # 打开图片并计算哈希
                                with Image.open(file_path) as img:
                                    image_hash = self.hasher.calculate_hash(img)

                                    # 添加到黑名单
                                    self.blacklist_hashes.add(image_hash)

                                    # 保存详细信息
                                    self.blacklist_info[image_hash] = {
                                        "image_filename": filename,
                                        "file_path": file_path,
                                        "description": f"从黑名单文件夹加载: {filename}",
                                        "added_time": self._get_current_time(),
                                    }

                            except Exception as e:
                                logger.warning(f"处理黑名单图片失败 {filename}: {e}")
                                continue

                logger.info(f"黑名单加载成功: {len(self.blacklist_hashes)} 个项目")
            except Exception as e:
                logger.error(f"黑名单加载失败: {e}")
                self.blacklist_hashes = set()
                self.blacklist_info = {}
        else:
            logger.info(f"黑名单文件夹不存在: {self.blacklist_folder}")
            # 创建黑名单文件夹
            try:
                os.makedirs(self.blacklist_folder, exist_ok=True)
                logger.info(f"已创建黑名单文件夹: {self.blacklist_folder}")
            except Exception as e:
                logger.error(f"创建黑名单文件夹失败: {e}")

    def save_blacklist(self) -> None:
        """确保黑名单文件夹存在"""
        try:
            os.makedirs(self.blacklist_folder, exist_ok=True)
            logger.info(f"黑名单文件夹已确保存在: {self.blacklist_folder}")
        except Exception as e:
            logger.error(f"创建黑名单文件夹失败: {e}")

    def add_image_file(self, image_file_path: str, description: str = "") -> bool:
        """将图片文件添加到黑名单文件夹

        Args:
            image_file_path: 图片文件路径
            description: 描述信息

        Returns:
            bool: 是否成功添加
        """
        try:
            if not os.path.exists(image_file_path):
                logger.error(f"图片文件不存在: {image_file_path}")
                return False

            # 确保黑名单文件夹存在
            os.makedirs(self.blacklist_folder, exist_ok=True)

            # 计算图片哈希
            with Image.open(image_file_path) as img:
                image_hash = self.hasher.calculate_hash(img)

            if image_hash in self.blacklist_hashes:
                logger.warning(f"图片哈希已在黑名单中: {image_hash}")
                return False

            # 复制图片到黑名单文件夹
            filename = os.path.basename(image_file_path)
            target_path = os.path.join(self.blacklist_folder, filename)

            # 如果目标文件已存在，添加序号
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(target_path):
                new_filename = f"{base_name}_{counter}{ext}"
                target_path = os.path.join(self.blacklist_folder, new_filename)
                counter += 1

            shutil.copy2(image_file_path, target_path)

            # 添加到黑名单
            self.blacklist_hashes.add(image_hash)

            # 保存详细信息
            self.blacklist_info[image_hash] = {
                "image_filename": os.path.basename(target_path),
                "file_path": target_path,
                "original_path": image_file_path,
                "description": description or f"从文件添加: {filename}",
                "added_time": self._get_current_time(),
            }

            logger.info(f"图片已添加到黑名单: {os.path.basename(target_path)}")
            return True

        except Exception as e:
            logger.error(f"添加图片文件到黑名单失败: {e}")
            return False

    def add_image(
        self,
        image_hash: str,
        archive_path: str = "",
        image_filename: str = "",
        description: str = "",
    ) -> bool:
        """添加图片哈希到黑名单（兼容性方法）

        Args:
            image_hash: 图片哈希值
            archive_path: 压缩包路径
            image_filename: 图片文件名
            description: 描述信息

        Returns:
            bool: 是否成功添加
        """
        try:
            if image_hash in self.blacklist_hashes:
                logger.warning(f"图片哈希已在黑名单中: {image_hash}")
                return False

            self.blacklist_hashes.add(image_hash)

            # 保存详细信息
            self.blacklist_info[image_hash] = {
                "archive_path": archive_path,
                "image_filename": image_filename,
                "description": description,
                "added_time": self._get_current_time(),
            }

            logger.info(f"图片哈希已添加到黑名单: {image_filename}")
            return True

        except Exception as e:
            logger.error(f"添加图片到黑名单失败: {e}")
            return False

    def remove_image(self, image_hash: str) -> bool:
        """从黑名单中移除图片

        Args:
            image_hash: 图片哈希值

        Returns:
            bool: 是否成功移除
        """
        try:
            if image_hash not in self.blacklist_hashes:
                logger.warning(f"图片哈希不在黑名单中: {image_hash}")
                return False

            # 获取图片信息
            image_info = self.blacklist_info.get(image_hash, {})
            file_path = image_info.get("file_path")

            # 如果有对应的文件路径，尝试删除文件
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"已删除黑名单图片文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除黑名单图片文件失败: {e}")

            # 从内存中移除
            self.blacklist_hashes.remove(image_hash)

            # 移除详细信息
            if image_hash in self.blacklist_info:
                del self.blacklist_info[image_hash]

            logger.info(f"图片已从黑名单移除: {image_hash}")
            return True

        except Exception as e:
            logger.error(f"从黑名单移除图片失败: {e}")
            return False

    def get_blacklist_info(self, image_hash: str) -> Dict[str, Any]:
        """获取黑名单图片的详细信息

        Args:
            image_hash: 图片哈希值

        Returns:
            Dict: 详细信息
        """
        return self.blacklist_info.get(image_hash, {})

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
        try:
            # 删除黑名单文件夹中的所有图片文件
            if os.path.exists(self.blacklist_folder) and os.path.isdir(
                self.blacklist_folder
            ):
                for filename in os.listdir(self.blacklist_folder):
                    file_path = os.path.join(self.blacklist_folder, filename)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                            logger.debug(f"已删除黑名单文件: {filename}")
                        except Exception as e:
                            logger.warning(f"删除黑名单文件失败 {filename}: {e}")

            # 清空内存中的数据
            self.blacklist_hashes.clear()
            self.blacklist_info.clear()
            logger.info("黑名单已清空")

        except Exception as e:
            logger.error(f"清空黑名单失败: {e}")

    def export_blacklist(self, export_file: str) -> bool:
        """导出黑名单到文件

        Args:
            export_file: 导出文件路径

        Returns:
            bool: 是否成功导出
        """
        try:
            data = {
                "hashes": list(self.blacklist_hashes),
                "info": self.blacklist_info,
                "export_time": self._get_current_time(),
                "count": len(self.blacklist_hashes),
            }

            with open(export_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"黑名单导出成功: {export_file}")
            return True

        except Exception as e:
            logger.error(f"黑名单导出失败: {e}")
            return False

    def import_blacklist(self, import_file: str, merge: bool = True) -> bool:
        """从文件导入黑名单

        Args:
            import_file: 导入文件路径
            merge: 是否与现有黑名单合并

        Returns:
            bool: 是否成功导入
        """
        try:
            if not os.path.exists(import_file):
                logger.error(f"导入文件不存在: {import_file}")
                return False

            with open(import_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            imported_hashes = set(data.get("hashes", []))
            imported_info = data.get("info", {})

            if not merge:
                # 不合并，直接替换
                self.blacklist_hashes = imported_hashes
                self.blacklist_info = imported_info
            else:
                # 合并
                self.blacklist_hashes.update(imported_hashes)
                self.blacklist_info.update(imported_info)

            logger.info(f"黑名单导入成功: {len(imported_hashes)} 个项目")
            return True

        except Exception as e:
            logger.error(f"黑名单导入失败: {e}")
            return False

    def filter_similar_hashes(
        self, hash_list: List[str], hasher: ImageHasher, threshold: int = 5
    ) -> List[str]:
        """过滤与黑名单相似的哈希值

        Args:
            hash_list: 要过滤的哈希值列表
            hasher: 图片哈希计算器
            threshold: 相似度阈值

        Returns:
            List[str]: 过滤后的哈希值列表
        """
        filtered_hashes = []

        for hash_value in hash_list:
            is_similar_to_blacklist = False

            for blacklist_hash in self.blacklist_hashes:
                if hasher.is_similar(hash_value, blacklist_hash, threshold):
                    is_similar_to_blacklist = True
                    break

            if not is_similar_to_blacklist:
                filtered_hashes.append(hash_value)

        return filtered_hashes

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
            supported_formats = {
                ".jpg",
                ".jpeg",
                ".png",
                ".bmp",
                ".gif",
                ".tiff",
                ".webp",
            }
            for filename in os.listdir(self.blacklist_folder):
                if os.path.isfile(os.path.join(self.blacklist_folder, filename)):
                    _, ext = os.path.splitext(filename.lower())
                    if ext in supported_formats:
                        folder_file_count += 1

        return {
            "total_count": len(self.blacklist_hashes),
            "folder_path": self.blacklist_folder,
            "folder_file_count": folder_file_count,
            "has_info": len(self.blacklist_info),
            "archives": list(
                set(
                    info.get("archive_path", "")
                    for info in self.blacklist_info.values()
                    if info.get("archive_path")
                )
            ),
            "file_paths": list(
                set(
                    info.get("file_path", "")
                    for info in self.blacklist_info.values()
                    if info.get("file_path")
                )
            ),
        }

    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
