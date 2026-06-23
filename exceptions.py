#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SubtitleForge v2 - 自定义异常模块

提供统一的异常层级，便于精确错误处理和用户友好的提示。
"""


class SubtitleForgeError(Exception):
    """SubtitleForge 所有异常的基类"""
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.message}\n详细信息: {self.detail}"
        return self.message


# ===== 配置与验证相关异常 =====

class ConfigError(SubtitleForgeError):
    """配置错误基类"""
    pass


class APIKeyMissingError(ConfigError):
    """API Key 缺失"""
    def __init__(self, provider: str = ""):
        msg = f"{provider} API Key 为空" if provider else "API Key 为空"
        detail = "请在设置中填写有效的 API Key，或通过环境变量 DEEPSEEK_API_KEY/OPENAI_API_KEY 配置"
        super().__init__(msg, detail)


class InvalidAPIKeyError(ConfigError):
    """API Key 格式无效"""
    def __init__(self, provider: str = ""):
        msg = f"{provider} API Key 格式不正确" if provider else "API Key 格式不正确"
        detail = "请检查 API Key 是否正确复制，不要包含多余的空格或换行"
        super().__init__(msg, detail)


class InvalidConfigValueError(ConfigError):
    """配置值无效"""
    def __init__(self, key: str, value: str, expected: str = ""):
        msg = f"配置项 '{key}' 的值无效: {value}"
        detail = expected if expected else "请检查配置值是否在允许范围内"
        super().__init__(msg, detail)


# ===== 文件与IO相关异常 =====

class FileError(SubtitleForgeError):
    """文件操作错误基类"""
    pass


class VideoFileNotFoundError(FileError):
    """视频文件不存在"""
    def __init__(self, path: str):
        msg = f"视频文件不存在: {path}"
        detail = "请确认文件路径是否正确，以及文件是否被移动或删除"
        super().__init__(msg, detail)


class InvalidVideoFileError(FileError):
    """不是有效的视频文件"""
    def __init__(self, path: str):
        msg = f"不是有效的视频文件: {path}"
        detail = "请确认文件格式为 MP4、AVI、MKV、MOV 等常见视频格式"
        super().__init__(msg, detail)


class AudioExtractionError(FileError):
    """音频提取失败"""
    def __init__(self, detail: str = ""):
        msg = "音频提取失败"
        detail = detail or "请检查 FFmpeg 是否正确安装，以及视频文件是否完整"
        super().__init__(msg, detail)


class SubtitleFileError(FileError):
    """字幕文件操作失败"""
    def __init__(self, path: str, action: str = "读取"):
        msg = f"字幕文件{action}失败: {path}"
        detail = "请检查文件权限和磁盘空间"
        super().__init__(msg, detail)


# ===== 翻译API相关异常 =====

class TranslationError(SubtitleForgeError):
    """翻译错误基类"""
    pass


class APIRateLimitError(TranslationError):
    """API 限流"""
    def __init__(self, provider: str, retry_after: int = 0):
        msg = f"{provider} API 请求过于频繁，已触发限流"
        detail = f"建议等待 {retry_after} 秒后重试，或稍后再试" if retry_after > 0 else "请稍后重试"
        super().__init__(msg, detail)
        self.retry_after = retry_after


class APIAuthenticationError(TranslationError):
    """API 认证失败"""
    def __init__(self, provider: str):
        msg = f"{provider} API 认证失败"
        detail = "请检查 API Key 是否正确，是否过期，以及账户是否有足够余额"
        super().__init__(msg, detail)


class APIConnectionError(TranslationError):
    """API 连接失败"""
    def __init__(self, provider: str, detail: str = ""):
        msg = f"无法连接到 {provider} API"
        detail = detail or "请检查网络连接是否正常，以及 API 服务是否可用"
        super().__init__(msg, detail)


class APIResponseParseError(TranslationError):
    """API 响应解析失败"""
    def __init__(self, provider: str, detail: str = ""):
        msg = f"{provider} API 返回结果解析失败"
        detail = detail or "API 返回的内容格式不符合预期，已尝试重试但仍失败"
        super().__init__(msg, detail)


class APITimeoutError(TranslationError):
    """API 请求超时"""
    def __init__(self, provider: str, timeout: float = 0):
        msg = f"{provider} API 请求超时"
        detail = f"在 {timeout:.0f} 秒内未收到响应，网络可能不稳定或服务端处理较慢" if timeout > 0 else "请检查网络连接"
        super().__init__(msg, detail)


class TranslationBatchError(TranslationError):
    """批次翻译失败"""
    def __init__(self, batch_index: int, detail: str = ""):
        msg = f"第 {batch_index} 批翻译失败"
        detail = detail or "将尝试以单句降级模式继续处理"
        super().__init__(msg, detail)
        self.batch_index = batch_index


# ===== 语音识别相关异常 =====

class SpeechRecognitionError(SubtitleForgeError):
    """语音识别错误基类"""
    pass


class WhisperModelError(SpeechRecognitionError):
    """Whisper 模型加载失败"""
    def __init__(self, model_name: str, detail: str = ""):
        msg = f"Whisper 模型加载失败: {model_name}"
        detail = detail or "请确认模型文件存在且完整，或使用更小的模型（base/small）"
        super().__init__(msg, detail)


class AudioProcessingError(SpeechRecognitionError):
    """音频处理失败"""
    def __init__(self, detail: str = ""):
        msg = "音频文件处理失败"
        detail = detail or "音频格式可能不支持，或文件已损坏"
        super().__init__(msg, detail)


class EmptyTranscriptError(SpeechRecognitionError):
    """识别结果为空"""
    def __init__(self):
        msg = "语音识别未检测到任何语音内容"
        detail = "可能原因：视频为纯音乐/静音，或音频质量过低导致无法识别"
        super().__init__(msg, detail)


# ===== 流水线阶段异常 =====

class PipelineError(SubtitleForgeError):
    """流水线阶段错误基类"""
    def __init__(self, stage: str, message: str, detail: str = ""):
        msg = f"[{stage}] {message}"
        super().__init__(msg, detail)
        self.stage = stage


class SubtitleBurnError(PipelineError):
    """字幕烧录失败"""
    def __init__(self, detail: str = ""):
        super().__init__("字幕烧录", "FFmpeg 字幕烧录失败", detail)


class CheckpointError(PipelineError):
    """断点续传错误"""
    def __init__(self, action: str, detail: str = ""):
        super().__init__("断点续传", f"{action}失败", detail)
        self.action = action
