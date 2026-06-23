#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SubtitleForge v2 - 配置管理模块单元测试"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as config_module


class TestConfigManagerInit(unittest.TestCase):
    """测试 ConfigManager 的初始化与默认配置加载"""

    def test_init_creates_config_dict(self):
        """测试初始化后 config 属性存在且为字典"""
        mgr = config_module.ConfigManager()
        self.assertIsInstance(mgr.config, dict)

    def test_default_sections_exist(self):
        """测试默认配置中各个 section 均存在"""
        mgr = config_module.ConfigManager()
        for key in ["api", "whisper", "translation", "subtitle"]:
            self.assertIn(key, mgr.config)

    def test_default_api_provider(self):
        """测试默认的 API provider 为 deepseek"""
        self.assertEqual(config_module.DEFAULT_CONFIG["api"]["provider"], "deepseek")

    def test_default_whisper_model(self):
        """测试默认的 Whisper 模型为 base"""
        self.assertEqual(config_module.DEFAULT_CONFIG["whisper"]["model"], "base")

    def test_default_translation_languages(self):
        """测试默认的翻译源语言和目标语言"""
        self.assertEqual(config_module.DEFAULT_CONFIG["translation"]["source_lang"], "ja")
        self.assertEqual(config_module.DEFAULT_CONFIG["translation"]["target_lang"], "zh")

    def test_default_font_sizes(self):
        """测试默认的字号配置"""
        self.assertEqual(config_module.DEFAULT_CONFIG["subtitle"]["zh_font_size"], 52)
        self.assertEqual(config_module.DEFAULT_CONFIG["subtitle"]["ja_font_size"], 44)


class TestValidateApiKey(unittest.TestCase):
    """测试 _validate_api_key 单项验证"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_valid_key(self):
        """测试有效的 API Key"""
        ok, msg = self.mgr._validate_api_key("sk-1234567890abcdefg", "deepseek")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_empty_key(self):
        """测试空字符串 API Key"""
        ok, msg = self.mgr._validate_api_key("", "deepseek")
        self.assertFalse(ok)
        self.assertIn("不能为空", msg)

    def test_none_key(self):
        """测试 None API Key"""
        ok, msg = self.mgr._validate_api_key(None, "deepseek")
        self.assertFalse(ok)

    def test_short_key(self):
        """测试长度过短的 API Key"""
        ok, msg = self.mgr._validate_api_key("short", "deepseek")
        self.assertFalse(ok)
        self.assertIn("长度过短", msg)

    def test_whitespace_only_key(self):
        """测试仅包含空白字符的 API Key"""
        ok, msg = self.mgr._validate_api_key("     ", "deepseek")
        self.assertFalse(ok)


class TestValidateWhisperModel(unittest.TestCase):
    """测试 _validate_whisper_model 单项验证"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_valid_model_base(self):
        """测试有效的模型 base"""
        ok, msg = self.mgr._validate_whisper_model("base")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_valid_model_large_v3(self):
        """测试有效的模型 large-v3"""
        ok, msg = self.mgr._validate_whisper_model("large-v3")
        self.assertTrue(ok)

    def test_invalid_model_name(self):
        """测试无效的模型名称"""
        ok, msg = self.mgr._validate_whisper_model("invalid-model")
        self.assertFalse(ok)
        self.assertIn("不在支持列表中", msg)

    def test_none_model(self):
        """测试 None 模型"""
        ok, msg = self.mgr._validate_whisper_model(None)
        self.assertFalse(ok)

    def test_empty_model(self):
        """测试空字符串模型"""
        ok, msg = self.mgr._validate_whisper_model("")
        self.assertFalse(ok)


class TestValidateDevice(unittest.TestCase):
    """测试 _validate_device 单项验证"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_valid_cpu(self):
        """测试有效的 cpu 设备"""
        ok, msg = self.mgr._validate_device("cpu")
        self.assertTrue(ok)

    def test_valid_cuda(self):
        """测试有效的 cuda 设备"""
        ok, msg = self.mgr._validate_device("cuda")
        self.assertTrue(ok)

    def test_valid_auto(self):
        """测试有效的 auto 设备"""
        ok, msg = self.mgr._validate_device("auto")
        self.assertTrue(ok)

    def test_invalid_device(self):
        """测试无效的设备名称"""
        ok, msg = self.mgr._validate_device("gpu")
        self.assertFalse(ok)

    def test_empty_device(self):
        """测试空字符串设备"""
        ok, msg = self.mgr._validate_device("")
        self.assertFalse(ok)


class TestValidateStyle(unittest.TestCase):
    """测试 _validate_style 单项验证"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_valid_anime(self):
        """测试有效的 anime 风格"""
        ok, msg = self.mgr._validate_style("anime")
        self.assertTrue(ok)

    def test_valid_drama(self):
        """测试有效的 drama 风格"""
        ok, msg = self.mgr._validate_style("drama")
        self.assertTrue(ok)

    def test_valid_youtube(self):
        """测试有效的 youtube 风格"""
        ok, msg = self.mgr._validate_style("youtube")
        self.assertTrue(ok)

    def test_valid_documentary(self):
        """测试有效的 documentary 风格"""
        ok, msg = self.mgr._validate_style("documentary")
        self.assertTrue(ok)

    def test_invalid_style(self):
        """测试无效的风格"""
        ok, msg = self.mgr._validate_style("invalid")
        self.assertFalse(ok)


class TestValidateFontSize(unittest.TestCase):
    """测试 _validate_font_size 边界值测试"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()
        self.min_val = config_module.FONT_SIZE_MIN
        self.max_val = config_module.FONT_SIZE_MAX

    def test_within_range(self):
        """测试范围内的字号"""
        ok, msg = self.mgr._validate_font_size(52)
        self.assertTrue(ok)

    def test_min_boundary(self):
        """测试最小边界值"""
        ok, msg = self.mgr._validate_font_size(self.min_val)
        self.assertTrue(ok)

    def test_max_boundary(self):
        """测试最大边界值"""
        ok, msg = self.mgr._validate_font_size(self.max_val)
        self.assertTrue(ok)

    def test_below_min(self):
        """测试小于最小值"""
        ok, msg = self.mgr._validate_font_size(self.min_val - 1)
        self.assertFalse(ok)
        self.assertIn("超出有效范围", msg)

    def test_above_max(self):
        """测试大于最大值"""
        ok, msg = self.mgr._validate_font_size(self.max_val + 1)
        self.assertFalse(ok)

    def test_non_integer_string(self):
        """测试非整数字符串"""
        ok, msg = self.mgr._validate_font_size("abc")
        self.assertFalse(ok)

    def test_none(self):
        """测试 None 值"""
        ok, msg = self.mgr._validate_font_size(None)
        self.assertFalse(ok)


class TestValidateLanguage(unittest.TestCase):
    """测试 _validate_language 单项验证"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_valid_ja(self):
        """测试有效的 ja"""
        ok, msg = self.mgr._validate_language("ja")
        self.assertTrue(ok)

    def test_valid_zh(self):
        """测试有效的 zh"""
        ok, msg = self.mgr._validate_language("zh")
        self.assertTrue(ok)

    def test_valid_three_chars(self):
        """测试 3 位字母代码"""
        ok, msg = self.mgr._validate_language("eng")
        self.assertTrue(ok)

    def test_empty(self):
        """测试空字符串"""
        ok, msg = self.mgr._validate_language("")
        self.assertFalse(ok)

    def test_numeric(self):
        """测试包含数字"""
        ok, msg = self.mgr._validate_language("j1")
        self.assertFalse(ok)

    def test_too_long(self):
        """测试过长的语言代码"""
        ok, msg = self.mgr._validate_language("japanese")
        self.assertFalse(ok)

    def test_whitespace(self):
        """测试仅空白字符的输入"""
        ok, msg = self.mgr._validate_language("   ")
        self.assertFalse(ok)


class TestValidateConfig(unittest.TestCase):
    """测试 validate_config 整体验证"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_empty_config_valid(self):
        """测试空字典 config 默认通过"""
        ok, errors = self.mgr.validate_config({})
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_good_config(self):
        """测试正确的完整配置"""
        cfg = {
            "api": {"deepseek_key": "sk-1234567890abcdefg"},
            "whisper": {"model": "base", "device": "cpu"},
            "translation": {"style": "anime", "source_lang": "ja", "target_lang": "zh"},
            "subtitle": {"zh_font_size": 52, "ja_font_size": 44},
        }
        ok, errors = self.mgr.validate_config(cfg)
        self.assertTrue(ok)
        self.assertEqual(errors, {})

    def test_bad_whisper_model(self):
        """测试错误 whisper 模型时报告错误"""
        cfg = {"whisper": {"model": "bad-model"}}
        ok, errors = self.mgr.validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("whisper.model", errors)

    def test_bad_font_size(self):
        """测试错误字号时报告错误"""
        cfg = {"subtitle": {"zh_font_size": 999}}
        ok, errors = self.mgr.validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("subtitle.zh_font_size", errors)

    def test_bad_style_and_language(self):
        """测试多个错误同时出现"""
        cfg = {
            "translation": {"style": "xx", "source_lang": "bad-lang"},
        }
        ok, errors = self.mgr.validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("translation.style", errors)
        self.assertIn("translation.source_lang", errors)

    def test_bad_api_key(self):
        """测试无效 API Key 会被报告"""
        cfg = {"api": {"deepseek_key": "short"}}
        ok, errors = self.mgr.validate_config(cfg)
        self.assertFalse(ok)
        self.assertIn("api.deepseek_key", errors)


class TestConfigGetSet(unittest.TestCase):
    """测试 get/set 配置值"""

    def setUp(self):
        self.mgr = config_module.ConfigManager()

    def test_get_existing_value(self):
        """测试获取已存在的值"""
        self.mgr.set("api.provider", "openai")
        self.assertEqual(self.mgr.get("api.provider"), "openai")

    def test_get_default_when_missing(self):
        """测试获取不存在的键返回默认值"""
        value = self.mgr.get("api.unknown.key", "default")
        self.assertEqual(value, "default")

    def test_get_nested_key(self):
        """测试嵌套点分路径"""
        self.mgr.set("a.b.c", 123)
        self.assertEqual(self.mgr.get("a.b.c"), 123)

    def test_set_overwrite(self):
        """测试 set 可以覆盖已有值"""
        self.mgr.set("whisper.model", "large-v3")
        self.assertEqual(self.mgr.get("whisper.model"), "large-v3")
        self.mgr.set("whisper.model", "base")
        self.assertEqual(self.mgr.get("whisper.model"), "base")

    def test_set_new_section(self):
        """测试 set 可以创建新的 section"""
        self.mgr.set("custom.field", "value")
        self.assertEqual(self.mgr.get("custom.field"), "value")


class TestConfigFileOperations(unittest.TestCase):
    """测试配置文件读写相关（使用临时目录，测试后清理）"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="subtitleforge_test_")
        self.orig_home = os.environ.get("HOME")
        self.orig_userprofile = os.environ.get("USERPROFILE")
        os.environ["HOME"] = self.test_dir
        os.environ["USERPROFILE"] = self.test_dir
        # 直接覆盖模块级 CONFIG_DIR / CONFIG_FILE，避免 Path.home() 已被缓存
        self._orig_config_dir = config_module.CONFIG_DIR
        self._orig_config_file = config_module.CONFIG_FILE
        # 保存并拷贝 DEFAULT_CONFIG，避免测试互相污染
        self._orig_default_config = config_module.DEFAULT_CONFIG
        config_module.DEFAULT_CONFIG = json.loads(json.dumps(self._orig_default_config))
        config_module.CONFIG_DIR = Path(self.test_dir) / ".subtitleforge"
        config_module.CONFIG_FILE = config_module.CONFIG_DIR / "config.json"

    def tearDown(self):
        config_module.CONFIG_DIR = self._orig_config_dir
        config_module.CONFIG_FILE = self._orig_config_file
        config_module.DEFAULT_CONFIG = self._orig_default_config
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if self.orig_home is not None:
            os.environ["HOME"] = self.orig_home
        else:
            os.environ.pop("HOME", None)
        if self.orig_userprofile is not None:
            os.environ["USERPROFILE"] = self.orig_userprofile
        else:
            os.environ.pop("USERPROFILE", None)

    def test_save_and_load_creates_file(self):
        """测试保存后配置文件存在"""
        mgr = config_module.ConfigManager()
        mgr.save()
        self.assertTrue(config_module.CONFIG_FILE.exists())

    def test_saved_file_is_valid_json(self):
        """测试保存的文件是合法 JSON"""
        mgr = config_module.ConfigManager()
        mgr.set("api.provider", "openai")
        mgr.save()
        with open(config_module.CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["api"]["provider"], "openai")

    def test_new_manager_reads_saved_config(self):
        """测试新创建的 ConfigManager 能够读取已保存的配置"""
        mgr1 = config_module.ConfigManager()
        mgr1.set("translation.style", "documentary")
        mgr1.save()
        mgr2 = config_module.ConfigManager()
        self.assertEqual(mgr2.get("translation.style"), "documentary")


if __name__ == "__main__":
    unittest.main()
