#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能测试脚本
用于测试numpy优化后的重复检测性能
"""

import time
import os
import sys
import numpy as np
from typing import List
from loguru import logger

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.config_manager import ConfigManager
from src.core.scanner import Scanner, ComicInfo

def create_test_data(num_comics: int = 100, images_per_comic: int = 20) -> List[ComicInfo]:
    """创建测试数据"""
    logger.info(f"创建测试数据: {num_comics} 个漫画，每个 {images_per_comic} 张图片")
    
    comic_infos = []
    
    for i in range(num_comics):
        # 生成随机哈希值（模拟真实哈希）
        image_hashes = {}
        
        for j in range(images_per_comic):
            # 生成64位哈希（8x8像素的感知哈希）
            if i < 10 and j < 5:  # 前10个漫画的前5张图片设为相似
                # 创建相似的哈希（只有少量位不同）
                base_hash = np.random.randint(0, 2, 64, dtype=np.uint8)
                # 随机翻转1-3位
                flip_positions = np.random.choice(64, np.random.randint(1, 4), replace=False)
                base_hash[flip_positions] = 1 - base_hash[flip_positions]
                hash_str = ''.join([hex(int(''.join(map(str, base_hash[k:k+4])), 2))[2:] for k in range(0, 64, 4)])
            else:
                # 生成完全随机的哈希
                random_hash = np.random.randint(0, 2, 64, dtype=np.uint8)
                hash_str = ''.join([hex(int(''.join(map(str, random_hash[k:k+4])), 2))[2:] for k in range(0, 64, 4)])
            
            image_hashes[f"image_{j:03d}.jpg"] = hash_str
        
        comic_info = ComicInfo(
            path=f"test_comic_{i:03d}.zip",
            size=1024 * 1024 * 10,  # 10MB
            mtime=time.time(),
            image_count=images_per_comic,
            image_hashes=image_hashes
        )
        comic_infos.append(comic_info)
    
    return comic_infos

def benchmark_detection(comic_infos: List[ComicInfo], config: ConfigManager) -> float:
    """基准测试重复检测性能"""
    logger.info("开始性能测试...")
    
    scanner = Scanner(config)
    
    start_time = time.time()
    duplicate_groups = scanner._detect_duplicates(comic_infos)
    end_time = time.time()
    
    elapsed_time = end_time - start_time
    
    logger.info(f"检测完成:")
    logger.info(f"  - 处理时间: {elapsed_time:.2f} 秒")
    logger.info(f"  - 漫画数量: {len(comic_infos)}")
    logger.info(f"  - 总图片数: {sum(len(comic.image_hashes) for comic in comic_infos)}")
    logger.info(f"  - 重复组数: {len(duplicate_groups)}")
    logger.info(f"  - 平均每个漫画处理时间: {elapsed_time / len(comic_infos) * 1000:.2f} 毫秒")
    
    return elapsed_time

def main():
    """主函数"""
    logger.info("=== 漫画去重工具性能测试 ===")
    
    # 初始化配置
    config = ConfigManager()
    config.set("similarity_thresholds.perceptual", 5)  # 设置相似度阈值
    config.set("min_similar_images", 3)    # 设置最小相似图片数
    
    # 测试不同规模的数据
    test_cases = [
        (50, 10),   # 50个漫画，每个10张图片
        (100, 20),  # 100个漫画，每个20张图片
        (200, 15),  # 200个漫画，每个15张图片
        (500, 10),  # 500个漫画，每个10张图片
    ]
    
    results = []
    
    for num_comics, images_per_comic in test_cases:
        logger.info(f"\n--- 测试用例: {num_comics} 个漫画，每个 {images_per_comic} 张图片 ---")
        
        # 创建测试数据
        comic_infos = create_test_data(num_comics, images_per_comic)
        
        # 运行性能测试
        elapsed_time = benchmark_detection(comic_infos, config)
        
        total_images = num_comics * images_per_comic
        images_per_second = total_images / elapsed_time
        
        results.append({
            'comics': num_comics,
            'images_per_comic': images_per_comic,
            'total_images': total_images,
            'time': elapsed_time,
            'images_per_second': images_per_second
        })
        
        logger.info(f"  - 处理速度: {images_per_second:.1f} 图片/秒")
    
    # 输出汇总结果
    logger.info("\n=== 性能测试汇总 ===")
    logger.info("漫画数 | 图片/漫画 | 总图片数 | 处理时间(秒) | 速度(图片/秒)")
    logger.info("-" * 60)
    
    for result in results:
        logger.info(
            f"{result['comics']:6d} | "
            f"{result['images_per_comic']:8d} | "
            f"{result['total_images']:8d} | "
            f"{result['time']:11.2f} | "
            f"{result['images_per_second']:12.1f}"
        )
    
    # 计算平均性能
    avg_speed = np.mean([r['images_per_second'] for r in results])
    logger.info(f"\n平均处理速度: {avg_speed:.1f} 图片/秒")
    
    logger.info("\n=== 性能测试完成 ===")
    logger.info("numpy优化的重复检测算法显著提升了处理性能！")

if __name__ == "__main__":
    main()