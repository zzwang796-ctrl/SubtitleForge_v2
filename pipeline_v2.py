#!/usr/bin/env python3
"""
SubtitleForge v2 - 升级版视频翻译流水线
集成上下文感知翻译 + 后处理润色的两阶段流水线

流程：音频提取 → 语音识别 → 断句 → 上下文感知翻译 → 后处理润色 → SRT/双语字幕生成
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass

# 添加模块路径
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from translator_v2 import ContextAwareTranslator, TranslationConfig, TranslationStyle
from post_processor import PostProcessor


class SubtitlePipelineV2:
    """SubtitleForge v2 升级版流水线"""
    
    def __init__(self, ffmpeg_path=None, whisper_model="base", device="cpu"):
        self.ffmpeg_path = ffmpeg_path
        self.whisper_model = whisper_model
        self.device = device
        
        # 自动查找 ffmpeg
        self._ffmpeg = self._find_ffmpeg()
    
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
        except:
            pass
        
        return "ffmpeg"
    
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
        
        recognizer = SpeechRecognizer(
            model_size=self.whisper_model,
            device=self.device,
            compute_type="int8" if self.device == "cpu" else "float16"
        )
        
        result = recognizer.transcribe(audio_path, language=language, word_timestamps=True)
        
        # 保存原始识别结果
        json_path = os.path.join(output_dir, "raw_transcript.json")
        recognizer.save_result(result, json_path)
        
        return result
    
    # ========== 阶段 3: 语义断句 ==========
    
    def split_sentences(self, transcript: Dict, output_dir: str) -> List[Dict]:
        """
        基于标点符号 + 停顿时长做语义断句
        规则：
        1. 优先按 .!?。！？ 等句末标点切分
        2. 无标点时，按停顿时长 >= 0.5s 切分
        3. 单句最长不超过 8 秒
        4. 合并过短的片段（< 0.5s）到相邻句子
        """
        segments = transcript.get("segments", [])
        if not segments:
            return []
        
        sentences = []
        current = {"start": None, "end": None, "text": "", "words": []}
        
        for seg in segments:
            text = seg["text"].strip()
            if not text:
                continue
            
            if current["start"] is None:
                current["start"] = seg["start"]
            
            if current["text"]:
                gap = seg["start"] - current["end"]
                prev_ends_with_punct = current["text"].rstrip().endswith(('.', '!', '?', '。', '！', '？'))
                current_too_long = (seg["end"] - current["start"]) > 8.0
                
                if prev_ends_with_punct or gap > 0.5 or current_too_long:
                    sentences.append(current)
                    current = {"start": seg["start"], "end": None, "text": "", "words": []}
            
            current["text"] += " " + text if current["text"] else text
            current["end"] = seg["end"]
            current["words"].extend(seg.get("words", []))
        
        if current["text"]:
            sentences.append(current)
        
        # 合并过短句
        merged = []
        for s in sentences:
            duration = s["end"] - s["start"]
            if duration < 0.5 and merged:
                prev = merged[-1]
                prev["text"] += " " + s["text"]
                prev["end"] = s["end"]
                prev["words"].extend(s["words"])
            else:
                merged.append(s)
        
        # 保存断句结果
        split_path = os.path.join(output_dir, "sentences.json")
        with open(split_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        
        print(f"断句完成: {len(segments)} 个原始片段 → {len(merged)} 个句子")
        
        return merged
    
    # ========== 阶段 4: 上下文感知翻译（v2 核心）==========
    
    def translate_subtitles_v2(
        self, 
        sentences: List[Dict],
        output_dir: str,
        api_key: str,
        style: str = "anime",
        provider: str = "deepseek",
        model: str = "deepseek-chat"
    ) -> List[Dict]:
        """
        使用上下文感知翻译器翻译字幕
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
            batch_size=10,
            context_window=3
        )
        
        translator = ContextAwareTranslator(config)
        translated = translator.translate_with_context(sentences)
        
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
    
    # ========== 阶段 6: SRT 字幕生成 ==========
    
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
        """秒数 → SRT 时间戳"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
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
        audio_path: str = None
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
        
        Returns:
            dict: 包含所有输出路径和处理结果
        """
        os.makedirs(output_dir, exist_ok=True)
        
        print("=" * 60)
        print("SubtitleForge v2 - 升级版流水线")
        print("=" * 60)
        print(f"视频: {video_path}")
        print(f"风格: {style}")
        print(f"源语言: {source_lang} → 目标语言: {target_lang}")
        print("=" * 60)
        
        result = {}
        
        # 阶段 1: 音频提取
        if not skip_audio:
            print("\n[阶段 1/6] 提取音频...")
            wav_path = self.extract_audio(video_path, output_dir)
        else:
            print("\n[阶段 1/6] 跳过音频提取（使用已有文件）")
            wav_path = audio_path or os.path.join(output_dir, "audio.wav")
        
        result["wav_path"] = wav_path
        print(f"  音频: {wav_path}")
        
        # 阶段 2: 语音识别
        print("\n[阶段 2/6] 语音识别...")
        transcript = self.recognize_speech(wav_path, output_dir, language=source_lang)
        result["transcript"] = transcript
        result["language"] = transcript.get("language", "unknown")
        print(f"  识别语言: {result['language']}")
        
        # 阶段 3: 语义断句
        print("\n[阶段 3/6] 语义断句...")
        sentences = self.split_sentences(transcript, output_dir)
        result["sentences_count"] = len(sentences)
        print(f"  句子数: {len(sentences)}")
        
        # 阶段 4: 上下文感知翻译（v2 核心）
        print("\n[阶段 4/6] 上下文感知翻译...")
        translated = self.translate_subtitles_v2(
            sentences, output_dir, api_key, style=style,
            provider=provider, model=model
        )
        result["translated_sentences"] = len(translated)
        
        # 阶段 5: 后处理润色
        print("\n[阶段 5/6] 后处理润色...")
        processed = self.post_process(translated, style=style)
        
        # 保存后处理结果
        processed_path = os.path.join(output_dir, "final_subtitles_v2.json")
        with open(processed_path, 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
        result["final_json"] = processed_path
        
        # 阶段 6: 生成 SRT 和导出文件
        print("\n[阶段 6/6] 生成字幕文件...")
        
        # 双语 SRT
        bilingual_srt = os.path.join(output_dir, "subtitle_bilingual_v2.srt")
        self.generate_srt(processed, bilingual_srt, True, True)
        result["bilingual_srt"] = bilingual_srt
        
        # 纯中文 SRT
        chinese_srt = os.path.join(output_dir, "subtitle_zh_v2.srt")
        self.generate_srt(processed, chinese_srt, False, True)
        result["chinese_srt"] = chinese_srt
        
        # 导出纯文本结果
        text_path = os.path.join(output_dir, "video_subtitle_result_v2.txt")
        self._export_text_result(processed, text_path, style)
        result["text_result"] = text_path
        
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