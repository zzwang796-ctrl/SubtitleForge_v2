#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SubtitleForge v2 - 自定义异常模块单元测试"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import exceptions


class TestSubtitleForgeErrorBase(unittest.TestCase):
    """测试 SubtitleForgeError 基类的基本功能"""

    def test_basic_construction(self):
        """测试基础构造和 message/detail 属性"""
        err = exceptions.SubtitleForgeError("测试错误", "测试详情")
        self.assertEqual(err.message, "测试错误")
        self.assertEqual(err.detail, "测试详情")

    def test_str_with_detail(self):
        """测试 __str__ 在包含 detail 时的输出"""
        err = exceptions.SubtitleForgeError("错误信息", "详细说明")
        s = str(err)
        self.assertIn("错误信息", s)
        self.assertIn("详细信息: 详细说明", s)

    def test_str_without_detail(self):
        """测试 __str__ 在不包含 detail 时的输出"""
        err = exceptions.SubtitleForgeError("简单错误")
        self.assertEqual(str(err), "简单错误")

    def test_isinstance_of_exception(self):
        """测试 SubtitleForgeError 是 Python Exception 的子类"""
        err = exceptions.SubtitleForgeError("x")
        self.assertIsInstance(err, Exception)


class TestConfigExceptions(unittest.TestCase):
    """测试配置相关异常类"""

    def test_config_error_inherits_base(self):
        """测试 ConfigError 继承 SubtitleForgeError"""
        err = exceptions.ConfigError("配置错误", "详情")
        self.assertIsInstance(err, exceptions.SubtitleForgeError)
        self.assertIsInstance(err, Exception)

    def test_api_key_missing_with_provider(self):
        """测试 APIKeyMissingError 带 provider 参数"""
        err = exceptions.APIKeyMissingError("DeepSeek")
        self.assertIn("DeepSeek", err.message)
        self.assertTrue(len(err.detail) > 0)

    def test_api_key_missing_without_provider(self):
        """测试 APIKeyMissingError 不带 provider 参数"""
        err = exceptions.APIKeyMissingError()
        self.assertIn("API Key", err.message)

    def test_invalid_config_value(self):
        """测试 InvalidConfigValueError 的 message 和 detail"""
        err = exceptions.InvalidConfigValueError("model", "bad-value", "应为 base/small/medium")
        self.assertIn("model", err.message)
        self.assertIn("bad-value", err.message)
        self.assertIn("应为", err.detail)

    def test_inheritance_api_key_missing(self):
        """测试 APIKeyMissingError 同时是 ConfigError 和 SubtitleForgeError"""
        err = exceptions.APIKeyMissingError("OpenAI")
        self.assertIsInstance(err, exceptions.ConfigError)
        self.assertIsInstance(err, exceptions.SubtitleForgeError)

    def test_inheritance_invalid_config_value(self):
        """测试 InvalidConfigValueError 的继承关系"""
        err = exceptions.InvalidConfigValueError("k", "v")
        self.assertIsInstance(err, exceptions.ConfigError)


class TestFileExceptions(unittest.TestCase):
    """测试文件与 IO 相关异常类"""

    def test_file_error_base(self):
        """测试 FileError 继承关系"""
        err = exceptions.FileError("文件错误", "详情")
        self.assertIsInstance(err, exceptions.SubtitleForgeError)

    def test_video_file_not_found(self):
        """测试 VideoFileNotFoundError 包含路径"""
        path = "/tmp/fake.mp4"
        err = exceptions.VideoFileNotFoundError(path)
        self.assertIn(path, err.message)
        self.assertTrue(len(err.detail) > 0)

    def test_invalid_video_file(self):
        """测试 InvalidVideoFileError"""
        err = exceptions.InvalidVideoFileError("test.txt")
        self.assertIn("test.txt", err.message)
        self.assertIsInstance(err, exceptions.FileError)

    def test_audio_extraction_error(self):
        """测试 AudioExtractionError 带和不带 detail"""
        err1 = exceptions.AudioExtractionError()
        self.assertIn("音频提取失败", err1.message)
        err2 = exceptions.AudioExtractionError("自定义详情")
        self.assertEqual(err2.detail, "自定义详情")

    def test_subtitle_file_error(self):
        """测试 SubtitleFileError 支持 action 参数"""
        err = exceptions.SubtitleFileError("/tmp/out.srt", "写入")
        self.assertIn("写入", err.message)
        self.assertIn("/tmp/out.srt", err.message)
        err2 = exceptions.SubtitleFileError("/tmp/in.srt")
        self.assertIn("读取", err2.message)


class TestTranslationExceptions(unittest.TestCase):
    """测试翻译 API 相关异常类"""

    def test_translation_error_base(self):
        """测试 TranslationError 继承关系"""
        err = exceptions.TranslationError("翻译错误", "详情")
        self.assertIsInstance(err, exceptions.SubtitleForgeError)

    def test_api_rate_limit_with_retry(self):
        """测试 APIRateLimitError 包含 retry_after"""
        err = exceptions.APIRateLimitError("DeepSeek", retry_after=30)
        self.assertEqual(err.retry_after, 30)
        self.assertIn("DeepSeek", err.message)
        self.assertIn("30", err.detail)

    def test_api_rate_limit_without_retry(self):
        """测试 APIRateLimitError 不带 retry_after"""
        err = exceptions.APIRateLimitError("OpenAI")
        self.assertEqual(err.retry_after, 0)
        self.assertIn("OpenAI", err.message)

    def test_api_authentication_error(self):
        """测试 APIAuthenticationError"""
        err = exceptions.APIAuthenticationError("DeepSeek")
        self.assertIn("DeepSeek", err.message)
        self.assertIsInstance(err, exceptions.TranslationError)

    def test_api_connection_error(self):
        """测试 APIConnectionError"""
        err = exceptions.APIConnectionError("DeepSeek", "网络超时")
        self.assertEqual(err.detail, "网络超时")
        err2 = exceptions.APIConnectionError("OpenAI")
        self.assertTrue(len(err2.detail) > 0)

    def test_api_response_parse_error(self):
        """测试 APIResponseParseError"""
        err = exceptions.APIResponseParseError("DeepSeek", "JSON 解析失败")
        self.assertIn("解析失败", err.message)
        self.assertEqual(err.detail, "JSON 解析失败")

    def test_api_timeout_error(self):
        """测试 APITimeoutError"""
        err = exceptions.APITimeoutError("DeepSeek", timeout=30.5)
        self.assertIn("30", err.detail)

    def test_translation_batch_error(self):
        """测试 TranslationBatchError 包含 batch_index"""
        err = exceptions.TranslationBatchError(batch_index=5)
        self.assertEqual(err.batch_index, 5)
        self.assertIn("5", err.message)
        self.assertIsInstance(err, exceptions.TranslationError)


class TestSpeechRecognitionExceptions(unittest.TestCase):
    """测试语音识别相关异常类"""

    def test_speech_recognition_error_base(self):
        """测试 SpeechRecognitionError 继承关系"""
        err = exceptions.SpeechRecognitionError("识别错误", "详情")
        self.assertIsInstance(err, exceptions.SubtitleForgeError)

    def test_whisper_model_error(self):
        """测试 WhisperModelError"""
        err = exceptions.WhisperModelError("large-v3")
        self.assertIn("large-v3", err.message)
        self.assertIsInstance(err, exceptions.SpeechRecognitionError)

    def test_audio_processing_error(self):
        """测试 AudioProcessingError"""
        err = exceptions.AudioProcessingError("FFmpeg 调用失败")
        self.assertEqual(err.detail, "FFmpeg 调用失败")
        err2 = exceptions.AudioProcessingError()
        self.assertTrue(len(err2.detail) > 0)

    def test_empty_transcript_error(self):
        """测试 EmptyTranscriptError"""
        err = exceptions.EmptyTranscriptError()
        self.assertIn("未检测到", err.message)
        self.assertTrue(len(err.detail) > 0)


class TestPipelineExceptions(unittest.TestCase):
    """测试流水线阶段相关异常类"""

    def test_pipeline_error_has_stage(self):
        """测试 PipelineError 包含 stage 属性"""
        err = exceptions.PipelineError("音频提取", "失败")
        self.assertEqual(err.stage, "音频提取")
        self.assertIn("[音频提取]", err.message)

    def test_subtitle_burn_error(self):
        """测试 SubtitleBurnError 的 stage 正确设置"""
        err = exceptions.SubtitleBurnError("FFmpeg 报错")
        self.assertEqual(err.stage, "字幕烧录")
        self.assertIsInstance(err, exceptions.PipelineError)
        self.assertIsInstance(err, exceptions.SubtitleForgeError)

    def test_checkpoint_error(self):
        """测试 CheckpointError 包含 action 属性"""
        err = exceptions.CheckpointError("保存", "磁盘已满")
        self.assertEqual(err.action, "保存")
        self.assertEqual(err.stage, "断点续传")
        self.assertIn("保存失败", err.message)


class TestExceptionInheritance(unittest.TestCase):
    """综合测试各异常类之间的继承关系"""

    def test_all_are_subtitle_forge_error(self):
        """测试所有具体异常都是 SubtitleForgeError 的子类"""
        err_classes = [
            exceptions.ConfigError,
            exceptions.APIKeyMissingError,
            exceptions.InvalidAPIKeyError,
            exceptions.InvalidConfigValueError,
            exceptions.FileError,
            exceptions.VideoFileNotFoundError,
            exceptions.InvalidVideoFileError,
            exceptions.AudioExtractionError,
            exceptions.SubtitleFileError,
            exceptions.TranslationError,
            exceptions.APIRateLimitError,
            exceptions.APIAuthenticationError,
            exceptions.APIConnectionError,
            exceptions.APIResponseParseError,
            exceptions.APITimeoutError,
            exceptions.TranslationBatchError,
            exceptions.SpeechRecognitionError,
            exceptions.WhisperModelError,
            exceptions.AudioProcessingError,
            exceptions.EmptyTranscriptError,
            exceptions.PipelineError,
            exceptions.SubtitleBurnError,
            exceptions.CheckpointError,
        ]
        for cls in err_classes:
            self.assertTrue(
                issubclass(cls, exceptions.SubtitleForgeError),
                f"{cls.__name__} 应该是 SubtitleForgeError 的子类",
            )

    def test_config_related_inheritance(self):
        """测试配置相关异常都属于 ConfigError"""
        self.assertTrue(issubclass(exceptions.APIKeyMissingError, exceptions.ConfigError))
        self.assertTrue(issubclass(exceptions.InvalidAPIKeyError, exceptions.ConfigError))
        self.assertTrue(issubclass(exceptions.InvalidConfigValueError, exceptions.ConfigError))

    def test_file_related_inheritance(self):
        """测试文件相关异常都属于 FileError"""
        self.assertTrue(issubclass(exceptions.VideoFileNotFoundError, exceptions.FileError))
        self.assertTrue(issubclass(exceptions.InvalidVideoFileError, exceptions.FileError))
        self.assertTrue(issubclass(exceptions.AudioExtractionError, exceptions.FileError))
        self.assertTrue(issubclass(exceptions.SubtitleFileError, exceptions.FileError))

    def test_translation_related_inheritance(self):
        """测试翻译相关异常都属于 TranslationError"""
        for cls in [
            exceptions.APIRateLimitError,
            exceptions.APIAuthenticationError,
            exceptions.APIConnectionError,
            exceptions.APIResponseParseError,
            exceptions.APITimeoutError,
            exceptions.TranslationBatchError,
        ]:
            self.assertTrue(
                issubclass(cls, exceptions.TranslationError),
                f"{cls.__name__} 应该是 TranslationError 的子类",
            )

    def test_speech_related_inheritance(self):
        """测试语音识别相关异常都属于 SpeechRecognitionError"""
        for cls in [
            exceptions.WhisperModelError,
            exceptions.AudioProcessingError,
            exceptions.EmptyTranscriptError,
        ]:
            self.assertTrue(
                issubclass(cls, exceptions.SpeechRecognitionError),
                f"{cls.__name__} 应该是 SpeechRecognitionError 的子类",
            )

    def test_pipeline_related_inheritance(self):
        """测试流水线相关异常都属于 PipelineError"""
        self.assertTrue(issubclass(exceptions.SubtitleBurnError, exceptions.PipelineError))
        self.assertTrue(issubclass(exceptions.CheckpointError, exceptions.PipelineError))

    def test_can_be_raised_and_caught(self):
        """测试异常可以被正常 raise 和 except"""
        try:
            raise exceptions.APIKeyMissingError("DeepSeek")
        except exceptions.ConfigError as e:
            self.assertIn("DeepSeek", str(e))
        try:
            raise exceptions.WhisperModelError("invalid-model")
        except exceptions.SubtitleForgeError:
            pass


if __name__ == "__main__":
    unittest.main()
