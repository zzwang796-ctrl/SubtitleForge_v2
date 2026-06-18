#!/usr/bin/env python3
"""
SubtitleForge v2 - 升级版视频翻译流水线
集成上下文感知翻译 + 后处理润色的两阶段流水线

流程：音频提取 → 语音识别 → 断句 → 上下文感知翻译 → 后处理润色 → SRT/双语字幕生成 → 字幕烧录
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Union, Callable
from dataclasses import dataclass

# 添加模块路径
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from translator_v2 import ContextAwareTranslator, TranslationConfig, TranslationStyle
from post_processor import PostProcessor


class SubtitlePipelineV2:
    """SubtitleForge v2 升级版流水线"""
    
    def __init__(self, ffmpeg_path=None, whisper_model="large-v3", device="cpu", compute_type="int8"):
        self.ffmpeg_path = ffmpeg_path
        self.whisper_model = whisper_model
        self.device = device
        self.compute_type = compute_type
        
        # 自动查找 ffmpeg
        self._ffmpeg = self._find_ffmpeg()
        
        # 检查点管理器（延迟初始化）
        self._checkpoint_manager = None
        self._checkpoint_enabled = False
        self._current_output_dir = None
    
    def _find_ffmpeg(self):
        """查找 ffmpeg"""
        if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
            return self.ffmpeg_path
        
        # 搜索项目目录下的 ffmpeg
        local_ffmpeg = os.path.join(MODULE_DIR, "ffmpeg", "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
        
        # PATH 中查找
        try:
            result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        
        return "ffmpeg"
    
    def _init_checkpoint(self, output_dir: str, enabled: bool = True):
        """初始化检查点管理器"""
        if not enabled:
            self._checkpoint_manager = None
            self._checkpoint_enabled = False
            return
        
        try:
            from checkpoint import CheckpointManager
            self._checkpoint_manager = CheckpointManager(output_dir)
            self._checkpoint_enabled = True
            self._current_output_dir = output_dir
            
            # 加载现有检查点
            progress = self._checkpoint_manager.get_progress()
            if progress["has_checkpoint"]:
                print(f"  [检查点] 发现已有进度: {self._checkpoint_manager.summarize()}")
        except ImportError:
            print("  [检查点] 检查点模块不可用，断点续传已禁用")
            self._checkpoint_manager = None
            self._checkpoint_enabled = False
    
    def _save_checkpoint(self, stage, stage_name: str, data: Dict = None):
        """保存检查点"""
        if not self._checkpoint_enabled or self._checkpoint_manager is None:
            return
        
        try:
            from checkpoint import PipelineStage
            stage_enum = PipelineStage[stage_name.upper()] if isinstance(stage_name, str) else stage
            self._checkpoint_manager.save_checkpoint(stage_enum, stage_name, data=data)
        except Exception as e:
            print(f"  [检查点] 保存失败: {e}")
    
    def _should_skip_stage(self, stage_name: str) -> bool:
        """检查是否应该跳过指定阶段"""
        if not self._checkpoint_enabled or self._checkpoint_manager is None:
            return False
        
        try:
            from checkpoint import PipelineStage
            stage_enum = PipelineStage[stage_name.upper()]
            return self._checkpoint_manager.should_skip_stage(stage_enum)
        except Exception:
            return False

    # ========== 阶段 1: 音频提取 ==========
    
    def extract_audio(self, video_path: str, output_dir: str) -> str:
        """从视频提取音频"""
        from audio_extractor import AudioExtractor
        
        os.makedirs(output_dir, exist_ok=True)
        
        extractor = AudioExtractor(self._ffmpeg)
        wav_path = extractor.extract_audio(
            video_path,
            output_dir=output_dir,
            sample_rate=16000,
            channels=1
        )
        
        return wav_path
    
    # ========== 阶段 2: 语音识别 ==========
    
    def recognize_speech(self, audio_path: str, output_dir: str, language=None) -> Dict:
        """语音转文字"""
        from speech_recognizer import SpeechRecognizer
        
        # 如果 whisper_model 是存在的本地目录路径，直接用作 model_path
        model_kwargs = dict(
            model_size=self.whisper_model,
            device=self.device,
            compute_type=self.compute_type
        )
        if os.path.isdir(self.whisper_model):
            model_kwargs["model_path"] = self.whisper_model
        
        recognizer = SpeechRecognizer(**model_kwargs)
        
        result = recognizer.transcribe(audio_path, language=language, word_timestamps=True)
        
        # 保存原始识别结果
        json_path = os.path.join(output_dir, "raw_transcript.json")
        recognizer.save_result(result, json_path)
        
        return result
    
    # ========== 阶段 3: 语义断句 ==========
    
    def split_sentences(self, transcript: Dict, output_dir: str) -> List[Dict]:
        """
        基于 Whisper 词级时间戳做语义断句（v2 重写）

        核心规则：
        1. 遇到句末标点（. ! ? 。！？）立即断句
        2. 词间停顿时长 >= 0.2s + 停顿后不是接续词（が、けど、から、ので、て、で、と、に、は、も）时断句
        3. 累计时长 >= 6s 强制断句（在最近的标点或停顿处）
        4. 最终不允许 > 8s 的句子
        5. 过短片段（< 0.3s）后向合并到下一个句子
        """
        segments = transcript.get("segments", [])
        if not segments:
            return []

        # 从 segments 中提取所有词级时间戳
        all_words = []
        for seg in segments:
            words = seg.get("words", [])
            if words:
                all_words.extend(words)

        if not all_words:
            # 降级：无词级时间戳时回退到 segment 级切分
            return self._split_sentences_fallback(transcript, output_dir)

        SENTENCE_ENDS = {'.', '!', '?', '。', '！', '？'}
        CONTINUATIVES = {'が', 'けど', 'から', 'ので', 'て', 'で', 'と', 'に', 'は', 'も'}
        MAX_DURATION = 6.0       # 累计 6s 强制断句
        HARD_LIMIT = 8.0         # 绝对不允许超过
        PAUSE_THRESHOLD = 0.2    # 词间停顿时长阈值
        SHORT_MERGE = 0.3        # 短句合并阈值

        # 第一阶段：按规则逐词切分
        raw_sentences = []
        current_words = []
        current_start = None

        for i, w in enumerate(all_words):
            word_text = w.get("word", "").strip()
            word_start = w.get("start", 0.0)
            word_end = w.get("end", word_start + 0.1)

            if not word_text:
                continue

            if current_start is None:
                current_start = word_start

            should_split = False

            if current_words:
                # 规则 1: 句末标点 —— 前一词以句末标点结尾则断句
                prev_text = current_words[-1].get("word", "").strip()
                if prev_text and any(prev_text.endswith(c) for c in SENTENCE_ENDS):
                    should_split = True

                # 规则 2: 停顿 >= 0.2s 且下一词不是接续词
                if not should_split:
                    gap = word_start - current_words[-1].get("end", word_start)
                    if gap >= PAUSE_THRESHOLD and word_text not in CONTINUATIVES:
                        should_split = True

                # 规则 3: 累计时长 >= 6s 强制断句
                if not should_split:
                    cumulative = word_end - current_start
                    if cumulative >= MAX_DURATION:
                        should_split = True

            if should_split and current_words:
                seg_end = current_words[-1].get("end", current_words[-1].get("start", 0) + 0.1)
                seg_text = "".join(w.get("word", "") for w in current_words)
                raw_sentences.append({
                    "start": current_start,
                    "end": seg_end,
                    "text": seg_text,
                    "words": current_words
                })
                current_words = [w]
                current_start = word_start
            else:
                current_words.append(w)

        # 收尾
        if current_words:
            seg_end = current_words[-1].get("end", current_words[-1].get("start", 0) + 0.1)
            seg_text = "".join(w.get("word", "") for w in current_words)
            raw_sentences.append({
                "start": current_start,
                "end": seg_end,
                "text": seg_text,
                "words": current_words
            })

        # 第二阶段：硬限制 — 不允许 > 8s 的句子
        def _dur(s): return s["end"] - s["start"]

        limited = []
        for s in raw_sentences:
            dur = _dur(s)
            if dur > HARD_LIMIT:
                words = s.get("words", [])
                # 在累计 6s 附近找最近的标点或停顿切割点
                cut_target = s["start"] + MAX_DURATION
                best_cut = None
                for j, w in enumerate(words):
                    w_end = w.get("end", 0)
                    if w_end >= cut_target and best_cut is None:
                        best_cut = j  # 至少在此处断开
                    w_text = w.get("word", "").strip()
                    if w_text and any(w_text.endswith(c) for c in SENTENCE_ENDS) and w_end <= cut_target + 1.0:
                        best_cut = j + 1  # 标点处优先

                if best_cut is not None and 0 < best_cut < len(words):
                    part1 = words[:best_cut]
                    part2 = words[best_cut:]
                    if part1 and part2:
                        limited.append({
                            "start": s["start"],
                            "end": part1[-1].get("end", cut_target),
                            "text": "".join(w.get("word", "") for w in part1),
                            "words": part1
                        })
                        limited.append({
                            "start": part2[0].get("start", cut_target),
                            "end": s["end"],
                            "text": "".join(w.get("word", "") for w in part2),
                            "words": part2
                        })
                        continue
                # 无合适切分点，在中间硬切
                mid_idx = len(words) // 2
                if mid_idx > 0:
                    part1 = words[:mid_idx]
                    part2 = words[mid_idx:]
                    limited.append({
                        "start": s["start"],
                        "end": part1[-1].get("end", s["start"] + dur / 2),
                        "text": "".join(w.get("word", "") for w in part1),
                        "words": part1
                    })
                    limited.append({
                        "start": part2[0].get("start", s["start"] + dur / 2),
                        "end": s["end"],
                        "text": "".join(w.get("word", "") for w in part2),
                        "words": part2
                    })
                else:
                    limited.append(s)
            else:
                limited.append(s)

        # 第三阶段：合并过短句（< 0.3s）到后一句
        final = []
        i = 0
        while i < len(limited):
            s = limited[i]
            dur = _dur(s)
            if dur < SHORT_MERGE and i + 1 < len(limited):
                nxt = limited[i + 1]
                nxt["text"] = s["text"] + nxt["text"]
                nxt["start"] = s["start"]
                nxt["words"] = s["words"] + nxt["words"]
                final.append(nxt)
                i += 2
            else:
                final.append(s)
                i += 1

        # 保存断句结果
        split_path = os.path.join(output_dir, "sentences.json")
        with open(split_path, 'w', encoding='utf-8') as f:
            json.dump(final, f, ensure_ascii=False, indent=2)

        # 打印时长分布统计
        durations = [_dur(s) for s in final]
        total_dur = sum(durations)
        avg_dur = total_dur / len(durations) if durations else 0
        max_dur = max(durations) if durations else 0
        min_dur = min(durations) if durations else 0

        buckets = {"<1s": 0, "1-3s": 0, "3-5s": 0, "5-7s": 0, "7-8s": 0, ">8s": 0}
        for d in durations:
            if d < 1.0:     buckets["<1s"] += 1
            elif d < 3.0:   buckets["1-3s"] += 1
            elif d < 5.0:   buckets["3-5s"] += 1
            elif d < 7.0:   buckets["5-7s"] += 1
            elif d <= 8.0:  buckets["7-8s"] += 1
            else:           buckets[">8s"] += 1

        print(f"断句完成: {len(all_words)} 个词 → {len(final)} 个句子")
        print(f"时长统计: 总={total_dur:.1f}s  平均={avg_dur:.1f}s  最短={min_dur:.1f}s  最长={max_dur:.1f}s")
        print(f"分布: " + " | ".join(f"{k}: {v}" for k, v in buckets.items() if v > 0))

        return final

    def _split_sentences_fallback(self, transcript: Dict, output_dir: str) -> List[Dict]:
        """降级方案：无词级时间戳时使用 segment 级切分"""
        segments = transcript.get("segments", [])
        if not segments:
            return []

        SENTENCE_ENDS = {'.', '!', '?', '。', '！', '？'}
        MAX_SENTENCE_DURATION = 6.0
        SILENCE_GAP = 0.3
        SHORT_MERGE = 0.4
        HARD_LIMIT = 10.0

        raw_sentences = []
        current = {"start": None, "end": None, "text": "", "words": []}

        for seg in segments:
            text = seg["text"].strip()
            if not text:
                continue

            if current["start"] is None:
                current["start"] = seg["start"]

            should_split = False
            if current["text"]:
                gap = seg["start"] - current["end"]
                prev_ends = current["text"].rstrip()
                prev_has_end = any(prev_ends.endswith(c) for c in SENTENCE_ENDS)
                potential_dur = seg["end"] - current["start"]

                if prev_has_end:
                    should_split = True
                elif gap >= SILENCE_GAP:
                    should_split = True
                elif potential_dur >= MAX_SENTENCE_DURATION:
                    should_split = True

            if should_split:
                raw_sentences.append(current)
                current = {"start": seg["start"], "end": None, "text": "", "words": []}

            current["text"] += " " + text if current["text"] else text
            current["end"] = seg["end"]
            current["words"].extend(seg.get("words", []))

        if current["text"]:
            raw_sentences.append(current)

        def _dur(s): return s["end"] - s["start"]

        merged = []
        for s in raw_sentences:
            dur = _dur(s)
            if dur < SHORT_MERGE and merged:
                prev = merged[-1]
                prev["text"] += " " + s["text"]
                prev["end"] = s["end"]
                prev["words"].extend(s["words"])
            else:
                merged.append(s)

        merged2 = []
        i = 0
        while i < len(merged):
            s = merged[i]
            dur = _dur(s)
            if dur < SHORT_MERGE and i + 1 < len(merged):
                nxt = merged[i + 1]
                nxt["text"] = s["text"] + " " + nxt["text"]
                nxt["start"] = s["start"]
                nxt["words"] = s["words"] + nxt["words"]
                merged2.append(nxt)
                i += 2
            else:
                merged2.append(s)
                i += 1

        final = []
        for s in merged2:
            dur = _dur(s)
            if dur > HARD_LIMIT:
                words = s.get("words", [])
                if words:
                    cut_point = s["start"] + 6.0
                    part1_words = [w for w in words if w.get("start", 0) < cut_point]
                    part2_words = [w for w in words if w.get("start", 0) >= cut_point]
                    if part1_words and part2_words:
                        final.append({
                            "start": s["start"],
                            "end": part1_words[-1].get("end", cut_point),
                            "text": " ".join(w.get("word", "") for w in part1_words),
                            "words": part1_words
                        })
                        final.append({
                            "start": part2_words[0].get("start", cut_point),
                            "end": s["end"],
                            "text": " ".join(w.get("word", "") for w in part2_words),
                            "words": part2_words
                        })
                        continue
                mid = s["start"] + dur / 2
                final.append({
                    "start": s["start"], "end": mid,
                    "text": s["text"][:len(s["text"]) // 2], "words": []
                })
                final.append({
                    "start": mid, "end": s["end"],
                    "text": s["text"][len(s["text"]) // 2:], "words": []
                })
            else:
                final.append(s)

        split_path = os.path.join(output_dir, "sentences.json")
        with open(split_path, 'w', encoding='utf-8') as f:
            json.dump(final, f, ensure_ascii=False, indent=2)

        durations = [_dur(s) for s in final]
        total_dur = sum(durations)
        avg_dur = total_dur / len(durations) if durations else 0
        max_dur = max(durations) if durations else 0
        min_dur = min(durations) if durations else 0

        buckets = {"<1s": 0, "1-3s": 0, "3-5s": 0, "5-7s": 0, "7-10s": 0, ">10s": 0}
        for d in durations:
            if d < 1.0:    buckets["<1s"] += 1
            elif d < 3.0:  buckets["1-3s"] += 1
            elif d < 5.0:  buckets["3-5s"] += 1
            elif d < 7.0:  buckets["5-7s"] += 1
            elif d <= 10.0: buckets["7-10s"] += 1
            else:          buckets[">10s"] += 1

        print(f"断句完成(降级): {len(segments)} 个原始片段 → {len(final)} 个句子")
        print(f"时长统计: 总={total_dur:.1f}s  平均={avg_dur:.1f}s  最短={min_dur:.1f}s  最长={max_dur:.1f}s")
        print(f"分布: " + " | ".join(f"{k}: {v}" for k, v in buckets.items() if v > 0))

        return final
    
    # ========== 阶段 4: 上下文感知翻译（v2 核心）==========
    
    def translate_subtitles_v2(
        self,
        sentences: List[Dict],
        output_dir: str,
        api_key: str,
        style: str = "anime",
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        temperature: float = 0.4,
        batch_size: int = 8,
        context_window: int = 5,
        target_language: str = "zh-CN",
        progress_callback=None
    ) -> List[Dict]:
        """
        使用上下文感知翻译器翻译字幕

        Args:
            progress_callback: 进度回调函数，签名: callback(current_batch, total_batches, current_text)
        """
        # 映射风格
        style_map = {
            "anime": TranslationStyle.ANIME,
            "drama": TranslationStyle.DRAMA,
            "youtube": TranslationStyle.YOUTUBE,
            "documentary": TranslationStyle.DOCUMENTARY,
        }
        
        config = TranslationConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            style=style_map.get(style, TranslationStyle.ANIME),
            temperature=temperature,
            batch_size=batch_size,
            context_window=context_window,
            target_language=target_language,
        )

        translator = ContextAwareTranslator(config)
        translated = translator.translate_with_context(sentences, progress_callback=progress_callback)

        # 保存翻译结果
        json_path = os.path.join(output_dir, "translated_sentences_v2.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)
        
        print(f"翻译完成，已保存: {json_path}")
        
        return translated
    
    # ========== 阶段 5: 后处理润色 ==========
    
    def post_process(self, sentences: List[Dict], style: str = "anime") -> List[Dict]:
        """后处理：去AI味、口语化、连贯性检查"""
        processor = PostProcessor(style=style)
        processed = processor.process(sentences)
        
        print(f"后处理完成，共处理 {len(processed)} 句")
        
        return processed
    
    # ========== 阶段 6: 翻译校对（二次精翻）==========
    
    def refine_translations(self, sentences: List[Dict], api_key: str,
                            provider: str = "deepseek", model: str = "deepseek-chat",
                            style: str = "anime") -> List[Dict]:
        """调用上下文感知翻译器的二次精翻校对"""
        style_map = {
            "anime": TranslationStyle.ANIME,
            "drama": TranslationStyle.DRAMA,
            "youtube": TranslationStyle.YOUTUBE,
            "documentary": TranslationStyle.DOCUMENTARY,
        }
        config = TranslationConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            style=style_map.get(style, TranslationStyle.ANIME),
        )
        translator = ContextAwareTranslator(config)
        refined = translator.refine_translations(sentences, api_key, provider=provider, model=model, style=style)
        print(f"翻译校对完成，共处理 {len(refined)} 句")
        return refined
    
    # ========== 阶段 7: SRT 字幕生成 ==========
    
    def generate_srt(self, sentences: List[Dict], output_path: str,
                     include_original: bool = True, include_translation: bool = True) -> str:
        """生成 SRT 字幕文件（支持双语）"""
        lines = []
        
        for i, sent in enumerate(sentences):
            lines.append(str(i + 1))
            
            start_ts = self._format_timestamp(sent["start"])
            end_ts = self._format_timestamp(sent["end"])
            lines.append(f"{start_ts} --> {end_ts}")
            
            # 字幕文本
            text_parts = []
            if include_original and sent.get("text"):
                text_parts.append(sent["text"].strip())
            if include_translation and sent.get("translated_text"):
                text_parts.append(sent["translated_text"].strip())
            
            lines.append("\n".join(text_parts))
            lines.append("")
        
        srt_content = "\n".join(lines)
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        print(f"SRT 已生成: {output_path} ({len(sentences)} 条字幕)")
        
        return output_path
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """秒数 → SRT 时间戳 (HH:MM:SS,mmm)"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        # 使用 round() 避免浮点数精度问题，如 0.999 * 1000 = 999.999
        ms = int(round((seconds % 1) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    # ========== 完整流水线 ==========
    
    def run_full_pipeline(
        self,
        video_path: str,
        output_dir: str,
        api_key: str,
        source_lang: str = "ja",
        target_lang: str = "zh",
        style: str = "anime",
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        skip_audio: bool = False,
        audio_path: str = None,
        skip_burn: bool = False,
        enable_checkpoint: bool = True,
    ) -> Dict:
        """
        一键执行完整升级版流水线

        Args:
            video_path: 视频路径
            output_dir: 输出目录
            api_key: DeepSeek/OpenAI API Key
            source_lang: 源语言（默认 ja）
            target_lang: 目标语言（默认 zh）
            style: 翻译风格 (anime/drama/youtube/documentary)
            provider: API 提供商 (deepseek/openai)
            model: 模型名称
            skip_audio: 跳过音频提取（如果有已有WAV文件）
            audio_path: 已有音频路径
            skip_burn: 跳过字幕烧录
            enable_checkpoint: 启用断点续传（默认 True）

        Returns:
            dict: 包含所有输出路径和处理结果
        """
        os.makedirs(output_dir, exist_ok=True)

        # 初始化检查点
        self._init_checkpoint(output_dir, enable_checkpoint)

        print("=" * 60)
        print("SubtitleForge v2 - 升级版流水线")
        print("=" * 60)
        print(f"视频: {video_path}")
        print(f"风格: {style}")
        print(f"源语言: {source_lang} → 目标语言: {target_lang}")
        print(f"断点续传: {'启用' if self._checkpoint_enabled else '禁用'}")
        print("=" * 60)

        result = {}

        # 阶段 1: 音频提取
        if self._should_skip_stage("AUDIO_EXTRACTION"):
            print("\n[阶段 1/8] 跳过音频提取（已有检查点）")
            wav_path = os.path.join(output_dir, "audio.wav")
            if not os.path.exists(wav_path):
                wav_path = audio_path or wav_path
        elif not skip_audio:
            print("\n[阶段 1/8] 提取音频...")
            wav_path = self.extract_audio(video_path, output_dir)
            self._save_checkpoint(None, "AUDIO_EXTRACTION", {"wav_path": wav_path})
        else:
            print("\n[阶段 1/8] 跳过音频提取（用户请求）")
            wav_path = audio_path or os.path.join(output_dir, "audio.wav")

        result["wav_path"] = wav_path
        print(f"  音频: {wav_path}")

        # 阶段 2: 语音识别
        if self._should_skip_stage("SPEECH_RECOGNITION"):
            print("\n[阶段 2/8] 跳过语音识别（已有检查点）")
            transcript_path = os.path.join(output_dir, "raw_transcript.json")
            if os.path.exists(transcript_path):
                from speech_recognizer import SpeechRecognizer
                transcript = SpeechRecognizer.load_result(transcript_path)
            else:
                transcript = self.recognize_speech(wav_path, output_dir, language=source_lang)
        else:
            print("\n[阶段 2/8] 语音识别...")
            transcript = self.recognize_speech(wav_path, output_dir, language=source_lang)
            self._save_checkpoint(None, "SPEECH_RECOGNITION", {"transcript_path": os.path.join(output_dir, "raw_transcript.json")})

        result["transcript"] = transcript
        result["language"] = transcript.get("language", "unknown")
        print(f"  识别语言: {result['language']}")

        # 阶段 3: 语义断句
        if self._should_skip_stage("SEMANTIC_SPLITTING"):
            print("\n[阶段 3/8] 跳过语义断句（已有检查点）")
            sentences_path = os.path.join(output_dir, "sentences.json")
            if os.path.exists(sentences_path):
                with open(sentences_path, 'r', encoding='utf-8') as f:
                    sentences = json.load(f)
            else:
                sentences = self.split_sentences(transcript, output_dir)
        else:
            print("\n[阶段 3/8] 语义断句...")
            sentences = self.split_sentences(transcript, output_dir)
            self._save_checkpoint(None, "SEMANTIC_SPLITTING", {"sentences_path": os.path.join(output_dir, "sentences.json")})

        result["sentences_count"] = len(sentences)
        print(f"  句子数: {len(sentences)}")

        # 阶段 4: 上下文感知翻译（v2 核心）
        if self._should_skip_stage("TRANSLATION"):
            print("\n[阶段 4/8] 跳过翻译（已有检查点）")
            translated_path = os.path.join(output_dir, "translated.json")
            if os.path.exists(translated_path):
                with open(translated_path, 'r', encoding='utf-8') as f:
                    translated = json.load(f)
            else:
                translated = self.translate_subtitles_v2(
                    sentences, output_dir, api_key, style=style,
                    provider=provider, model=model
                )
        else:
            print("\n[阶段 4/8] 上下文感知翻译...")
            translated = self.translate_subtitles_v2(
                sentences, output_dir, api_key, style=style,
                provider=provider, model=model
            )
            self._save_checkpoint(None, "TRANSLATION", {"translated_path": os.path.join(output_dir, "translated.json")})

        result["translated_sentences"] = len(translated)

        # 阶段 5: 后处理润色
        if self._should_skip_stage("POST_PROCESSING"):
            print("\n[阶段 5/8] 跳过后处理润色（已有检查点）")
            processed_path = os.path.join(output_dir, "final_subtitles_v2.json")
            if os.path.exists(processed_path):
                with open(processed_path, 'r', encoding='utf-8') as f:
                    processed = json.load(f)
            else:
                processed = self.post_process(translated, style=style)
        else:
            print("\n[阶段 5/8] 后处理润色...")
            processed = self.post_process(translated, style=style)

            # 保存后处理结果
            processed_path = os.path.join(output_dir, "final_subtitles_v2.json")
            with open(processed_path, 'w', encoding='utf-8') as f:
                json.dump(processed, f, ensure_ascii=False, indent=2)
            self._save_checkpoint(None, "POST_PROCESSING", {"processed_path": processed_path})

        result["final_json"] = processed_path

        # 阶段 6: 翻译校对（二次精翻）
        if self._should_skip_stage("REFINEMENT"):
            print("\n[阶段 6/8] 跳过翻译校对（已有检查点）")
            refined_path = os.path.join(output_dir, "refined_subtitles.json")
            if os.path.exists(refined_path):
                with open(refined_path, 'r', encoding='utf-8') as f:
                    refined = json.load(f)
            else:
                refined = self.refine_translations(processed, api_key, provider=provider, model=model, style=style)
        else:
            print("\n[阶段 6/8] 翻译校对...")
            refined = self.refine_translations(processed, api_key, provider=provider, model=model, style=style)

            # 保存校对结果
            refined_path = os.path.join(output_dir, "refined_subtitles.json")
            with open(refined_path, 'w', encoding='utf-8') as f:
                json.dump(refined, f, ensure_ascii=False, indent=2)
            self._save_checkpoint(None, "REFINEMENT", {"refined_path": refined_path})

        result["refined_json"] = refined_path

        # 阶段 7: 生成 SRT 和导出文件
        if self._should_skip_stage("SUBTITLE_EXPORT"):
            print("\n[阶段 7/8] 跳过字幕生成（已有检查点）")
            bilingual_srt = os.path.join(output_dir, "subtitle_bilingual_v2.srt")
            chinese_srt = os.path.join(output_dir, "subtitle_zh_v2.srt")
            text_path = os.path.join(output_dir, "video_subtitle_result_v2.txt")
        else:
            print("\n[阶段 7/8] 生成字幕文件...")

            # 双语 SRT
            bilingual_srt = os.path.join(output_dir, "subtitle_bilingual_v2.srt")
            self.generate_srt(refined, bilingual_srt, True, True)
            result["bilingual_srt"] = bilingual_srt

            # 纯中文 SRT
            chinese_srt = os.path.join(output_dir, "subtitle_zh_v2.srt")
            self.generate_srt(refined, chinese_srt, False, True)
            result["chinese_srt"] = chinese_srt

            # 导出纯文本结果
            text_path = os.path.join(output_dir, "video_subtitle_result_v2.txt")
            self._export_text_result(refined, text_path, style)
            self._save_checkpoint(None, "SUBTITLE_EXPORT", {
                "bilingual_srt": bilingual_srt,
                "chinese_srt": chinese_srt,
                "text_path": text_path
            })

        result["bilingual_srt"] = bilingual_srt
        result["chinese_srt"] = chinese_srt
        result["text_result"] = text_path

        # 阶段 8: 字幕烧录到视频
        if self._should_skip_stage("VIDEO_BURNING"):
            print("\n[阶段 8/8] 跳过字幕烧录（已有检查点）")
            video_output = os.path.join(output_dir, "video_with_subtitles.mp4")
            if os.path.exists(video_output):
                result["video_with_subtitles"] = video_output
        elif not skip_burn:
            print("\n[阶段 8/8] 字幕烧录到视频...")
            video_output = self.burn_subtitles(video_path, bilingual_srt, output_dir)
            self._save_checkpoint(None, "VIDEO_BURNING", {"video_output": video_output}, completed=True)
            result["video_with_subtitles"] = video_output
        else:
            print("\n[阶段 8/8] 跳过字幕烧录（用户请求）")

        print("\n" + "=" * 60)
        print("流水线执行完成！")
        print("=" * 60)
        for key, value in result.items():
            print(f"  {key}: {value}")

        return result
    
    def _export_text_result(self, sentences: List[Dict], output_path: str, style: str):
        """导出纯文本翻译结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"SubtitleForge v2 翻译结果\n")
            f.write(f"风格: {style}\n")
            f.write("=" * 40 + "\n\n")
            for i, s in enumerate(sentences):
                jp = s.get("text", "")
                zh = s.get("translated_text", "")
                ts = s.get("start", 0)
                te = s.get("end", 0)
                f.write(f"[{i+1}] {ts:.1f}s-{te:.1f}s\n")
                f.write(f"    日文: {jp}\n")
                f.write(f"    中文: {zh}\n\n")
        
        print(f"纯文本结果已保存: {output_path}")
    
    # ========== 阶段 8: 字幕烧录 ==========
    
    def burn_subtitles(self, video_path: str, bilingual_srt: str, output_dir: str,
                       zh_font_size: int = 52, jp_font_size: int = 44,
                       font_name: str = "Microsoft YaHei") -> str:
        """
        将双语字幕烧录到视频中

        使用 FFmpeg 的 subtitles 滤镜直接烧录 SRT 格式，
        而不是转换为 ASS 格式，以确保字幕时间戳完全对齐。
        """
        print("\n[阶段 8/8] 字幕烧录到视频...")

        # SRT 格式字幕可以直接使用 FFmpeg 的 subtitles 滤镜烧录
        # 这样可以保证时间戳完全对齐，不会出现 ASS 格式的延迟问题
        output_video = os.path.join(output_dir, "video_with_subtitles.mp4")

        # 转义 SRT 路径中的特殊字符
        srt_escaped = bilingual_srt.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

        # 使用 subtitles 滤镜直接烧录 SRT
        cmd = [
            self._ffmpeg, '-i', video_path,
            '-vf', f"subtitles='{srt_escaped}'",
            '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
            '-c:a', 'aac', '-b:a', '192k',
            '-y', output_video
        ]

        print(f"  执行: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            print(f"  FFmpeg 错误:\n{result.stderr}")
            raise RuntimeError(f"字幕烧录失败: {result.stderr}")

        print(f"  字幕已烧录到视频: {output_video}")
        return output_video
    
    # ========== 兼容旧版接口 ==========
    
    def run(self, video_path, output_dir, source_lang=None):
        """兼容旧版 run() 接口（仅生成SRT，不翻译）"""
        os.makedirs(output_dir, exist_ok=True)
        
        print("=" * 60)
        print(f"开始处理视频: {video_path}")
        print("=" * 60)
        
        print("\n[1/4] 提取音频...")
        wav_path = self.extract_audio(video_path, output_dir)
        
        print("\n[2/4] 语音识别...")
        transcript = self.recognize_speech(wav_path, output_dir, language=source_lang)
        
        print("\n[3/4] 语义断句...")
        sentences = self.split_sentences(transcript, output_dir)
        
        print("\n[4/4] 生成 SRT 字幕...")
        srt_path = os.path.join(output_dir, "subtitle.srt")
        self.generate_srt(sentences, srt_path, True, False)
        
        print("\n" + "=" * 60)
        print("流水线执行完成！")
        print(f"  SRT 字幕: {srt_path}")
        print("=" * 60)
        
        return {
            "wav_path": wav_path,
            "transcript": transcript,
            "sentences": sentences,
            "srt_path": srt_path
        }


def main():
    """测试流水线"""
    print("SubtitleForge v2 流水线测试")
    print("请通过 main_v2.py 运行完整测试")


if __name__ == "__main__":
    main()