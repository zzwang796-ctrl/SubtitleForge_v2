#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDD 测试: T15 - 跨平台字体检测
验证 FontDetector 的正确性
"""

import unittest
import sys
import os

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from font_utils import FontDetector


class TestFontDetector(unittest.TestCase):
    """测试字体检测器"""

    def test_get_system_platform(self):
        """测试获取系统平台"""
        platform = FontDetector.get_system_platform()
        self.assertIsNotNone(platform)
        # Windows 应该是 win32
        self.assertIn(platform, ["win32", "darwin", "linux"])

    def test_platform_detection(self):
        """测试平台检测方法"""
        # 至少有一个为真
        is_windows = FontDetector.is_windows()
        is_macos = FontDetector.is_macos()
        is_linux = FontDetector.is_linux()
        # 至少一个应该是 True
        self.assertTrue(is_windows or is_macos or is_linux)

    def test_get_font_dirs(self):
        """测试获取字体目录"""
        dirs = FontDetector.get_font_dirs()
        self.assertIsInstance(dirs, list)
        # Windows 应该有字体目录
        if FontDetector.is_windows():
            self.assertTrue(len(dirs) > 0)
            # 检查常见目录
            self.assertTrue(any("Windows\\Fonts" in d for d in dirs))

    def test_get_available_fonts(self):
        """测试获取可用字体"""
        fonts = FontDetector.get_available_fonts()
        self.assertIsInstance(fonts, list)
        # 系统通常有字体
        if FontDetector.is_windows():
            self.assertTrue(len(fonts) > 0)

    def test_is_font_available(self):
        """测试检查字体是否可用"""
        # 测试一个不太可能存在的字体
        result = FontDetector.is_font_available("ThisFontDoesNotExist12345")
        self.assertFalse(result)

    def test_find_font(self):
        """测试查找字体"""
        # 查找不存在的字体
        result = FontDetector.find_font("NonExistentFont999")
        self.assertIsNone(result)

    def test_get_default_font(self):
        """测试获取默认字体"""
        default_zh = FontDetector.get_default_font("zh")
        self.assertIsInstance(default_zh, str)
        self.assertTrue(len(default_zh) > 0)

        default_ja = FontDetector.get_default_font("ja")
        self.assertIsInstance(default_ja, str)
        self.assertTrue(len(default_ja) > 0)

    def test_get_recommended_fonts(self):
        """测试获取推荐字体"""
        fonts = FontDetector.get_recommended_fonts()
        self.assertIsInstance(fonts, list)
        self.assertTrue(len(fonts) > 0)

        # 检查字体结构
        for font in fonts:
            self.assertIn("name", font)
            self.assertIn("available", font)
            self.assertIn("language", font)

    def test_expand_path(self):
        """测试路径展开"""
        # 测试用户目录展开
        expanded = FontDetector.expand_path("~/.fonts")
        self.assertNotEqual(expanded, "~/.fonts")  # 应该被展开了

    def test_scan_fonts_in_dir(self):
        """测试扫描目录下的字体"""
        # 获取字体目录
        dirs = FontDetector.get_font_dirs()
        if dirs:
            fonts = FontDetector.scan_fonts_in_dir(dirs[0])
            self.assertIsInstance(fonts, list)


if __name__ == '__main__':
    unittest.main()
