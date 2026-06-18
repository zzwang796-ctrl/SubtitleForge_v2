import subprocess
import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Optional, List, Tuple


class VideoProbe:
    """
    视频预检模块，使用 ffprobe 获取视频详细信息
    在处理前验证视频文件完整性
    """

    def __init__(self, ffprobe_path=None):
        """初始化视频探测器"""
        self.ffprobe = self._find_ffprobe(ffprobe_path)
        self.ffmpeg = self._find_ffmpeg(ffprobe_path)
        if not self.ffprobe:
            raise RuntimeError("未找到 ffprobe，请确保 ffmpeg 已正确安装")

    def _find_ffprobe(self, custom_path=None) -> Optional[str]:
        """查找 ffprobe 可执行文件"""
        if custom_path and os.path.exists(custom_path):
            return custom_path

        # 常见安装位置
        common_paths = [
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
            r"D:\ffmpeg\bin\ffprobe.exe",
            "ffprobe.exe",  # PATH 中查找
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        # 在 PATH 中查找
        try:
            result = subprocess.run(["where", "ffprobe"],
                                   capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass

        return None

    def _find_ffmpeg(self, custom_path=None) -> Optional[str]:
        """查找 ffmpeg 可执行文件"""
        if custom_path and os.path.exists(custom_path):
            return custom_path

        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"D:\ffmpeg\bin\ffmpeg.exe",
            "ffmpeg.exe",
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        try:
            result = subprocess.run(["where", "ffmpeg"],
                                   capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass

        return None

    def probe(self, video_path: str) -> Dict:
        """
        使用 ffprobe 探测视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            包含视频详细信息的字典
        """
        cmd = [
            self.ffprobe,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"视频探测失败: {e.stderr}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"视频信息解析失败: {e}")

    def validate(self, video_path: str) -> Tuple[bool, List[str]]:
        """
        验证视频文件完整性

        Args:
            video_path: 视频文件路径

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        # 检查文件是否存在
        if not os.path.exists(video_path):
            return False, [f"视频文件不存在: {video_path}"]

        # 检查文件是否为空
        file_size = os.path.getsize(video_path)
        if file_size == 0:
            return False, ["视频文件为空"]

        # 探测视频信息
        try:
            info = self.probe(video_path)
        except Exception as e:
            return False, [f"视频探测失败: {e}"]

        # 检查是否有视频流
        video_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
        if not video_streams:
            errors.append("未找到视频流")

        # 检查是否有音频流
        audio_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']
        if not audio_streams:
            errors.append("未找到音频流（无法提取字幕）")

        # 检查时长
        format_info = info.get('format', {})
        duration = float(format_info.get('duration', 0))
        if duration <= 0:
            errors.append("视频时长无效或为 0")

        # 检查文件大小是否与 format_size 一致
        format_size = int(format_info.get('size', 0))
        if format_size > 0 and abs(file_size - format_size) > 1024 * 1024:  # 差异超过 1MB
            errors.append(f"文件大小不匹配（实际: {file_size}, 头信息: {format_size}）")

        return len(errors) == 0, errors

    def get_summary(self, video_path: str) -> Dict:
        """
        获取视频信息摘要

        Returns:
            包含关键信息的字典
        """
        try:
            info = self.probe(video_path)
            format_info = info.get('format', {})

            # 提取视频流信息
            video_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
            audio_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']

            summary = {
                "filename": os.path.basename(video_path),
                "path": video_path,
                "file_size": os.path.getsize(video_path),
                "duration": float(format_info.get('duration', 0)),
                "format_name": format_info.get('format_name', 'unknown'),
                "has_video": len(video_streams) > 0,
                "has_audio": len(audio_streams) > 0,
            }

            if video_streams:
                vs = video_streams[0]
                summary["video_codec"] = vs.get('codec_name', 'unknown')
                summary["video_width"] = vs.get('width', 0)
                summary["video_height"] = vs.get('height', 0)
                summary["video_fps"] = self._parse_fps(vs.get('r_frame_rate', '0/1'))

            if audio_streams:
                as_ = audio_streams[0]
                summary["audio_codec"] = as_.get('codec_name', 'unknown')
                summary["audio_channels"] = as_.get('channels', 0)
                summary["audio_sample_rate"] = as_.get('sample_rate', 'unknown')

            return summary

        except Exception as e:
            return {"error": str(e)}

    def _parse_fps(self, fps_str: str) -> float:
        """解析帧率字符串 (如 '30000/1001')"""
        try:
            if '/' in fps_str:
                num, den = fps_str.split('/')
                return float(num) / float(den)
            return float(fps_str)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def print_summary(self, video_path: str) -> bool:
        """
        打印视频信息摘要并返回是否有效

        Returns:
            True 如果视频有效，False 否则
        """
        print(f"\n{'='*50}")
        print(f"视频预检: {os.path.basename(video_path)}")
        print('='*50)

        # 验证
        is_valid, errors = self.validate(video_path)

        if not is_valid:
            print("✗ 视频验证失败:")
            for error in errors:
                print(f"  - {error}")
            return False

        # 获取摘要
        summary = self.get_summary(video_path)

        if "error" in summary:
            print(f"✗ 获取视频信息失败: {summary['error']}")
            return False

        # 打印信息
        print(f"文件大小: {summary['file_size'] / 1024 / 1024:.2f} MB")
        print(f"时长: {summary['duration']:.1f} 秒 ({summary['duration']/60:.1f} 分钟)")
        print(f"格式: {summary['format_name']}")

        if summary.get('has_video'):
            print(f"视频: {summary['video_codec']} {summary['video_width']}x{summary['video_height']} @ {summary['video_fps']:.2f}fps")

        if summary.get('has_audio'):
            print(f"音频: {summary['audio_codec']} {summary['audio_channels']}ch {summary['audio_sample_rate']}Hz")

        print("✓ 视频验证通过")
        return True


class AudioExtractor:
    def __init__(self, ffmpeg_path=None):
        """初始化音频提取器，自动查找 ffmpeg"""
        self.ffmpeg = self._find_ffmpeg(ffmpeg_path)
        if not self.ffmpeg:
            raise RuntimeError("未找到 ffmpeg，请先安装 ffmpeg 并添加到 PATH")
        print(f"使用 ffmpeg: {self.ffmpeg}")
    
    def _find_ffmpeg(self, custom_path=None):
        """查找 ffmpeg 可执行文件"""
        # 1. 用户指定路径
        if custom_path and os.path.exists(custom_path):
            return custom_path
        
        # 2. 常见安装位置
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"D:\ffmpeg\bin\ffmpeg.exe",
            r"ffmpeg.exe",  # PATH 中查找
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        # 3. 在 PATH 中查找
        try:
            result = subprocess.run(["where", "ffmpeg"], 
                                  capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        
        return None
    
    def extract_audio(self, video_path, output_dir=None, sample_rate=16000, channels=1):
        """
        从视频中提取音频为 WAV 格式
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录（默认同目录）
            sample_rate: 采样率（默认 16kHz，适合语音识别）
            channels: 声道数（默认单声道）
        
        Returns:
            wav_path: 提取的音频文件路径
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 准备输出路径
        video_name = Path(video_path).stem
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            wav_path = os.path.join(output_dir, f"{video_name}.wav")
        else:
            wav_path = str(Path(video_path).with_suffix('.wav'))
        
        # ffmpeg 命令
        cmd = [
            self.ffmpeg,
            '-y',  # 覆盖输出文件
            '-i', video_path,
            '-vn',  # 不要视频
            '-acodec', 'pcm_s16le',  # PCM 16-bit 小端
            '-ar', str(sample_rate),  # 采样率
            '-ac', str(channels),  # 声道数
            '-f', 'wav',
            wav_path
        ]
        
        print(f"正在提取音频: {video_path} → {wav_path}")
        print(f"命令: {' '.join(cmd)}")
        
        try:
            # 执行提取
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"音频提取成功: {wav_path}")
            
            # 验证文件
            if os.path.exists(wav_path):
                size = os.path.getsize(wav_path)
                print(f"音频文件大小: {size:,} 字节 ({size/1024/1024:.2f} MB)")
                return wav_path
            else:
                raise RuntimeError("音频文件未生成")
                
        except subprocess.CalledProcessError as e:
            print(f"ffmpeg 错误: {e.stderr}")
            raise RuntimeError(f"音频提取失败: {e.stderr}")
    
    def get_audio_info(self, audio_path):
        """获取音频文件信息"""
        cmd = [
            self.ffmpeg,
            '-i', audio_path,
            '-hide_banner'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            # 解析输出
            for line in result.stderr.split('\n'):
                if 'Duration' in line:
                    print(f"音频信息: {line.strip()}")
                if 'Audio:' in line:
                    print(f"音频编码: {line.strip()}")
            return result.stderr
        except Exception as e:
            print(f"获取音频信息失败: {e}")
            return None
    
    def get_video_info(self, video_path):
        """获取视频信息（音轨数量等）"""
        cmd = [
            self.ffmpeg,
            '-i', video_path,
            '-hide_banner'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            # 解析音轨信息
            audio_streams = []
            lines = result.stderr.split('\n')
            for i, line in enumerate(lines):
                if 'Stream #0:' in line and 'Audio:' in line:
                    # 提取详细信息
                    stream_info = line.strip()
                    # 尝试获取下一行更多信息
                    if i+1 < len(lines) and 'Metadata:' in lines[i+1]:
                        stream_info += '\n' + lines[i+1].strip()
                    audio_streams.append(stream_info)
            
            if audio_streams:
                print(f"视频包含 {len(audio_streams)} 个音轨:")
                for stream in audio_streams:
                    print(f"  - {stream}")
            else:
                print("未找到音轨信息")
            
            return audio_streams
        except Exception as e:
            print(f"获取视频信息失败: {e}")
            return []


def test_extraction():
    """测试音频提取功能"""
    # 创建测试视频（使用 ffmpeg 生成一个测试视频）
    test_dir = "test_audio_extraction"
    os.makedirs(test_dir, exist_ok=True)
    
    # 生成一个 5 秒的测试视频
    test_video = os.path.join(test_dir, "test_video.mp4")
    if not os.path.exists(test_video):
        print("生成测试视频...")
        # 使用 ffmpeg 生成测试视频
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'lavfi',
            '-i', 'testsrc=duration=5:size=640x360:rate=30',
            '-f', 'lavfi',
            '-i', 'sine=frequency=440:duration=5',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            test_video
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True)
            print(f"测试视频已生成: {test_video}")
        except (subprocess.SubprocessError, OSError):
            print("无法生成测试视频，请手动准备一个视频文件")
            return None
    
    # 测试提取
    extractor = AudioExtractor()
    
    # 获取视频信息
    print("\n=== 视频信息 ===")
    extractor.get_video_info(test_video)
    
    # 提取音频
    print("\n=== 音频提取 ===")
    try:
        wav_path = extractor.extract_audio(test_video, test_dir)
        print(f"提取的音频: {wav_path}")
        
        # 获取音频信息
        print("\n=== 音频信息 ===")
        extractor.get_audio_info(wav_path)
        
        return wav_path
    except Exception as e:
        print(f"测试失败: {e}")
        return None


if __name__ == "__main__":
    print("=== SubtitleForge 音频提取模块测试 ===")
    
    # 检查 ffmpeg
    try:
        extractor = AudioExtractor()
        print("✓ ffmpeg 已找到")
    except RuntimeError as e:
        print(f"✗ {e}")
        print("请从 https://ffmpeg.org/download.html 下载 ffmpeg")
        print("或使用 winget install ffmpeg 安装")
        sys.exit(1)
    
    # 测试
    print("\n运行测试...")
    result = test_extraction()
    
    if result:
        print(f"\n✓ 音频提取模块测试成功！")
        print(f"音频文件: {result}")
    else:
        print("\n✗ 测试失败，请检查 ffmpeg 安装")