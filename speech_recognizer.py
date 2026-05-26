"""
SubtitleForge - 语音识别模块
支持 faster-whisper 引擎，输出词级时间戳
"""
import os
import json
import time
from typing import List, Dict, Optional


class SpeechRecognizer:
    """
    语音识别引擎，当前基于 faster-whisper
    """
    
    SUPPORTED_MODELS = {
        "tiny":     {"vram": "~1GB",  "speed": "最快", "accuracy": "低"},
        "base":     {"vram": "~1GB",  "speed": "快",   "accuracy": "中"},
        "small":    {"vram": "~2GB",  "speed": "中",   "accuracy": "中高"},
        "medium":   {"vram": "~5GB",  "speed": "慢",   "accuracy": "高"},
        "large-v2": {"vram": "~10GB", "speed": "最慢", "accuracy": "最高"},
        "large-v3": {"vram": "~10GB", "speed": "最慢", "accuracy": "最高"},
    }
    
    # 本地模型路径映射
    LOCAL_MODEL_PATHS = {
        "base": r"C:\Users\aaa\.cache\huggingface\hub\Systran\faster-whisper-base",
    }
    
    def __init__(self, model_size="base", device="auto", compute_type="auto", model_path=None):
        """
        Args:
            model_size: 模型大小 (tiny/base/small/medium/large-v3)
            device: cuda / cpu / auto
            compute_type: float16 / int8 / auto
            model_path: 本地模型路径（优先于 model_size 从 HuggingFace 下载）
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model_path = model_path
        self.model = None
        
    def _load_model(self):
        """惰性加载模型，优先使用本地路径"""
        if self.model is not None:
            return
        
        from faster_whisper import WhisperModel
        
        # 确定模型路径
        load_path = self.model_path
        if not load_path:
            load_path = self.LOCAL_MODEL_PATHS.get(self.model_size)
        if not load_path:
            load_path = self.model_size  # 回退到 HuggingFace 在线下载
        
        print(f"加载 Whisper 模型: {load_path}")
        t0 = time.time()
        
        try:
            self.model = WhisperModel(
                load_path,
                device=self.device,
                compute_type=self.compute_type
            )
            elapsed = time.time() - t0
            print(f"模型加载完成，耗时 {elapsed:.1f} 秒")
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {e}\n请确保网络可连接 HuggingFace 以下载模型")
    
    def transcribe(self, audio_path: str, language=None, word_timestamps=True) -> Dict:
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径 (WAV/MP3/FLAC 等)
            language: 指定语言代码 (如 "en", "zh")，None 则自动检测
            word_timestamps: 是否返回词级时间戳
        
        Returns:
            {
                "language": "en",
                "duration_seconds": 120.5,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 3.2,
                        "text": "Hello world",
                        "words": [
                            {"word": "Hello", "start": 0.0, "end": 0.8, "probability": 0.98},
                            {"word": "world", "start": 1.0, "end": 2.5, "probability": 0.95}
                        ]
                    },
                    ...
                ],
                "full_text": "完整转录文本..."
            }
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        self._load_model()
        
        print(f"开始转录: {audio_path}")
        t0 = time.time()
        
        # 执行转录
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=word_timestamps,
            beam_size=5,
            vad_filter=True,  # 使用 VAD 过滤静音
        )
        
        # 收集结果
        result = {
            "language": info.language,
            "language_probability": info.language_probability,
            "duration_seconds": info.duration,
            "segments": []
        }
        
        full_text_parts = []
        
        for seg in segments:
            words = []
            if word_timestamps and seg.words:
                for w in seg.words:
                    words.append({
                        "word": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3)
                    })
            
            seg_data = {
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": words
            }
            result["segments"].append(seg_data)
            full_text_parts.append(seg.text.strip())
        
        result["full_text"] = " ".join(full_text_parts)
        
        elapsed = time.time() - t0
        print(f"转录完成！检测语言: {info.language} (置信度 {info.language_probability:.2f})")
        print(f"共 {len(result['segments'])} 个片段，耗时 {elapsed:.1f} 秒")
        
        return result
    
    def save_result(self, result: Dict, output_path: str):
        """保存转录结果为 JSON"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"转录结果已保存: {output_path}")
    
    @staticmethod
    def load_result(json_path: str) -> Dict:
        """加载转录结果"""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def test_recognizer():
    """测试语音识别"""
    audio_path = r"C:\Users\aaa\AppData\Roaming\Tencent\Marvis\User\ACFBDC35E50C8ADB5A927CC0C238E493\workspace\conv_19e59082374_8eb6a6d3ac46\temp\test_video.wav"
    output_dir = r"C:\Users\aaa\AppData\Roaming\Tencent\Marvis\User\ACFBDC35E50C8ADB5A927CC0C238E493\workspace\conv_19e59082374_8eb6a6d3ac46\temp"
    
    if not os.path.exists(audio_path):
        print(f"测试音频不存在: {audio_path}")
        return None
    
    # 使用 base 模型（轻量快速）
    recognizer = SpeechRecognizer(model_size="base", device="cpu")
    
    try:
        result = recognizer.transcribe(audio_path)
        
        # 保存
        json_path = os.path.join(output_dir, "transcript_result.json")
        recognizer.save_result(result, json_path)
        
        # 打印摘要
        print("\n=== 转录摘要 ===")
        print(f"语言: {result['language']}")
        print(f"片段数: {len(result['segments'])}")
        print(f"完整文本: {result['full_text'][:200]}...")
        
        return result
    except Exception as e:
        import traceback
        print(f"转录失败: {e}")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_recognizer()