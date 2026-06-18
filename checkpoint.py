#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SubtitleForge v2 - 断点续传模块
支持流水线各阶段的检查点和恢复
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class PipelineStage(Enum):
    """流水线阶段枚举"""
    AUDIO_EXTRACTION = 1
    SPEECH_RECOGNITION = 2
    SEMANTIC_SPLITTING = 3
    TRANSLATION = 4
    POST_PROCESSING = 5
    REFINEMENT = 6
    SUBTITLE_EXPORT = 7
    VIDEO_BURNING = 8


@dataclass
class Checkpoint:
    """检查点数据"""
    stage: int  # 当前阶段 (PipelineStage value)
    stage_name: str  # 阶段名称
    completed: bool  # 是否已完成
    timestamp: float  # 创建时间
    data: Dict[str, Any]  # 阶段数据
    error: Optional[str]  # 错误信息（如果有）

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "Checkpoint":
        return cls(**d)


class CheckpointManager:
    """
    断点续传管理器

    功能：
    1. 在每个阶段完成时保存检查点
    2. 支持从指定阶段恢复
    3. 自动检测可用的检查点
    4. 支持查看当前进度
    """

    CHECKPOINT_FILENAME = "pipeline_checkpoint.json"
    STAGE_FILES = {
        PipelineStage.AUDIO_EXTRACTION: "audio.wav",
        PipelineStage.SPEECH_RECOGNITION: "raw_transcript.json",
        PipelineStage.SEMANTIC_SPLITTING: "sentences.json",
        PipelineStage.TRANSLATION: "translated.json",
        PipelineStage.POST_PROCESSING: "final_subtitles_v2.json",
        PipelineStage.REFINEMENT: "refined_subtitles.json",
    }

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.checkpoint_path = os.path.join(output_dir, self.CHECKPOINT_FILENAME)
        self._checkpoint: Optional[Checkpoint] = None

    def _get_timestamp(self) -> float:
        """获取当前时间戳"""
        return time.time()

    def load_checkpoint(self) -> Optional[Checkpoint]:
        """加载检查点"""
        if not os.path.exists(self.checkpoint_path):
            return None

        try:
            with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._checkpoint = Checkpoint.from_dict(data)
            return self._checkpoint
        except Exception as e:
            print(f"警告: 读取检查点失败: {e}")
            return None

    def save_checkpoint(
        self,
        stage: PipelineStage,
        stage_name: str,
        completed: bool = False,
        data: Dict[str, Any] = None,
        error: Optional[str] = None
    ) -> None:
        """
        保存检查点

        Args:
            stage: 当前阶段
            stage_name: 阶段名称
            completed: 是否已完成整个流水线
            data: 阶段相关数据（如输出文件路径）
            error: 错误信息（如果有）
        """
        checkpoint = Checkpoint(
            stage=stage.value,
            stage_name=stage_name,
            completed=completed,
            timestamp=self._get_timestamp(),
            data=data or {},
            error=error
        )

        try:
            with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            self._checkpoint = checkpoint
        except Exception as e:
            print(f"警告: 保存检查点失败: {e}")

    def get_latest_stage(self) -> Optional[PipelineStage]:
        """获取最新完成的阶段"""
        checkpoint = self.load_checkpoint()
        if checkpoint is None:
            return None

        if checkpoint.completed:
            return PipelineStage.VIDEO_BURNING  # 全部完成

        return PipelineStage(checkpoint.stage)

    def is_stage_completed(self, stage: PipelineStage) -> bool:
        """检查指定阶段是否已完成"""
        checkpoint = self.load_checkpoint()
        if checkpoint is None:
            return False

        # 如果检查点阶段 > 当前阶段，说明已完成（已进入下一阶段）
        if checkpoint.stage > stage.value:
            return True

        # 如果检查点阶段 == 当前阶段且 pipeline 已全部完成
        if checkpoint.stage == stage.value and checkpoint.completed:
            return True

        # 如果检查点阶段 > 当前阶段 且是当前阶段（说明已保存该阶段检查点）
        # 注意：对于非最终阶段，保存检查点即意味着该阶段已完成
        if checkpoint.stage == stage.value:
            # 检查是否是最终阶段（VIDEO_BURNING）
            if stage == PipelineStage.VIDEO_BURNING:
                return checkpoint.completed
            # 对于其他阶段，保存检查点即完成
            return True

        return False

    def get_stage_file_path(self, stage: PipelineStage) -> Optional[str]:
        """获取指定阶段的输出文件路径"""
        checkpoint = self.load_checkpoint()
        if checkpoint is None:
            return None

        filename = self.STAGE_FILES.get(stage)
        if filename is None:
            return None

        return os.path.join(self.output_dir, filename)

    def clear_checkpoint(self) -> None:
        """清除检查点"""
        if os.path.exists(self.checkpoint_path):
            try:
                os.remove(self.checkpoint_path)
                self._checkpoint = None
            except Exception as e:
                print(f"警告: 清除检查点失败: {e}")

    def get_progress(self) -> Dict[str, Any]:
        """
        获取当前进度

        Returns:
            进度信息字典
        """
        checkpoint = self.load_checkpoint()

        if checkpoint is None:
            return {
                "has_checkpoint": False,
                "progress_percent": 0,
                "current_stage": None,
                "completed_stages": [],
            }

        stages = list(PipelineStage)
        completed_stages = []

        for stage in stages:
            if self.is_stage_completed(stage):
                completed_stages.append(stage.name)

        current_stage = None
        if checkpoint.stage <= len(stages):
            try:
                current_stage = PipelineStage(checkpoint.stage).name
            except ValueError:
                current_stage = f"Unknown({checkpoint.stage})"

        progress_percent = (len(completed_stages) / len(stages)) * 100

        return {
            "has_checkpoint": True,
            "progress_percent": progress_percent,
            "current_stage": current_stage,
            "completed_stages": completed_stages,
            "last_update": checkpoint.timestamp,
            "completed": checkpoint.completed,
        }

    def should_skip_stage(self, stage: PipelineStage) -> bool:
        """
        判断是否应该跳过指定阶段

        Args:
            stage: 要检查的阶段

        Returns:
            True 如果该阶段已经完成且有输出文件
        """
        # 检查检查点
        if self.is_stage_completed(stage):
            return True

        # 检查输出文件是否存在
        file_path = self.get_stage_file_path(stage)
        if file_path and os.path.exists(file_path):
            return True

        return False

    def get_next_stage(self) -> Optional[PipelineStage]:
        """
        获取下一个需要执行的阶段

        Returns:
            下一个阶段的枚举值，如果没有待执行的阶段返回 None
        """
        checkpoint = self.load_checkpoint()

        if checkpoint is None:
            return PipelineStage.AUDIO_EXTRACTION

        if checkpoint.completed:
            return None  # 全部完成

        current_stage = PipelineStage(checkpoint.stage)
        stages = list(PipelineStage)

        # 找下一个未完成的阶段
        try:
            current_idx = stages.index(current_stage)
            for i in range(current_idx + 1, len(stages)):
                if not self.should_skip_stage(stages[i]):
                    return stages[i]
        except ValueError:
            pass

        return None

    def summarize(self) -> str:
        """获取进度摘要字符串"""
        progress = self.get_progress()

        if not progress["has_checkpoint"]:
            return "无检查点，从头开始"

        lines = [
            f"进度: {progress['progress_percent']:.0f}%",
            f"当前阶段: {progress['current_stage']}",
            f"已完成: {', '.join(progress['completed_stages']) or '无'}",
        ]

        if progress.get("completed"):
            lines.append("状态: 全部完成")

        return " | ".join(lines)


# 便捷函数
def load_progress(output_dir: str) -> Dict[str, Any]:
    """加载进度信息"""
    manager = CheckpointManager(output_dir)
    return manager.get_progress()


def clear_progress(output_dir: str) -> None:
    """清除进度信息"""
    manager = CheckpointManager(output_dir)
    manager.clear_checkpoint()


# 测试
if __name__ == "__main__":
    import tempfile

    # 创建临时目录测试
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CheckpointManager(tmpdir)

        print("=== 测试断点续传 ===\n")

        # 初始状态
        print("1. 初始状态:")
        print(f"   {manager.summarize()}\n")

        # 模拟阶段1完成
        manager.save_checkpoint(
            PipelineStage.AUDIO_EXTRACTION,
            "音频提取",
            data={"wav_path": os.path.join(tmpdir, "audio.wav")}
        )
        print("2. 阶段1完成:")
        print(f"   {manager.summarize()}\n")

        # 模拟阶段2完成
        manager.save_checkpoint(
            PipelineStage.SPEECH_RECOGNITION,
            "语音识别",
            data={"transcript_path": os.path.join(tmpdir, "raw_transcript.json")}
        )
        print("3. 阶段2完成:")
        print(f"   {manager.summarize()}\n")

        # 模拟阶段3进行中
        manager.save_checkpoint(
            PipelineStage.SEMANTIC_SPLITTING,
            "语义断句",
            data={"sentences_path": os.path.join(tmpdir, "sentences.json")}
        )
        print("4. 阶段3进行中:")
        print(f"   {manager.summarize()}\n")

        # 恢复后应该从阶段3继续
        manager2 = CheckpointManager(tmpdir)
        print("5. 重新加载:")
        print(f"   {manager2.summarize()}")
        print(f"   下一个阶段: {manager2.get_next_stage()}")
        print(f"   跳过阶段1: {manager2.should_skip_stage(PipelineStage.AUDIO_EXTRACTION)}")
        print(f"   跳过阶段2: {manager2.should_skip_stage(PipelineStage.SPEECH_RECOGNITION)}")
        print(f"   跳过阶段3: {manager2.should_skip_stage(PipelineStage.SEMANTIC_SPLITTING)}")
