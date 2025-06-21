# -*- coding: utf-8 -*-
"""
文件工具模块
提供文件操作相关的实用函数
"""

import os
import shutil
import hashlib
from typing import List, Optional, Tuple
from pathlib import Path
from loguru import logger

def is_supported_archive(file_path: str) -> bool:
    """检查文件是否为支持的压缩格式"""
    if not os.path.isfile(file_path):
        return False
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext in ['.zip', '.rar', '.cbz', '.cbr']

def is_supported_image(file_path: str) -> bool:
    """检查文件是否为支持的图片格式"""
    if not os.path.isfile(file_path):
        return False
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif']

def get_file_size(file_path: str) -> int:
    """获取文件大小（字节）"""
    try:
        return os.path.getsize(file_path)
    except (OSError, IOError):
        return 0

def get_file_hash(file_path: str, algorithm: str = 'md5') -> Optional[str]:
    """计算文件哈希值"""
    try:
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    except Exception as e:
        logger.error(f"计算文件哈希失败 {file_path}: {e}")
        return None

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def safe_delete_file(file_path: str, use_recycle_bin: bool = True) -> bool:
    """安全删除文件"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return False
        
        if use_recycle_bin:
            # 尝试移动到回收站
            try:
                import send2trash
                send2trash.send2trash(file_path)
                logger.info(f"文件已移动到回收站: {file_path}")
                return True
            except ImportError:
                logger.warning("send2trash 模块未安装，使用直接删除")
            except Exception as e:
                logger.error(f"移动到回收站失败: {e}，使用直接删除")
        
        # 直接删除
        os.remove(file_path)
        logger.info(f"文件已删除: {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"删除文件失败 {file_path}: {e}")
        return False

def safe_move_file(src_path: str, dst_path: str) -> bool:
    """安全移动文件"""
    try:
        if not os.path.exists(src_path):
            logger.error(f"源文件不存在: {src_path}")
            return False
        
        # 确保目标目录存在
        dst_dir = os.path.dirname(dst_path)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        # 如果目标文件已存在，生成新名称
        if os.path.exists(dst_path):
            dst_path = get_unique_filename(dst_path)
        
        shutil.move(src_path, dst_path)
        logger.info(f"文件已移动: {src_path} -> {dst_path}")
        return True
    
    except Exception as e:
        logger.error(f"移动文件失败 {src_path} -> {dst_path}: {e}")
        return False

def get_unique_filename(file_path: str) -> str:
    """获取唯一的文件名（如果文件已存在，添加数字后缀）"""
    if not os.path.exists(file_path):
        return file_path
    
    path = Path(file_path)
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{suffix}"
        new_path = parent / new_name
        
        if not new_path.exists():
            return str(new_path)
        
        counter += 1
        
        # 防止无限循环
        if counter > 9999:
            import time
            timestamp = int(time.time())
            new_name = f"{stem}_{timestamp}{suffix}"
            return str(parent / new_name)

def find_files_by_pattern(directory: str, patterns: List[str], recursive: bool = True) -> List[str]:
    """根据模式查找文件"""
    import fnmatch
    
    found_files = []
    
    try:
        if recursive:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    for pattern in patterns:
                        if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                            found_files.append(os.path.join(root, filename))
                            break
        else:
            if os.path.isdir(directory):
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        for pattern in patterns:
                            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                                found_files.append(file_path)
                                break
    
    except Exception as e:
        logger.error(f"查找文件失败: {e}")
    
    return found_files

def get_directory_size(directory: str) -> int:
    """获取目录总大小（字节）"""
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, IOError):
                    continue
    
    except Exception as e:
        logger.error(f"计算目录大小失败: {e}")
    
    return total_size

def ensure_directory_exists(directory: str) -> bool:
    """确保目录存在"""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"创建目录: {directory}")
        return True
    
    except Exception as e:
        logger.error(f"创建目录失败 {directory}: {e}")
        return False

def clean_empty_directories(directory: str) -> int:
    """清理空目录，返回删除的目录数量"""
    deleted_count = 0
    
    try:
        for root, dirs, files in os.walk(directory, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):  # 目录为空
                        os.rmdir(dir_path)
                        logger.info(f"删除空目录: {dir_path}")
                        deleted_count += 1
                except (OSError, IOError) as e:
                    logger.warning(f"删除空目录失败 {dir_path}: {e}")
    
    except Exception as e:
        logger.error(f"清理空目录失败: {e}")
    
    return deleted_count

def get_available_disk_space(path: str) -> Tuple[int, int, int]:
    """获取磁盘空间信息（总空间，已用空间，可用空间）"""
    try:
        if os.name == 'nt':  # Windows
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(path),
                ctypes.pointer(free_bytes),
                ctypes.pointer(total_bytes),
                None
            )
            total = total_bytes.value
            free = free_bytes.value
            used = total - free
        else:  # Unix/Linux
            statvfs = os.statvfs(path)
            total = statvfs.f_frsize * statvfs.f_blocks
            free = statvfs.f_frsize * statvfs.f_available
            used = total - free
        
        return total, used, free
    
    except Exception as e:
        logger.error(f"获取磁盘空间信息失败: {e}")
        return 0, 0, 0

def is_path_writable(path: str) -> bool:
    """检查路径是否可写"""
    try:
        if os.path.isfile(path):
            # 检查文件是否可写
            return os.access(path, os.W_OK)
        elif os.path.isdir(path):
            # 检查目录是否可写
            test_file = os.path.join(path, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                return True
            except (OSError, IOError):
                return False
        else:
            # 检查父目录是否可写
            parent_dir = os.path.dirname(path)
            return os.access(parent_dir, os.W_OK) if os.path.exists(parent_dir) else False
    
    except Exception:
        return False

def backup_file(file_path: str, backup_dir: Optional[str] = None) -> Optional[str]:
    """备份文件"""
    try:
        if not os.path.exists(file_path):
            return None
        
        if backup_dir is None:
            backup_dir = os.path.dirname(file_path)
        
        ensure_directory_exists(backup_dir)
        
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        
        import time
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{name}_backup_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        shutil.copy2(file_path, backup_path)
        logger.info(f"文件已备份: {file_path} -> {backup_path}")
        
        return backup_path
    
    except Exception as e:
        logger.error(f"备份文件失败 {file_path}: {e}")
        return None

def natural_sort_key(filename: str) -> List:
        """自然排序键函数
        
        Args:
            filename: 文件名
            
        Returns:
            List: 排序键
        """
        import re
        
        def convert(text):
            return int(text) if text.isdigit() else text.lower()
        
        def alphanum_key(key):
            return [convert(c) for c in re.split('([0-9]+)', key)]
        
        return alphanum_key(filename)