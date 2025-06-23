# -*- coding: utf-8 -*-
"""
漫画扫描器模块
负责扫描目录中的漫画文件并检测重复
"""

import os
import time
import pickle
import numpy as np
import imagehash
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from loguru import logger
from PyQt5.QtCore import QObject, pyqtSignal
from numpy.typing import NDArray

from .config_manager import ConfigManager
from .archive_reader import ArchiveReader
from .image_hash import ImageHasher
from .blacklist_manager import BlacklistManager
from .cache_manager import CacheManager


@dataclass
class ScanProgress:
    """扫描进度信息"""

    current_file: str = ""
    processed_files: int = 0
    total_files: int = 0
    duplicates_found: int = 0
    errors: int = 0
    elapsed_time: float = 0.0
    start_time: float = 0.0
    stage: str = "scanning"  # "scanning" or "processing"
    history: Optional[List[List[Tuple[float, int]]]] = (
        None  # 用于存储 (timestamp, processed_files) 对
    )

    @property
    def file_progress(self) -> float:
        """文件处理进度百分比"""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100


@dataclass
class ComicInfo:
    """漫画信息"""

    path: str
    size: int
    mtime: float
    image_hashes: List[
        Tuple[str, str, NDArray[np.uint8]]
    ]  # filename, hash_hex, hash_array
    cache_key: str  # 缓存键
    error: Optional[str] = None
    checked: bool = False  # 是否已检查标记


@dataclass
class DuplicateGroup:
    """重复漫画组"""

    comics: List[ComicInfo]
    similar_hash_groups: List[Tuple[str, str, int]]  # (hash1, hash2, similarity)
    similarity_count: int


class Scanner(QObject):
    """漫画扫描器"""

    # 信号定义
    progress_updated = pyqtSignal(ScanProgress)
    scan_completed = pyqtSignal(list)  # List[DuplicateGroup]
    scan_error = pyqtSignal(str)
    scan_paused = pyqtSignal()
    scan_resumed = pyqtSignal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config = config_manager
        self.archive_reader = ArchiveReader(self.config.get_supported_image_formats())
        self.image_hasher = ImageHasher(self.config.get_hash_algorithm())
        self.blacklist_manager = BlacklistManager(self.config.get_blacklist_folder())
        self.cache_manager = CacheManager(self.config.get_cache_dir())

        self.is_scanning = False
        self.is_paused = False
        self.should_stop = False

        self.progress = ScanProgress()

    def scan_directory(self, directory: str) -> None:
        """扫描目录中的漫画文件

        Args:
            directory: 要扫描的目录路径
        """
        if self.is_scanning:
            logger.warning("扫描已在进行中")
            return

        try:
            self.is_scanning = True
            self.is_paused = False
            self.should_stop = False

            logger.info(f"开始扫描目录: {directory}")

            # 查找所有漫画文件
            comic_files = self._find_comic_files(directory)
            if not comic_files:
                self.scan_error.emit("未找到支持的漫画文件")
                return

            self.progress = ScanProgress(total_files=len(comic_files))
            self.progress_updated.emit(self.progress)
            self.progress.start_time = time.time()

            # 扫描漫画文件
            comic_infos = self._process_comic_files(comic_files)

            if self.should_stop:
                logger.info("扫描已停止")
                return

            # 检测重复漫画
            duplicate_groups = self._detect_duplicates(comic_infos)

            self.progress.duplicates_found = len(duplicate_groups)
            self.progress.elapsed_time = time.time() - self.progress.start_time
            self.progress_updated.emit(self.progress)

            logger.info(f"扫描完成，找到 {len(duplicate_groups)} 组重复漫画")
            self.scan_completed.emit(duplicate_groups)

        except Exception as e:
            logger.error(f"扫描过程中发生错误: {e}")
            self.scan_error.emit(str(e))
        finally:
            self.is_scanning = False

    def pause_scan(self) -> None:
        """暂停扫描"""
        if self.is_scanning and not self.is_paused:
            self.is_paused = True
            logger.info("扫描已暂停")
            self.scan_paused.emit()

    def resume_scan(self) -> None:
        """恢复扫描"""
        if self.is_scanning and self.is_paused:
            self.is_paused = False
            if self.progress.stage == "scanning":
                logger.info("扫描已恢复")
            elif self.progress.stage == "processing":
                logger.info("处理已恢复")
            self.scan_resumed.emit()

    def stop_scan(self) -> None:
        """停止扫描"""
        if self.is_scanning:
            self.should_stop = True
            if self.progress.stage == "scanning":
                logger.info("正在停止扫描...")
            elif self.progress.stage == "processing":
                logger.info("正在停止处理...")

    def _find_comic_files(self, directory: str) -> List[str]:
        """查找目录中的所有漫画文件"""
        comic_files = []
        supported_formats = self.config.get_supported_formats()

        for root, _dirs, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(fmt) for fmt in supported_formats):
                    comic_files.append(os.path.join(root, file))

        logger.info(f"找到 {len(comic_files)} 个漫画文件")
        return comic_files

    def _process_comic_files(self, comic_files: List[str]) -> List[ComicInfo]:
        """处理漫画文件，提取图片哈希"""
        comic_infos = []
        max_workers = self.config.get_max_workers()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_file = {
                executor.submit(self._process_single_comic, file): file
                for file in comic_files
            }

            # 处理结果
            for future in as_completed(future_to_file):
                if self.should_stop:
                    executor.shutdown(wait=True, cancel_futures=True)
                    break

                file_path = future_to_file[future]
                try:
                    comic_info = future.result()
                    if comic_info:
                        comic_infos.append(comic_info)

                    self.progress.processed_files += 1
                    self.progress.current_file = os.path.basename(file_path)
                    self.progress.elapsed_time = time.time() - self.progress.start_time
                    self.progress_updated.emit(self.progress)

                except Exception as e:
                    logger.error(f"处理漫画文件失败 {file_path}: {e}")
                    self.progress.errors += 1

        return comic_infos

    def _persist_cache_keys(self, similar_comic_cache_dict: dict):
        """持久化缓存键"""
        try:
            with open("index.db", "wb") as f:
                pickle.dump(
                    similar_comic_cache_dict,
                    f,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
        except Exception as e:
            logger.error(f"更新缓存 index.db 失败: {e}")

    def _process_single_comic(self, file_path: str) -> Optional[ComicInfo]:
        """处理单个漫画文件"""
        try:
            # 获取文件信息
            file_stat = os.stat(file_path)
            mtime = file_stat.st_mtime
            size = file_stat.st_size

            # 检查缓存
            if self.config.is_cache_enabled():
                cached_info = self.cache_manager.get_comic_cache(
                    file_path, mtime, self.config.get_hash_algorithm()
                )
                if cached_info:
                    logger.debug(f"使用缓存数据: {file_path}")
                    return ComicInfo(
                        path=file_path,
                        size=size,
                        mtime=mtime,
                        image_hashes=cached_info["image_hashes"],
                        cache_key=self.cache_manager.get_cache_key(
                            file_path, mtime, self.config.get_hash_algorithm()
                        ),
                    )

            # 处理压缩包
            image_hashes = []
            min_width, min_height = self.config.get_min_image_resolution()

            for filename, image_data in self.archive_reader.read_all_images(file_path):
                # 等待暂停
                while self.is_paused and not self.should_stop:
                    time.sleep(0.1)

                if self.should_stop:
                    return None

                # 验证图片
                if not self.archive_reader.validate_image(image_data):
                    continue

                # 检查图片尺寸
                if not self.image_hasher.is_valid_image_size(
                    image_data, min_width, min_height
                ):
                    continue

                # 计算哈希
                try:
                    image_hash = self.image_hasher.calculate_hash(image_data)
                    hash_array = imagehash.hex_to_hash(image_hash).hash.flatten()
                    image_hashes.append((filename, image_hash, hash_array))

                except Exception as e:
                    logger.warning(f"计算图片哈希失败 {file_path}/{filename}: {e}")
                    continue

            comic_info = ComicInfo(
                path=file_path,
                size=size,
                mtime=mtime,
                image_hashes=image_hashes,
                cache_key=self.cache_manager.get_cache_key(
                    file_path, mtime, self.config.get_hash_algorithm()
                ),
            )

            # 保存到缓存
            if not self.should_stop and self.config.is_cache_enabled():
                self.cache_manager.set_comic_cache(
                    file_path,
                    mtime,
                    self.config.get_hash_algorithm(),
                    {"image_count": len(image_hashes), "image_hashes": image_hashes},
                )

            return comic_info

        except Exception as e:
            logger.error(f"处理漫画文件失败 {file_path}: {e}")
            return None

    def _detect_duplicates(self, comic_infos: List[ComicInfo]) -> List[DuplicateGroup]:
        """检测重复漫画 - 使用numpy优化的高性能实现"""
        duplicate_groups = []
        processed_comic_indices = set()

        similarity_threshold = self.config.get_similarity_threshold()
        min_similar_images = self.config.get_min_similar_images()
        min_image_count, max_image_count = self.config.get_comic_image_count_range()

        # 加载缓存
        try:
            with open("index.db", "rb") as f:
                similar_comic_cache_dict: Dict[str, NDArray[np.int64]] = pickle.load(f)
        except Exception:
            similar_comic_cache_dict = dict()

        # 过滤有效的漫画（包括图片数量范围过滤）
        valid_comics: List[ComicInfo] = []
        filtered_count = 0
        for comic in comic_infos:
            if comic.error or not comic.image_hashes:
                continue

            image_count = len(comic.image_hashes)
            # 检查图片数量是否在配置范围内
            if image_count < min_image_count:
                filtered_count += 1
                continue
            if max_image_count is not None and image_count > max_image_count:
                filtered_count += 1
                continue

            valid_comics.append(comic)

        if filtered_count > 0:
            logger.info(f"根据图片数量范围配置过滤了 {filtered_count} 个漫画文件")
        if len(valid_comics) < 2:
            return duplicate_groups

        logger.info(f"开始检测 {len(valid_comics)} 个漫画的重复")

        # 从缓存中筛选出相似漫画
        similar_comic_cache_keys = set()
        skipped_comic_cache_keys = set()
        for cache_key, similar_image_counts in similar_comic_cache_dict.items():
            if np.any(similar_image_counts >= min_similar_images):
                similar_comic_cache_keys.add(cache_key)
            else:
                skipped_comic_cache_keys.add(cache_key)

        # 对 valid_comics 进行排序
        if similar_comic_cache_keys or skipped_comic_cache_keys:
            valid_comics.sort(
                key=lambda x: 0
                if x.cache_key in similar_comic_cache_keys
                else 2
                if x.cache_key in skipped_comic_cache_keys
                else 1
            )

        # 生成黑名单图片哈希
        blacklist_hashes = self.blacklist_manager.get_all_hashes()
        if blacklist_hashes:
            blacklist_hashes_array = []
            for hash_hex in blacklist_hashes:
                # 将哈希字符串转换为numpy数组
                hash_obj = imagehash.hex_to_hash(hash_hex)
                hash_array = np.array(hash_obj.hash, dtype=np.uint8)
                blacklist_hashes_array.append(hash_array.flatten())
            blacklist_hashes = np.array(blacklist_hashes_array, dtype=np.uint8)
            del blacklist_hashes_array

        # 构建全局哈希数组和索引映射
        all_hashes = []
        hash_to_comic_idx = []
        comic_hash_ranges = {}  # comic_idx -> (start_idx, end_idx)

        current_idx = 0
        blacklist_image_count = 0
        for comic_idx, comic in enumerate(valid_comics):
            start_idx = current_idx
            # 批量处理图片哈希
            hash_arrays = np.array([h[2] for h in comic.image_hashes])

            # 批量计算黑名单距离
            if len(blacklist_hashes) > 0:
                hamming_distances = np.dot(blacklist_hashes, hash_arrays.T)
                blacklist_mask = np.any(
                    hamming_distances <= similarity_threshold, axis=0
                )
                blacklist_image_count += np.sum(blacklist_mask)
                # 过滤掉黑名单图片
                hash_arrays = hash_arrays[~blacklist_mask]

            # 批量添加有效哈希
            if len(hash_arrays) > 0:
                all_hashes.extend(hash_arrays)
                hash_to_comic_idx.extend([comic_idx] * len(hash_arrays))
                current_idx += len(hash_arrays)

            end_idx = current_idx
            if end_idx > start_idx:
                comic_hash_ranges[comic_idx] = (start_idx, end_idx)

        if not all_hashes:
            logger.warning("没有有效的图片哈希")
            return duplicate_groups

        logger.info(
            f"成功构建了 {len(all_hashes)} 个图片哈希，其中 {blacklist_image_count} 个被排除在黑名单内"
        )

        # 转换为numpy矩阵
        all_hashes = np.array(all_hashes)  # shape: (total_images, hash_bits)
        all_hashes_inv = ~all_hashes
        hash_to_comic_idx = np.array(hash_to_comic_idx, dtype=np.int32)

        # 计算跳过的漫画数量并更新总文件数
        skipped_count = sum(
            1 for comic in valid_comics if comic.cache_key in skipped_comic_cache_keys
        )
        remaining_count = len(valid_comics) - skipped_count
        logger.info(
            f"已跳过 {skipped_count} 个漫画文件，开始处理剩余 {remaining_count} 个"
        )

        # 进度条更新
        self.progress.stage = "processing"
        self.progress.processed_files = skipped_count
        self.progress.duplicates_found = 0
        self.progress.total_files = len(valid_comics)
        self.progress.start_time = time.time()
        self.progress.history = []

        # 对每个漫画进行重复检测
        for comic_idx, comic in enumerate(valid_comics):
            # 如果之后的漫画已跳过，则停止处理
            if comic.cache_key in skipped_comic_cache_keys:
                logger.info("遇到已跳过的漫画，提前结束重复检测")
                break

            # 更新进度
            self.progress.processed_files += 1
            self.progress.duplicates_found = len(duplicate_groups)
            self.progress.current_file = os.path.basename(comic.path)
            self.progress.elapsed_time = time.time() - self.progress.start_time
            self.progress_updated.emit(self.progress)

            # 等待暂停
            while self.is_paused and not self.should_stop:
                time.sleep(0.1)

            if self.should_stop:
                logger.info("处理已停止")
                break

            if comic_idx in processed_comic_indices:
                continue

            if comic_idx not in comic_hash_ranges:
                continue

            start_idx, end_idx = comic_hash_ranges[comic_idx]
            comic_hashes = all_hashes[start_idx:end_idx].astype(
                np.uint8
            )  # 当前漫画的哈希矩阵

            # 计算当前漫画图片与后续图片的汉明距离矩阵
            sub_hashes = all_hashes[end_idx:]
            sub_hashes_inv = all_hashes_inv[end_idx:]
            hamming_distances = np.dot(comic_hashes, sub_hashes_inv.T) + np.dot(
                1 - comic_hashes, sub_hashes.T
            )  # shape: (comic_images, all_images)

            # 应用相似度阈值
            similarity_mask = hamming_distances <= similarity_threshold

            # 获取相似图片对应的漫画索引
            similar_image_mask = np.any(similarity_mask, axis=0)
            similar_comic_indices = hash_to_comic_idx[end_idx:][similar_image_mask]

            # 统计每个漫画的相似图片数量
            unique_comics, counts = np.unique(similar_comic_indices, return_counts=True)

            # 更新缓存
            similar_comic_cache_dict[comic.cache_key] = counts

            # 找到满足最小相似图片数量要求的漫画
            valid_similar_comics = unique_comics[counts >= min_similar_images]

            # 去除已经处理过的漫画
            valid_similar_comics = [
                int(idx)
                for idx in valid_similar_comics
                if idx not in processed_comic_indices
            ]

            if len(valid_similar_comics) > 0:
                # 构建重复组
                similar_comics = [comic]
                all_similar_groups = []

                for similar_comic_idx in valid_similar_comics:
                    similar_comic = valid_comics[similar_comic_idx]
                    similar_comics.append(similar_comic)

                    # 收集相似图片的位置信息
                    similar_start_idx, similar_end_idx = comic_hash_ranges[
                        similar_comic_idx
                    ]
                    image_mask = similarity_mask[
                        :, similar_start_idx - end_idx : similar_end_idx - end_idx
                    ]
                    image_positions = np.nonzero(image_mask)

                    for pos_i, pos_j in zip(image_positions[0], image_positions[1]):
                        hash1 = all_hashes[start_idx + pos_i]
                        hash1 = str(imagehash.ImageHash(hash1))
                        hash2 = all_hashes[similar_start_idx + pos_j]
                        hash2 = str(imagehash.ImageHash(hash2))
                        similarity = int(
                            hamming_distances[
                                pos_i, similar_start_idx - end_idx + pos_j
                            ]
                        )
                        all_similar_groups.append((hash1, hash2, similarity))

                duplicate_group = DuplicateGroup(
                    comics=similar_comics,
                    similar_hash_groups=all_similar_groups,
                    similarity_count=len(all_similar_groups),
                )
                duplicate_groups.append(duplicate_group)

                # 标记已处理
                processed_comic_indices.update(valid_similar_comics)

                # 缓存持久化
                self._persist_cache_keys(similar_comic_cache_dict)

        # 缓存持久化
        self._persist_cache_keys(similar_comic_cache_dict)
        return duplicate_groups
