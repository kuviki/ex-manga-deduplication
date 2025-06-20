# -*- coding: utf-8 -*-
"""
漫画扫描器模块
负责扫描目录中的漫画文件并检测重复
"""

import os
import time
from typing import List, Dict, Set, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from loguru import logger
from PyQt5.QtCore import QObject, pyqtSignal

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
    current_images: int = 0
    total_images: int = 0
    duplicates_found: int = 0
    errors: int = 0
    elapsed_time: float = 0.0
    
    @property
    def file_progress(self) -> float:
        """文件处理进度百分比"""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    @property
    def image_progress(self) -> float:
        """图片处理进度百分比"""
        if self.total_images == 0:
            return 0.0
        return (self.current_images / self.total_images) * 100

@dataclass
class ComicInfo:
    """漫画信息"""
    path: str
    size: int
    mtime: float
    image_count: int
    image_hashes: Dict[str, str]  # filename -> hash
    error: Optional[str] = None

@dataclass
class DuplicateGroup:
    """重复漫画组"""
    comics: List[ComicInfo]
    similar_images: List[Tuple[str, str, int]]  # (hash1, hash2, similarity)
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
        self.blacklist_manager = BlacklistManager(self.config.get_blacklist_file())
        self.cache_manager = CacheManager(self.config.get_cache_dir())
        
        self.is_scanning = False
        self.is_paused = False
        self.should_stop = False
        
        self.progress = ScanProgress()
        self.start_time = 0.0
    
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
            self.start_time = time.time()
            
            logger.info(f"开始扫描目录: {directory}")
            
            # 查找所有漫画文件
            comic_files = self._find_comic_files(directory)
            if not comic_files:
                self.scan_error.emit("未找到支持的漫画文件")
                return
            
            self.progress = ScanProgress(total_files=len(comic_files))
            self.progress_updated.emit(self.progress)
            
            # 处理漫画文件
            comic_infos = self._process_comic_files(comic_files)
            
            if self.should_stop:
                logger.info("扫描已停止")
                return
            
            # 检测重复
            duplicate_groups = self._detect_duplicates(comic_infos)
            
            self.progress.duplicates_found = len(duplicate_groups)
            self.progress.elapsed_time = time.time() - self.start_time
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
            logger.info("扫描已恢复")
            self.scan_resumed.emit()
    
    def stop_scan(self) -> None:
        """停止扫描"""
        if self.is_scanning:
            self.should_stop = True
            logger.info("正在停止扫描...")
    
    def _find_comic_files(self, directory: str) -> List[str]:
        """查找目录中的所有漫画文件"""
        comic_files = []
        supported_formats = self.config.get_supported_formats()
        
        for root, dirs, files in os.walk(directory):
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
            future_to_file = {executor.submit(self._process_single_comic, file): file 
                             for file in comic_files}
            
            # 处理结果
            for future in as_completed(future_to_file):
                if self.should_stop:
                    break
                
                # 等待暂停
                while self.is_paused and not self.should_stop:
                    time.sleep(0.1)
                
                file_path = future_to_file[future]
                try:
                    comic_info = future.result()
                    if comic_info:
                        comic_infos.append(comic_info)
                    
                    self.progress.processed_files += 1
                    self.progress.current_file = os.path.basename(file_path)
                    self.progress.elapsed_time = time.time() - self.start_time
                    self.progress_updated.emit(self.progress)
                    
                except Exception as e:
                    logger.error(f"处理漫画文件失败 {file_path}: {e}")
                    self.progress.errors += 1
        
        return comic_infos
    
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
                        image_count=cached_info['image_count'],
                        image_hashes=cached_info['image_hashes']
                    )
            
            # 处理压缩包
            image_hashes = {}
            min_width, min_height = self.config.get_min_image_resolution()
            
            for filename, image_data in self.archive_reader.read_all_images(file_path):
                if self.should_stop:
                    break
                
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
                    
                    # 检查黑名单
                    if not self.blacklist_manager.is_blacklisted(image_hash):
                        image_hashes[filename] = image_hash
                        
                except Exception as e:
                    logger.warning(f"计算图片哈希失败 {file_path}/{filename}: {e}")
                    continue
            
            comic_info = ComicInfo(
                path=file_path,
                size=size,
                mtime=mtime,
                image_count=len(image_hashes),
                image_hashes=image_hashes
            )
            
            # 保存到缓存
            if self.config.is_cache_enabled():
                self.cache_manager.set_comic_cache(
                    file_path, mtime, self.config.get_hash_algorithm(),
                    {
                        'image_count': len(image_hashes),
                        'image_hashes': image_hashes
                    }
                )
            
            return comic_info
            
        except Exception as e:
            logger.error(f"处理漫画文件失败 {file_path}: {e}")
            return ComicInfo(
                path=file_path,
                size=0,
                mtime=0,
                image_count=0,
                image_hashes={},
                error=str(e)
            )
    
    def _detect_duplicates(self, comic_infos: List[ComicInfo]) -> List[DuplicateGroup]:
        """检测重复漫画"""
        duplicate_groups = []
        processed_comics = set()
        
        similarity_threshold = self.config.get_similarity_threshold()
        min_similar_images = self.config.get_min_similar_images()
        
        for i, comic1 in enumerate(comic_infos):
            if comic1.path in processed_comics or comic1.error:
                continue
            
            similar_comics = [comic1]
            all_similar_images = []
            
            for j, comic2 in enumerate(comic_infos[i+1:], i+1):
                if comic2.path in processed_comics or comic2.error:
                    continue
                
                # 比较两个漫画的相似图片
                similar_images = self._compare_comics(comic1, comic2, similarity_threshold)
                
                if len(similar_images) >= min_similar_images:
                    similar_comics.append(comic2)
                    all_similar_images.extend(similar_images)
            
            # 如果找到重复漫画
            if len(similar_comics) > 1:
                duplicate_group = DuplicateGroup(
                    comics=similar_comics,
                    similar_images=all_similar_images,
                    similarity_count=len(all_similar_images)
                )
                duplicate_groups.append(duplicate_group)
                
                # 标记已处理
                for comic in similar_comics:
                    processed_comics.add(comic.path)
        
        return duplicate_groups
    
    def _compare_comics(self, comic1: ComicInfo, comic2: ComicInfo, 
                       threshold: int) -> List[Tuple[str, str, int]]:
        """比较两个漫画的相似图片"""
        similar_images = []
        
        for filename1, hash1 in comic1.image_hashes.items():
            for filename2, hash2 in comic2.image_hashes.items():
                similarity = self.image_hasher.calculate_similarity(hash1, hash2)
                
                if similarity <= threshold:
                    similar_images.append((hash1, hash2, similarity))
        
        return similar_images