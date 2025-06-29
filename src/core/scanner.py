# -*- coding: utf-8 -*-
"""
漫画扫描器模块
负责扫描目录中的漫画文件并检测重复
"""

import os
import time
import pickle
import traceback
import numpy as np
import imagehash
from typing import Dict, List, Set, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from loguru import logger
from PyQt5.QtCore import QObject, pyqtSignal
from numpy.typing import NDArray

from src.utils.file_utils import is_supported_archive, is_comic_folder

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
    image_hashes: List[Tuple[str, str]]  # [(filename, hash_hex)]
    image_hash_array: NDArray[np.uint64]
    cache_key: str  # 缓存键
    error: Optional[str] = None
    checked: bool = False  # 是否已检查标记

    def __hash__(self) -> int:
        return hash(self.cache_key)


@dataclass
class DuplicateGroup:
    """重复漫画组"""

    comics: List[ComicInfo]
    similar_hash_groups: Set[Tuple[str, str, int]]  # (hash1, hash2, similarity)


@dataclass
class CachedDuplicateGroup:
    """缓存重复漫画组"""

    comic_cache_keys: List[str]
    similar_hash_groups: Set[Tuple[str, str, int]]  # (hash1, hash2, similarity)


class Scanner(QObject):
    """漫画扫描器"""

    # 信号定义
    progress_updated = pyqtSignal(ScanProgress)
    scan_completed = pyqtSignal(list, float)  # List[DuplicateGroup], elapsed_time
    scan_error = pyqtSignal(str)
    scan_paused = pyqtSignal()
    scan_resumed = pyqtSignal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config = config_manager
        self.archive_reader = ArchiveReader()
        self.image_hasher = ImageHasher(self.config.get_hash_algorithm())
        self.cache_manager = CacheManager(self.config.get_cache_dir())
        self.blacklist_manager = BlacklistManager(
            self.config.get_blacklist_folder(),
            self.image_hasher,
            config_manager,
            self.cache_manager,
        )

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

            start_time = time.time()
            self.progress = ScanProgress(total_files=len(comic_files))
            self.progress_updated.emit(self.progress)
            self.progress.start_time = start_time

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

            elapsed_time = time.time() - start_time
            logger.info(
                f"扫描完成，找到 {len(duplicate_groups)} 组重复漫画，耗时 {elapsed_time:.0f} 秒"
            )
            self.scan_completed.emit(duplicate_groups, elapsed_time)

        except Exception as e:
            logger.error(f"扫描过程中发生错误: {traceback.format_exc()}")
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
        """查找目录中的所有漫画文件和漫画文件夹"""
        comic_files = []
        processed_dirs = set()  # 避免重复处理子目录

        for root, dirs, files in os.walk(directory):
            # 检查当前目录是否是漫画文件夹
            if root not in processed_dirs and is_comic_folder(root):
                comic_files.append(root)
                processed_dirs.add(root)
                # 如果当前目录是漫画文件夹，跳过其子目录
                dirs.clear()
                continue
            
            # 检查压缩包文件
            for file in files:
                if is_supported_archive(file):
                    comic_files.append(os.path.join(root, file))

        logger.info(f"找到 {len(comic_files)} 个漫画文件/文件夹")
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

                except Exception:
                    logger.error(
                        f"处理漫画失败 {file_path}: {traceback.format_exc()}"
                    )
                    self.progress.errors += 1

        return comic_infos

    def _persist_index(
        self,
        similar_comic_cache_dict: dict,
        duplicate_groups: List[DuplicateGroup],
        similarity_threshold: int,
        min_similar_images: int,
    ):
        """持久化索引"""
        cached_duplicate_groups = []
        for group in duplicate_groups:
            cache_group = CachedDuplicateGroup(
                comic_cache_keys=[comic.cache_key for comic in group.comics],
                similar_hash_groups=group.similar_hash_groups,
            )
            cached_duplicate_groups.append(cache_group)

        try:
            cache_data = {
                "similar_comic_cache_dict": similar_comic_cache_dict,
                "cached_duplicate_groups": cached_duplicate_groups,
                "similarity_threshold": similarity_threshold,
                "min_similar_images": min_similar_images,
            }
            with open("index.db", "wb") as f:
                pickle.dump(
                    cache_data,
                    f,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
        except Exception as e:
            logger.error(f"更新缓存 index.db 失败: {e}")

    def _process_single_comic(self, file_path: str) -> Optional[ComicInfo]:
        """处理单个漫画文件或文件夹"""
        try:
            # 获取文件/文件夹信息
            file_stat = os.stat(file_path)
            mtime = file_stat.st_mtime
            
            # 计算大小（文件夹需要递归计算）
            if os.path.isdir(file_path):
                size = 0
                for root, dirs, files in os.walk(file_path):
                    for file in files:
                        try:
                            size += os.path.getsize(os.path.join(root, file))
                        except (OSError, IOError):
                            pass
            else:
                size = file_stat.st_size

            # 检查缓存
            if self.config.is_cache_enabled():
                cached_info = self.cache_manager.get_cache(
                    file_path, mtime, self.config.get_hash_algorithm()
                )
                if (
                    cached_info
                    and "image_hashes" in cached_info
                    and "image_hash_array" in cached_info
                ):
                    logger.debug(f"使用缓存数据: {file_path}")
                    return ComicInfo(
                        path=file_path,
                        size=size,
                        mtime=mtime,
                        image_hashes=cached_info["image_hashes"],
                        image_hash_array=np.array(cached_info["image_hash_array"]),
                        cache_key=self.cache_manager.get_cache_key(
                            file_path, mtime, self.config.get_hash_algorithm()
                        ),
                    )

            # 处理压缩包或文件夹
            image_hashes = []
            min_width, min_height = self.config.get_min_image_resolution()

            image_hash_array = []
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
                    hash_obj = imagehash.hex_to_hash(image_hash)
                    hash_u64 = (
                        np.packbits(hash_obj.hash, axis=1).flatten().view(np.uint64)
                    )
                    image_hashes.append((filename, image_hash))
                    image_hash_array.append(hash_u64)

                except Exception as e:
                    logger.warning(f"计算图片哈希失败 {file_path}/{filename}: {e}")
                    continue

            comic_info = ComicInfo(
                path=file_path,
                size=size,
                mtime=mtime,
                image_hashes=image_hashes,
                image_hash_array=np.array(image_hash_array),
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
                    {
                        "image_hashes": image_hashes,
                        "image_hash_array": image_hash_array,
                    },
                )

            return comic_info

        except Exception as e:
            logger.error(f"处理漫画失败 {file_path}: {e}")
            return None

    def _detect_duplicates(self, comic_infos: List[ComicInfo]) -> List[DuplicateGroup]:
        """检测重复漫画 - 使用numpy优化的高性能实现"""
        duplicate_groups: List[DuplicateGroup] = []

        similarity_threshold = self.config.get_similarity_threshold()
        min_similar_images = self.config.get_min_similar_images()
        min_image_count, max_image_count = self.config.get_comic_image_count_range()

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

        # 生成黑名单图片哈希
        blacklist_hashes = self.blacklist_manager.get_all_hashes()
        if blacklist_hashes:
            blacklist_hashes_array = []
            for hash_hex in blacklist_hashes:
                # 将哈希字符串转换为numpy数组
                hash_obj = imagehash.hex_to_hash(hash_hex)
                hash_u64 = np.packbits(hash_obj.hash, axis=1).flatten().view(np.uint64)
                blacklist_hashes_array.append(hash_u64)
            blacklist_hashes = np.array(blacklist_hashes_array).flatten()
            del blacklist_hashes_array

        logger.info(f"加载了 {len(blacklist_hashes)} 个黑名单图片哈希")

        # 加载索引
        similar_comic_cache_dict: Dict[str, NDArray[np.int64]] = {}
        cached_duplicate_groups: List[CachedDuplicateGroup] = []
        try:
            with open("index.db", "rb") as f:
                cache_data = pickle.load(f)
                similar_comic_cache_dict = cache_data.get(
                    "similar_comic_cache_dict", {}
                )
                cached_duplicate_groups = cache_data.get("cached_duplicate_groups", [])
                cached_similarity_threshold = cache_data.get(
                    "similarity_threshold", None
                )
                cached_min_similar_images = cache_data.get("min_similar_images", None)

                # 最小相似图片减少时
                if (
                    cached_min_similar_images is None
                    or min_similar_images < cached_min_similar_images
                ):
                    cached_duplicate_groups = []
                    logger.info("最小相似图片数量减少，清空缓存的重复组")

                # 相似度阈值放宽时
                if (
                    cached_similarity_threshold is None
                    or similarity_threshold > cached_similarity_threshold
                ):
                    cached_duplicate_groups = []
                    similar_comic_cache_dict = {}
                    logger.info("相似度阈值放宽，清空所有索引")
        except Exception:
            logger.debug("加载索引 index.db 失败")

        # 验证缓存的重复组并提取有效的跳过漫画
        valid_cached_groups = []
        skipped_comic_cache_keys = set()

        # 创建 valid_comics 的 cache_key 到 comic 的映射
        valid_comic_map = {comic.cache_key: comic for comic in valid_comics}

        for group in cached_duplicate_groups:
            # 检查组中的漫画是否仍然存在
            valid_comics_in_group: List[ComicInfo] = []
            for cache_key in group.comic_cache_keys:
                if cache_key in valid_comic_map:
                    # 使用当前的 comic 信息
                    valid_comics_in_group.append(valid_comic_map[cache_key])

            if len(valid_comics_in_group) < 2:
                continue  # 组中有效漫画少于2个，跳过

            # 图片哈希到漫画的映射
            hash_comic_cache_keys = {}
            for comic in valid_comics_in_group:
                for _, image_hash in comic.image_hashes:
                    if image_hash in hash_comic_cache_keys:
                        hash_comic_cache_keys[image_hash].add(comic.cache_key)
                    else:
                        hash_comic_cache_keys[image_hash] = {comic.cache_key}

            # 根据相似度阈值过滤哈希对
            valid_similar_hashes = set()
            valid_similar_hash_groups = []
            for hash1, hash2, distance in group.similar_hash_groups:
                if distance <= similarity_threshold:
                    # 检查哈希的漫画是否仍然存在
                    if (
                        hash1 not in hash_comic_cache_keys
                        or hash2 not in hash_comic_cache_keys
                    ):
                        continue

                    # 检查是否存在于不同漫画中
                    # 如果两个哈希值的所有漫画都相同，则跳过
                    if all(
                        ck1 == ck2
                        for ck1 in hash_comic_cache_keys[hash1]
                        for ck2 in hash_comic_cache_keys[hash2]
                    ):
                        continue

                    if len(blacklist_hashes) == 0:
                        valid_similar_hash_groups.append((hash1, hash2, distance))
                        continue

                    # 检查是否在黑名单中
                    hash1_obj = imagehash.hex_to_hash(hash1)
                    hash1_u64 = (
                        np.packbits(hash1_obj.hash, axis=1).flatten().view(np.uint64)
                    )
                    hash2_obj = imagehash.hex_to_hash(hash2)
                    hash2_u64 = (
                        np.packbits(hash2_obj.hash, axis=1).flatten().view(np.uint64)
                    )
                    hash_u64 = np.stack((hash1_u64, hash2_u64), axis=0)

                    # 批量计算黑名单距离
                    hamming_distances = np.bitwise_count(
                        np.bitwise_xor(hash_u64, blacklist_hashes)
                    )
                    if np.all(hamming_distances > similarity_threshold):
                        valid_similar_hashes.add(hash1)
                        valid_similar_hashes.add(hash2)
                        valid_similar_hash_groups.append((hash1, hash2, distance))

            # 检查是否满足最小相似图片数量要求
            # 统计每个漫画的相似图片数量
            valid_comics_in_group2 = []
            for comic in valid_comics_in_group:
                similar_count = 0
                for _, image_hash in comic.image_hashes:
                    if image_hash in valid_similar_hashes:
                        similar_count += 1
                if similar_count >= min_similar_images:
                    valid_comics_in_group2.append(comic)

            if len(valid_comics_in_group2) < 2:
                continue  # 组中有效漫画少于2个，跳过

            # 更新组信息
            valid_cached_groups.append(
                DuplicateGroup(
                    comics=valid_comics_in_group2,
                    similar_hash_groups=valid_similar_hash_groups,
                )
            )

            # 将这些漫画的 cache_key 加入到跳过列表
            skipped_comic_cache_keys.update(
                comic.cache_key for comic in valid_comics_in_group2
            )

        # 将有效的缓存重复组加入到结果中
        duplicate_groups.extend(valid_cached_groups)

        logger.info(f"从缓存中加载了 {len(valid_cached_groups)} 个有效重复组")

        # 从缓存中筛选出其他跳过的漫画
        for cache_key, similar_image_counts in similar_comic_cache_dict.items():
            if np.all(similar_image_counts < min_similar_images):
                skipped_comic_cache_keys.add(cache_key)

        # 对 valid_comics 进行排序
        if skipped_comic_cache_keys:
            valid_comics.sort(
                key=lambda x: 1 if x.cache_key in skipped_comic_cache_keys else 0
            )

        # 构建全局哈希数组和索引映射
        all_hashes = []
        hash_to_comic_idx = []
        hash_to_image_idx = []
        comic_hash_ranges = {}  # comic_idx -> (start_idx, end_idx)

        current_idx = 0
        blacklist_image_count = 0
        for comic_idx, comic in enumerate(valid_comics):
            start_idx = current_idx
            hash_array = comic.image_hash_array
            hash_index = np.arange(len(hash_array))

            # 批量计算黑名单距离
            if len(blacklist_hashes) > 0:
                hamming_distances = np.bitwise_count(
                    np.bitwise_xor(hash_array, blacklist_hashes)
                )
                blacklist_mask = np.any(
                    hamming_distances <= similarity_threshold, axis=1
                )
                blacklist_image_count += np.sum(blacklist_mask)
                # 过滤掉黑名单图片
                hash_array = hash_array[~blacklist_mask]
                hash_index = hash_index[~blacklist_mask]

            # 批量添加有效哈希
            if len(hash_array) > 0:
                all_hashes.extend(hash_array)
                hash_to_comic_idx.extend([comic_idx] * len(hash_array))
                hash_to_image_idx.extend(hash_index)
                current_idx += len(hash_array)

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
        all_hashes = np.array(all_hashes).flatten()  # shape: (total_images)
        hash_to_comic_idx = np.array(hash_to_comic_idx, dtype=np.int32)
        hash_to_image_idx = np.array(hash_to_image_idx, dtype=np.int32)

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
        self.progress.processed_files = 0
        self.progress.duplicates_found = 0
        self.progress.total_files = remaining_count
        self.progress.start_time = time.time()

        # 构建漫画到重复组的字典映射
        comic_to_group_map: Dict[ComicInfo, DuplicateGroup] = {}

        # 更新字典映射
        for group in valid_cached_groups:
            for comic in group.comics:
                comic_to_group_map[comic.cache_key] = group

        # 对每个漫画进行重复检测
        recall_comic_cache_keys = set()
        for comic_idx, comic in enumerate(valid_comics):
            # 漫画已跳过
            if (
                comic.cache_key in skipped_comic_cache_keys
                and comic.cache_key not in recall_comic_cache_keys
            ):
                continue

            # 更新进度
            self.progress.processed_files += 1
            self.progress.duplicates_found = len(duplicate_groups)
            self.progress.total_files = remaining_count + len(recall_comic_cache_keys)
            self.progress.current_file = os.path.basename(comic.path)
            self.progress.elapsed_time = time.time() - self.progress.start_time
            self.progress_updated.emit(self.progress)

            # 等待暂停
            while self.is_paused and not self.should_stop:
                time.sleep(0.1)

            if self.should_stop:
                logger.info("处理已停止")
                break

            if comic_idx not in comic_hash_ranges:
                continue

            start_idx, end_idx = comic_hash_ranges[comic_idx]
            comic_hashes = all_hashes[start_idx:end_idx]  # 当前漫画的哈希矩阵

            # 逐张计算汉明距离以优化内存占用
            similar_comic_index_dict = {}  # {similar_idx: ({all_hash_idx1}, {all_hash_idx2})}
            similarity_results = {}  # 存储每张图片的相似性结果 {all_hash_idx1: [(all_hash_idx2, distance)]}

            for img_idx, comic_hash in enumerate(comic_hashes):
                # 计算当前图片与所有图片的汉明距离
                hamming_distances = np.bitwise_count(
                    np.bitwise_xor(comic_hash, all_hashes)
                )

                # 应用相似度阈值
                similarity_mask = hamming_distances <= similarity_threshold
                similar_indices = np.where(similarity_mask)[0]

                # 存储相似性结果
                similarity_results[start_idx + img_idx] = [
                    (idx, hamming_distances[idx]) for idx in similar_indices
                ]

                # 获取相似图片对应的漫画索引并统计
                for similar_idx in similar_indices:
                    similar_comic_idx = hash_to_comic_idx[similar_idx]
                    if similar_comic_idx != comic_idx:  # 排除当前漫画
                        if similar_comic_idx in similar_comic_index_dict:
                            similar_comic_index_dict[similar_comic_idx][0].add(img_idx)
                            similar_comic_index_dict[similar_comic_idx][1].add(
                                similar_idx
                            )
                        else:
                            similar_comic_index_dict[similar_comic_idx] = (
                                {img_idx},
                                {similar_idx},
                            )

            # 转换为numpy数组格式以保持兼容性
            counts = np.array(
                [
                    min(len(indices1), len(indices2))
                    for indices1, indices2 in similar_comic_index_dict.values()
                ]
            )

            # 更新缓存
            similar_comic_cache_dict[comic.cache_key] = counts

            # 找到满足最小相似图片数量要求的漫画
            valid_similar_comics = [
                similar_comic_idx
                for similar_comic_idx, (
                    indices1,
                    indices2,
                ) in similar_comic_index_dict.items()
                if min(len(indices1), len(indices2)) >= min_similar_images
            ]

            if len(valid_similar_comics) > 0:
                # 构建重复组
                similar_comics = [comic]
                all_similar_groups = set()

                for similar_comic_idx in valid_similar_comics:
                    similar_comic = valid_comics[similar_comic_idx]
                    similar_comics.append(similar_comic)

                    # 收集相似图片的位置信息
                    similar_start_idx, similar_end_idx = comic_hash_ranges[
                        similar_comic_idx
                    ]

                    # 从结果中收集重复组
                    current_comic_similar_indices = set()
                    for all_hash_idx1, similar_list in similarity_results.items():
                        for all_hash_idx2, distance in similar_list:
                            # 检查是否属于目标漫画
                            if similar_start_idx <= all_hash_idx2 < similar_end_idx:
                                # 取漫画中图片的位置
                                image_idx1 = hash_to_image_idx[all_hash_idx1]
                                image_idx2 = hash_to_image_idx[all_hash_idx2]

                                current_comic_similar_indices.add(image_idx1)
                                hash1 = comic.image_hashes[image_idx1][1]
                                hash2 = similar_comic.image_hashes[image_idx2][1]

                                # 确保哈希顺序一致
                                if hash1 > hash2:
                                    hash1, hash2 = hash2, hash1
                                all_similar_groups.add((hash1, hash2, int(distance)))

                duplicate_group = DuplicateGroup(
                    comics=similar_comics,
                    similar_hash_groups=all_similar_groups,
                )

                # 召回已跳过漫画
                recall_comic_cache_keys.update(
                    c.cache_key
                    for c in duplicate_group.comics
                    if c.cache_key in skipped_comic_cache_keys
                )

                # 合并重复组
                all_merged_comics = set(similar_comics)
                for comic in similar_comics:
                    existing_group = comic_to_group_map.get(comic.cache_key)
                    if existing_group:
                        all_merged_comics.update(existing_group.comics)
                        duplicate_group.similar_hash_groups.update(
                            existing_group.similar_hash_groups
                        )

                        # 移除旧的重复组
                        if existing_group in duplicate_groups:
                            duplicate_groups.remove(existing_group)

                # 更新 similar_comics 为合并后的结果并排序
                duplicate_group.comics = sorted(
                    all_merged_comics, key=lambda c: len(c.image_hashes), reverse=True
                )

                # 更新字典映射
                for comic in duplicate_group.comics:
                    comic_to_group_map[comic.cache_key] = duplicate_group

                # 加入重复组
                duplicate_groups.append(duplicate_group)

                # 索引持久化
                self._persist_index(
                    similar_comic_cache_dict,
                    duplicate_groups,
                    similarity_threshold,
                    min_similar_images,
                )

        # 缓存持久化
        self._persist_index(
            similar_comic_cache_dict,
            duplicate_groups,
            similarity_threshold,
            min_similar_images,
        )
        return duplicate_groups
