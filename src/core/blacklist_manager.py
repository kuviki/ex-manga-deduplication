# -*- coding: utf-8 -*-
"""
黑名单管理模块
负责管理需要排除的图片黑名单
"""

import os
import yaml
from typing import Set, List, Dict, Any
from loguru import logger
from .image_hash import ImageHasher

class BlacklistManager:
    """黑名单管理器"""
    
    def __init__(self, blacklist_file: str = "blacklist.yaml"):
        self.blacklist_file = blacklist_file
        self.blacklist_hashes: Set[str] = set()
        self.blacklist_info: Dict[str, Dict[str, Any]] = {}
        self.load_blacklist()
    
    def load_blacklist(self) -> None:
        """从文件加载黑名单"""
        if os.path.exists(self.blacklist_file):
            try:
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    
                    # 加载哈希值集合
                    self.blacklist_hashes = set(data.get('hashes', []))
                    
                    # 加载详细信息
                    self.blacklist_info = data.get('info', {})
                    
                logger.info(f"黑名单加载成功: {len(self.blacklist_hashes)} 个项目")
            except Exception as e:
                logger.error(f"黑名单加载失败: {e}")
                self.blacklist_hashes = set()
                self.blacklist_info = {}
        else:
            logger.info("黑名单文件不存在，创建新的黑名单")
            self.save_blacklist()
    
    def save_blacklist(self) -> None:
        """保存黑名单到文件"""
        try:
            os.makedirs(os.path.dirname(self.blacklist_file) or '.', exist_ok=True)
            
            data = {
                'hashes': list(self.blacklist_hashes),
                'info': self.blacklist_info
            }
            
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                
            logger.info(f"黑名单保存成功: {len(self.blacklist_hashes)} 个项目")
        except Exception as e:
            logger.error(f"黑名单保存失败: {e}")
    
    def add_image(self, image_hash: str, archive_path: str = "", 
                  image_filename: str = "", description: str = "") -> bool:
        """添加图片到黑名单
        
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
                'archive_path': archive_path,
                'image_filename': image_filename,
                'description': description,
                'added_time': self._get_current_time()
            }
            
            logger.info(f"图片已添加到黑名单: {image_filename}")
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
            
            self.blacklist_hashes.remove(image_hash)
            
            # 移除详细信息
            if image_hash in self.blacklist_info:
                del self.blacklist_info[image_hash]
            
            logger.info(f"图片已从黑名单移除: {image_hash}")
            return True
            
        except Exception as e:
            logger.error(f"从黑名单移除图片失败: {e}")
            return False
    
    def is_blacklisted(self, image_hash: str) -> bool:
        """检查图片是否在黑名单中
        
        Args:
            image_hash: 图片哈希值
            
        Returns:
            bool: 是否在黑名单中
        """
        return image_hash in self.blacklist_hashes
    
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
        self.blacklist_hashes.clear()
        self.blacklist_info.clear()
        logger.info("黑名单已清空")
    
    def export_blacklist(self, export_file: str) -> bool:
        """导出黑名单到文件
        
        Args:
            export_file: 导出文件路径
            
        Returns:
            bool: 是否成功导出
        """
        try:
            data = {
                'hashes': list(self.blacklist_hashes),
                'info': self.blacklist_info,
                'export_time': self._get_current_time(),
                'count': len(self.blacklist_hashes)
            }
            
            with open(export_file, 'w', encoding='utf-8') as f:
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
            
            with open(import_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            imported_hashes = set(data.get('hashes', []))
            imported_info = data.get('info', {})
            
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
    
    def filter_similar_hashes(self, hash_list: List[str], hasher: ImageHasher, 
                             threshold: int = 5) -> List[str]:
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
        return {
            'total_count': len(self.blacklist_hashes),
            'file_path': self.blacklist_file,
            'has_info': len(self.blacklist_info),
            'archives': list(set(info.get('archive_path', '') for info in self.blacklist_info.values() if info.get('archive_path')))
        }
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')