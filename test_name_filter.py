#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试名称筛选功能
"""

import re
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.config_manager import ConfigManager

def test_config_manager():
    """测试配置管理器的筛选设置功能"""
    print("测试配置管理器的筛选设置功能...")
    
    config = ConfigManager()
    
    # 测试默认设置
    default_settings = config.get_filter_settings()
    print(f"默认筛选设置: {default_settings}")
    
    # 测试设置新的筛选配置
    test_settings = {
        'created_filter_enabled': True,
        'created_after': '2023-01-01',
        'created_before': '2023-12-31',
        'modified_filter_enabled': True,
        'modified_after': '2023-06-01',
        'modified_before': '2023-12-31',
        'name_filter_enabled': True,
        'name_filter_regex': r'.*test.*|.*demo.*'
    }
    
    config.set_filter_settings(test_settings)
    print(f"设置新的筛选配置: {test_settings}")
    
    # 验证设置是否保存成功
    saved_settings = config.get_filter_settings()
    print(f"保存后的筛选设置: {saved_settings}")
    
    # 验证设置是否正确
    assert saved_settings['name_filter_enabled'] == True
    assert saved_settings['name_filter_regex'] == r'.*test.*|.*demo.*'
    print("✓ 配置管理器测试通过!")

def test_regex_filtering():
    """测试正则表达式筛选逻辑"""
    print("\n测试正则表达式筛选逻辑...")
    
    # 测试用例
    test_cases = [
        {
            'regex': r'.*test.*',
            'names': ['test_manga', 'my_test_comic', 'normal_manga', 'testing_book'],
            'expected_filtered': ['test_manga', 'my_test_comic', 'testing_book']
        },
        {
            'regex': r'^demo_.*',
            'names': ['demo_manga', 'my_demo_comic', 'demo_test', 'normal_manga'],
            'expected_filtered': ['demo_manga', 'demo_test']
        },
        {
            'regex': r'.*\.(tmp|temp)$',
            'names': ['manga.tmp', 'comic.temp', 'normal.zip', 'test.tmp'],
            'expected_filtered': ['manga.tmp', 'comic.temp', 'test.tmp']
        }
    ]
    
    for i, case in enumerate(test_cases):
        print(f"\n测试用例 {i+1}: 正则表达式 '{case['regex']}'")
        
        try:
            pattern = re.compile(case['regex'])
            filtered = []
            
            for name in case['names']:
                if pattern.search(name):
                    filtered.append(name)
                    print(f"  ✓ '{name}' 匹配 (将被排除)")
                else:
                    print(f"  - '{name}' 不匹配 (保留)")
            
            # 验证结果
            assert set(filtered) == set(case['expected_filtered']), \
                f"期望过滤: {case['expected_filtered']}, 实际过滤: {filtered}"
            
            print(f"  ✓ 测试用例 {i+1} 通过!")
            
        except re.error as e:
            print(f"  ✗ 正则表达式错误: {e}")

if __name__ == "__main__":
    print("开始测试名称筛选功能...\n")
    
    try:
        test_config_manager()
        test_regex_filtering()
        print("\n🎉 所有测试通过! 名称筛选功能实现成功!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()