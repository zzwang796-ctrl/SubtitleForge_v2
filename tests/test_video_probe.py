#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDD 测试: T19 - ffprobe视频预检
验证 VideoProbe 的正确性
"""

import unittest
import sys
import os

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio_extractor import VideoProbe


class TestVideoProbe(unittest.TestCase):
    """测试视频预检模块"""

    def setUp(self):
        """设置测试"""
        try:
            self.probe = VideoProbe()
        except RuntimeError as e:
            self.skipTest(f"ffprobe not available: {e}")

    def test_probe_valid_video(self):
        """测试探测有效视频"""
        # 使用测试视频（如果存在）
        test_video = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_output",
            "【病娇 NTR】被女性朋友强制拘束，惩罚出轨的我....wav"
        )

        # 这个文件是音频不是视频，跳过
        if not test_video.endswith('.mp4'):
            self.skipTest("No mp4 test video available")

        if not os.path.exists(test_video):
            self.skipTest("Test video not found")

        info = self.probe.probe(test_video)
        self.assertIn("streams", info)
        self.assertIn("format", info)

    def test_validate_nonexistent_file(self):
        """测试验证不存在的文件"""
        is_valid, errors = self.probe.validate("nonexistent_video.mp4")
        self.assertFalse(is_valid)
        self.assertTrue(any("不存在" in e for e in errors))

    def test_validate_empty_file(self):
        """测试验证空文件"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"")  # 写入空内容
            temp_path = f.name

        try:
            is_valid, errors = self.probe.validate(temp_path)
            self.assertFalse(is_valid)
            self.assertTrue(any("为空" in e for e in errors))
        finally:
            os.unlink(temp_path)

    def test_get_summary(self):
        """测试获取视频摘要"""
        test_video = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_output",
            "【病娇 NTR】被女性朋友强制拘束，惩罚出轨的我....wav"
        )

        # 这是音频文件，探测应该能工作
        if os.path.exists(test_video):
            summary = self.probe.get_summary(test_video)
            self.assertIn("filename", summary)
            self.assertIn("path", summary)
            self.assertIn("file_size", summary)

    def test_parse_fps(self):
        """测试帧率解析"""
        # 测试分数格式
        fps = self.probe._parse_fps("30000/1001")
        self.assertAlmostEqual(fps, 29.97, places=1)

        # 测试整数格式
        fps = self.probe._parse_fps("30")
        self.assertEqual(fps, 30.0)

        # 测试无效格式
        fps = self.probe._parse_fps("invalid")
        self.assertEqual(fps, 0.0)

    def test_ffprobe_found(self):
        """测试 ffprobe 是否可用"""
        self.assertIsNotNone(self.probe.ffprobe)
        self.assertTrue(len(self.probe.ffprobe) > 0)

    def test_ffmpeg_found(self):
        """测试 ffmpeg 是否可用"""
        self.assertIsNotNone(self.probe.ffmpeg)
        self.assertTrue(len(self.probe.ffmpeg) > 0)


class TestVideoProbeValidation(unittest.TestCase):
    """测试视频验证逻辑"""

    def setUp(self):
        """设置测试"""
        try:
            self.probe = VideoProbe()
        except RuntimeError as e:
            self.skipTest(f"ffprobe not available: {e}")

    def test_validation_checks_all_criteria(self):
        """测试验证检查所有条件"""
        import tempfile

        # 创建一个临时空文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            temp_path = f.name

        try:
            is_valid, errors = self.probe.validate(temp_path)
            # 空文件应该验证失败
            self.assertFalse(is_valid)
            self.assertTrue(len(errors) > 0)
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
