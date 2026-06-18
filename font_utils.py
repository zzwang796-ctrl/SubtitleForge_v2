#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SubtitleForge v2 - 跨平台字体检测模块
支持 Windows、macOS、Linux 系统字体检测
"""

import os
import sys
from typing import List, Dict, Optional


class FontDetector:
    """跨平台字体检测器"""

    # 各平台常见中文字体映射（备选方案）
    FALLBACK_FONTS = {
        "windows": [
            "Microsoft YaHei",
            "Microsoft YaHei UI",
            "SimHei",
            "SimSun",
            "PingFang SC",
            "STHeiti",
        ],
        "darwin": [
            "PingFang SC",
            "STHeiti",
            "Apple LiGothic",
            "Hiragino Sans GB",
            "Microsoft YaHei",
        ],
        "linux": [
            "Noto Sans CJK SC",
            "Noto Sans CJK JP",
            "WenQuanYi Micro Hei",
            "Source Han Sans SC",
            "Droid Sans Fallback",
        ],
    }

    # Windows 字体目录
    WINDOWS_FONT_DIRS = [
        r"C:\Windows\Fonts",
        r"C:\Users\{}\AppData\Local\Microsoft\Windows\Fonts".format(os.getenv("USERNAME", "")),
    ]

    # macOS 字体目录
    DARWIN_FONT_DIRS = [
        "/System/Library/Fonts",
        "/Library/Fonts",
        "/Users/{}/Library/Fonts".format(os.getenv("USER", "")),
    ]

    # Linux 字体目录
    LINUX_FONT_DIRS = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        "~/.fonts",
        "~/.local/share/fonts",
    ]

    @classmethod
    def get_system_platform(cls) -> str:
        """获取当前系统平台"""
        return sys.platform.lower()

    @classmethod
    def is_windows(cls) -> bool:
        return cls.get_system_platform().startswith("win")

    @classmethod
    def is_macos(cls) -> bool:
        return cls.get_system_platform().startswith("darwin")

    @classmethod
    def is_linux(cls) -> bool:
        return cls.get_system_platform().startswith("linux")

    @classmethod
    def expand_path(cls, path: str) -> str:
        """展开路径中的用户目录"""
        return os.path.expanduser(os.path.expandvars(path))

    @classmethod
    def get_font_dirs(cls) -> List[str]:
        """获取当前平台的字体目录列表"""
        if cls.is_windows():
            dirs = cls.WINDOWS_FONT_DIRS.copy()
            # 动态替换用户名
            dirs = [cls.expand_path(d) for d in dirs]
            return [d for d in dirs if os.path.exists(d)]
        elif cls.is_macos():
            dirs = cls.DARWIN_FONT_DIRS.copy()
            dirs = [cls.expand_path(d) for d in dirs]
            return [d for d in dirs if os.path.exists(d)]
        else:
            dirs = cls.LINUX_FONT_DIRS.copy()
            dirs = [cls.expand_path(d) for d in dirs]
            result = []
            for d in dirs:
                if os.path.exists(d):
                    result.append(d)
                # 递归检查子目录
                if os.path.isdir(d):
                    for subdir in os.listdir(d):
                        subpath = os.path.join(d, subdir)
                        if os.path.isdir(subpath) and subpath not in result:
                            result.append(subpath)
            return result

    @classmethod
    def scan_fonts_in_dir(cls, font_dir: str) -> List[str]:
        """扫描目录下的所有字体文件"""
        font_extensions = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
        fonts = set()

        try:
            for root, _, files in os.walk(font_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in font_extensions:
                        # 字体名称（不带扩展名）
                        font_name = os.path.splitext(file)[0]
                        fonts.add(font_name)
        except PermissionError:
            pass

        return sorted(fonts)

    @classmethod
    def get_available_fonts(cls) -> List[str]:
        """获取系统中所有可用的字体"""
        fonts = set()

        for font_dir in cls.get_font_dirs():
            fonts.update(cls.scan_fonts_in_dir(font_dir))

        return sorted(fonts)

    @classmethod
    def find_font(cls, font_name: str) -> Optional[str]:
        """
        检查字体是否存在

        Args:
            font_name: 字体名称

        Returns:
            字体文件路径，如果不存在返回 None
        """
        if not font_name:
            return None

        # 首先检查字体文件是否存在
        if os.path.isfile(font_name):
            return font_name

        # 在字体目录中搜索
        for font_dir in cls.get_font_dirs():
            for root, _, files in os.walk(font_dir):
                for file in files:
                    file_name = os.path.splitext(file)[0]
                    if file_name.lower() == font_name.lower():
                        return os.path.join(root, file)

        return None

    @classmethod
    def is_font_available(cls, font_name: str) -> bool:
        """检查字体是否可用"""
        return cls.find_font(font_name) is not None

    @classmethod
    def get_default_font(cls, language: str = "zh") -> str:
        """
        获取指定语言的默认字体

        Args:
            language: 语言代码，"zh" 为中文，"ja" 为日文

        Returns:
            系统可用的默认字体名称
        """
        platform = "windows" if cls.is_windows() else ("darwin" if cls.is_macos() else "linux")

        # 获取该平台的备选字体列表
        fallback_list = cls.FALLBACK_FONTS.get(platform, cls.FALLBACK_FONTS["windows"])

        # 按优先级查找第一个可用的字体
        for font in fallback_list:
            if cls.is_font_available(font):
                return font

        # 如果都不可用，返回系统中的第一个可用字体
        available = cls.get_available_fonts()
        if available:
            return available[0]

        return "Arial"  # 最终回退

    @classmethod
    def get_recommended_fonts(cls) -> List[Dict[str, str]]:
        """
        获取推荐的字体列表（带详细信息）

        Returns:
            字体列表，每个元素包含 name、path、language 属性
        """
        recommended = []

        # 常见推荐字体
        recommended_names = [
            # 中文推荐
            ("Microsoft YaHei", "zh", "微软雅黑 - Windows 最佳中文字体"),
            ("Microsoft YaHei UI", "zh", "微软雅黑 UI - Windows 更好看的版本"),
            ("PingFang SC", "zh", "苹方 - macOS 中文字体"),
            ("Noto Sans CJK SC", "zh", "思源黑体 - Linux/跨平台"),
            ("SimHei", "zh", "黑体 - Windows 常见"),
            # 日文推荐
            ("Yu Gothic UI", "ja", "游 Gothic UI - Windows 日文字体"),
            ("Hiragino Sans GB", "ja", "冬青黑体 - macOS 日文字体"),
            ("Meiryo", "ja", "明瞭 - Windows 日文字体"),
            # 通用
            ("Arial", "latin", "Arial - 通用拉丁字体"),
            ("Times New Roman", "latin", "Times New Roman - 通用衬线字体"),
        ]

        for font_name, language, description in recommended_names:
            font_path = cls.find_font(font_name)
            if font_path:
                recommended.append({
                    "name": font_name,
                    "path": font_path,
                    "language": language,
                    "description": description,
                    "available": True,
                })
            else:
                recommended.append({
                    "name": font_name,
                    "path": "",
                    "language": language,
                    "description": description,
                    "available": False,
                })

        return recommended


# 测试函数
def test_font_detector():
    """测试字体检测器"""
    print(f"系统平台: {FontDetector.get_system_platform()}")
    print(f"字体目录: {FontDetector.get_font_dirs()}")
    print()

    print("=== 系统可用字体 ===")
    fonts = FontDetector.get_available_fonts()
    print(f"共 {len(fonts)} 个字体")
    # 只显示前 20 个
    for font in fonts[:20]:
        print(f"  - {font}")
    if len(fonts) > 20:
        print(f"  ... 还有 {len(fonts) - 20} 个字体")

    print()
    print("=== 推荐字体 ===")
    recommended = FontDetector.get_recommended_fonts()
    for font in recommended:
        status = "✓" if font["available"] else "✗"
        print(f"  {status} {font['name']} ({font['language']}) - {font['description']}")

    print()
    print(f"默认中文字体: {FontDetector.get_default_font('zh')}")
    print(f"默认日文字体: {FontDetector.get_default_font('ja')}")


if __name__ == "__main__":
    test_font_detector()
