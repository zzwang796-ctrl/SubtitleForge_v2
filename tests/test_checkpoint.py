#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDD 测试: T18 - 断点续传机制
验证 CheckpointManager 的正确性
"""

import unittest
import tempfile
import os
import sys
import json

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checkpoint import CheckpointManager, PipelineStage, Checkpoint


class TestCheckpointManager(unittest.TestCase):
    """测试检查点管理器"""

    def setUp(self):
        """创建临时目录用于测试"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(self.temp_dir)

    def tearDown(self):
        """清理临时目录"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_no_checkpoint_initially(self):
        """测试初始状态无检查点"""
        checkpoint = self.manager.load_checkpoint()
        self.assertIsNone(checkpoint)

    def test_save_and_load_checkpoint(self):
        """测试保存和加载检查点"""
        self.manager.save_checkpoint(
            PipelineStage.AUDIO_EXTRACTION,
            "音频提取",
            data={"wav_path": os.path.join(self.temp_dir, "audio.wav")}
        )

        # 重新创建 manager 加载
        manager2 = CheckpointManager(self.temp_dir)
        checkpoint = manager2.load_checkpoint()

        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.stage, PipelineStage.AUDIO_EXTRACTION.value)
        self.assertEqual(checkpoint.stage_name, "音频提取")
        self.assertEqual(checkpoint.data["wav_path"], os.path.join(self.temp_dir, "audio.wav"))

    def test_is_stage_completed(self):
        """测试阶段完成判断"""
        # 初始状态
        self.assertFalse(self.manager.is_stage_completed(PipelineStage.AUDIO_EXTRACTION))

        # 保存阶段1
        self.manager.save_checkpoint(PipelineStage.AUDIO_EXTRACTION, "音频提取")
        self.assertTrue(self.manager.is_stage_completed(PipelineStage.AUDIO_EXTRACTION))
        self.assertFalse(self.manager.is_stage_completed(PipelineStage.SPEECH_RECOGNITION))

    def test_get_latest_stage(self):
        """测试获取最新阶段"""
        # 初始状态
        self.assertIsNone(self.manager.get_latest_stage())

        # 保存阶段1
        self.manager.save_checkpoint(PipelineStage.AUDIO_EXTRACTION, "音频提取")
        self.assertEqual(self.manager.get_latest_stage(), PipelineStage.AUDIO_EXTRACTION)

        # 保存阶段2
        self.manager.save_checkpoint(PipelineStage.SPEECH_RECOGNITION, "语音识别")
        self.assertEqual(self.manager.get_latest_stage(), PipelineStage.SPEECH_RECOGNITION)

    def test_should_skip_stage(self):
        """测试是否应该跳过阶段"""
        # 无检查点时不应跳过
        self.assertFalse(self.manager.should_skip_stage(PipelineStage.AUDIO_EXTRACTION))

        # 保存阶段1完成
        self.manager.save_checkpoint(PipelineStage.AUDIO_EXTRACTION, "音频提取")

        # 阶段1应该被跳过
        self.assertTrue(self.manager.should_skip_stage(PipelineStage.AUDIO_EXTRACTION))
        # 阶段2不应被跳过
        self.assertFalse(self.manager.should_skip_stage(PipelineStage.SPEECH_RECOGNITION))

    def test_get_next_stage(self):
        """测试获取下一个阶段"""
        # 初始状态，下一个应该是阶段1
        self.assertEqual(self.manager.get_next_stage(), PipelineStage.AUDIO_EXTRACTION)

        # 阶段1完成
        self.manager.save_checkpoint(PipelineStage.AUDIO_EXTRACTION, "音频提取")
        self.assertEqual(self.manager.get_next_stage(), PipelineStage.SPEECH_RECOGNITION)

        # 阶段2完成
        self.manager.save_checkpoint(PipelineStage.SPEECH_RECOGNITION, "语音识别")
        self.assertEqual(self.manager.get_next_stage(), PipelineStage.SEMANTIC_SPLITTING)

    def test_clear_checkpoint(self):
        """测试清除检查点"""
        self.manager.save_checkpoint(PipelineStage.AUDIO_EXTRACTION, "音频提取")
        self.assertIsNotNone(self.manager.load_checkpoint())

        self.manager.clear_checkpoint()
        self.assertIsNone(self.manager.load_checkpoint())

    def test_get_progress(self):
        """测试获取进度信息"""
        # 初始状态
        progress = self.manager.get_progress()
        self.assertFalse(progress["has_checkpoint"])
        self.assertEqual(progress["progress_percent"], 0)

        # 阶段1完成
        self.manager.save_checkpoint(PipelineStage.AUDIO_EXTRACTION, "音频提取")
        progress = self.manager.get_progress()
        self.assertTrue(progress["has_checkpoint"])
        self.assertIn("AUDIO_EXTRACTION", progress["completed_stages"])

    def test_completed_pipeline(self):
        """测试流水线完成状态"""
        # 保存完成的检查点
        self.manager.save_checkpoint(
            PipelineStage.VIDEO_BURNING,
            "字幕烧录",
            completed=True,
            data={"output_video": "video.mp4"}
        )

        self.assertTrue(self.manager.get_latest_stage(), PipelineStage.VIDEO_BURNING)
        progress = self.manager.get_progress()
        self.assertTrue(progress["completed"])

    def test_summarize(self):
        """测试进度摘要"""
        # 初始状态
        summary = self.manager.summarize()
        self.assertIn("无检查点", summary)

        # 阶段1进行中
        self.manager.save_checkpoint(PipelineStage.SEMANTIC_SPLITTING, "语义断句")
        summary = self.manager.summarize()
        self.assertIn("SEMANTIC_SPLITTING", summary)
        # 3个阶段已完成: AUDIO_EXTRACTION, SPEECH_RECOGNITION, SEMANTIC_SPLITTING
        # 3/8 = 37.5% ≈ 38%
        self.assertIn("38%", summary)


class TestCheckpointDataClass(unittest.TestCase):
    """测试 Checkpoint 数据类"""

    def test_to_dict_and_from_dict(self):
        """测试序列化/反序列化"""
        checkpoint = Checkpoint(
            stage=1,
            stage_name="测试阶段",
            completed=False,
            timestamp=1234567890.0,
            data={"key": "value"},
            error=None
        )

        # 转字典
        d = checkpoint.to_dict()
        self.assertEqual(d["stage"], 1)
        self.assertEqual(d["stage_name"], "测试阶段")

        # 从字典恢复
        restored = Checkpoint.from_dict(d)
        self.assertEqual(restored.stage, checkpoint.stage)
        self.assertEqual(restored.stage_name, checkpoint.stage_name)
        self.assertEqual(restored.data, checkpoint.data)


if __name__ == '__main__':
    unittest.main()
