#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SubtitleForge v2 - 配置管理模块
支持多来源配置：
1. 命令行参数（最高优先级）
2. 环境变量
3. ~/.subtitleforge/config.json
4. .env 文件
5. 默认值（最低优先级）
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v1",
    "large-v2",
    "large-v3",
]
SUPPORTED_DEVICES = ["cpu", "cuda", "auto"]
SUPPORTED_STYLES = ["anime", "drama", "youtube", "documentary"]
FONT_SIZE_MIN = 20
FONT_SIZE_MAX = 100

# 配置目录
CONFIG_DIR = Path.home() / ".subtitleforge"
CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_FILE = Path.cwd() / ".env"

# 默认配置
DEFAULT_CONFIG = {
    "api": {
        "deepseek_key": "",
        "openai_key": "",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.4,
        "max_tokens": 3000,
        "batch_size": 8,
        "context_window": 5,
    },
    "whisper": {
        "model": "base",
        "device": "cpu",
        "compute_type": "auto",
        "model_path": "",
    },
    "translation": {
        "source_lang": "ja",
        "target_lang": "zh",
        "style": "anime",
    },
    "subtitle": {
        "zh_font_size": 52,
        "ja_font_size": 44,
        "font_name": "Microsoft YaHei",
    },
    "output": {
        "directory": "",
    },
}


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置（多层级优先级）"""
        config = DEFAULT_CONFIG.copy()
        
        # 1. 加载 JSON 配置文件
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    config = self._deep_merge(config, file_config)
            except Exception as e:
                print(f"警告: 读取配置文件失败: {e}")
        
        # 2. 加载 .env 文件
        if ENV_FILE.exists():
            env_config = self._load_env_file()
            config = self._deep_merge(config, env_config)
        
        # 3. 加载环境变量
        env_config = self._load_env_vars()
        config = self._deep_merge(config, env_config)
        
        return config
    
    def _load_env_file(self) -> Dict[str, Any]:
        """加载 .env 文件"""
        env_config = {}
        try:
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        env_config = self._set_nested_key(env_config, key, value)
        except Exception as e:
            print(f"警告: 读取 .env 文件失败: {e}")
        return env_config
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        env_config = {}
        prefix = "SUBTITLEFORGE_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                env_config = self._set_nested_key(env_config, config_key, value)
        
        # 兼容旧的环境变量名
        if "DEEPSEEK_API_KEY" in os.environ:
            env_config["api"] = env_config.get("api", {})
            env_config["api"]["deepseek_key"] = os.environ["DEEPSEEK_API_KEY"]
        
        if "OPENAI_API_KEY" in os.environ:
            env_config["api"] = env_config.get("api", {})
            env_config["api"]["openai_key"] = os.environ["OPENAI_API_KEY"]
        
        return env_config
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并配置"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _set_nested_key(self, config: Dict, key: str, value: Any) -> Dict:
        """设置嵌套键值"""
        parts = key.split('_')
        current = config
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = value
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点分隔路径）"""
        parts = key.split('.')
        current = self.config
        try:
            for part in parts:
                current = current[part]
            return current
        except KeyError:
            return default
    
    def set(self, key: str, value: Any):
        """设置配置值（支持点分隔路径）"""
        parts = key.split('.')
        current = self.config
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = value
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
    
    def save(self):
        """保存配置到文件"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """获取指定提供商的 API Key"""
        if provider == "deepseek":
            return self.get("api.deepseek_key")
        elif provider == "openai":
            return self.get("api.openai_key")
        return None
    
    def set_api_key(self, provider: str, key: str):
        """设置指定提供商的 API Key"""
        if provider == "deepseek":
            self.set("api.deepseek_key", key)
        elif provider == "openai":
            self.set("api.openai_key", key)

    def _validate_api_key(self, api_key: str, provider: str) -> Tuple[bool, str]:
        if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
            return False, f"API Key ({provider}) 不能为空"
        key = api_key.strip()
        if len(key) < 10:
            return False, f"API Key ({provider}) 长度过短"
        if key.isspace():
            return False, f"API Key ({provider}) 仅包含空白字符"
        return True, ""

    def _validate_whisper_model(self, model: str) -> Tuple[bool, str]:
        if not model or not isinstance(model, str):
            return False, "Whisper 模型名称无效"
        if model not in SUPPORTED_MODELS:
            return False, f"Whisper 模型 '{model}' 不在支持列表中: {SUPPORTED_MODELS}"
        return True, ""

    def _validate_device(self, device: str) -> Tuple[bool, str]:
        if not device or not isinstance(device, str):
            return False, "设备名称无效"
        if device not in SUPPORTED_DEVICES:
            return False, f"设备 '{device}' 不在支持列表中: {SUPPORTED_DEVICES}"
        return True, ""

    def _validate_style(self, style: str) -> Tuple[bool, str]:
        if not style or not isinstance(style, str):
            return False, "风格名称无效"
        if style not in SUPPORTED_STYLES:
            return False, f"风格 '{style}' 不在支持列表中: {SUPPORTED_STYLES}"
        return True, ""

    def _validate_font_size(self, size: int, min_val: int = FONT_SIZE_MIN, max_val: int = FONT_SIZE_MAX) -> Tuple[bool, str]:
        try:
            size_int = int(size)
        except (TypeError, ValueError):
            return False, f"字号 '{size}' 不是有效整数"
        if size_int < min_val or size_int > max_val:
            return False, f"字号 {size_int} 超出有效范围 [{min_val}, {max_val}]"
        return True, ""

    def _validate_language(self, lang: str) -> Tuple[bool, str]:
        if not lang or not isinstance(lang, str):
            return False, "语言代码无效"
        lang_code = lang.strip()
        if not lang_code.isalpha() or not (2 <= len(lang_code) <= 3):
            return False, f"语言代码 '{lang_code}' 格式不正确（应为 2-3 位字母）"
        return True, ""

    def validate_config(self, config_dict: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        errors = {}

        api = config_dict.get("api", {})
        provider = api.get("provider", "")
        deepseek_key = api.get("deepseek_key", "")
        openai_key = api.get("openai_key", "")
        if deepseek_key:
            ok, msg = self._validate_api_key(deepseek_key, "deepseek")
            if not ok:
                errors["api.deepseek_key"] = msg
        if openai_key:
            ok, msg = self._validate_api_key(openai_key, "openai")
            if not ok:
                errors["api.openai_key"] = msg

        whisper = config_dict.get("whisper", {})
        whisper_model = whisper.get("model")
        if whisper_model is not None:
            ok, msg = self._validate_whisper_model(whisper_model)
            if not ok:
                errors["whisper.model"] = msg
        device = whisper.get("device")
        if device is not None:
            ok, msg = self._validate_device(device)
            if not ok:
                errors["whisper.device"] = msg

        translation = config_dict.get("translation", {})
        style = translation.get("style")
        if style is not None:
            ok, msg = self._validate_style(style)
            if not ok:
                errors["translation.style"] = msg
        source_lang = translation.get("source_lang")
        if source_lang:
            ok, msg = self._validate_language(source_lang)
            if not ok:
                errors["translation.source_lang"] = msg
        target_lang = translation.get("target_lang")
        if target_lang:
            ok, msg = self._validate_language(target_lang)
            if not ok:
                errors["translation.target_lang"] = msg

        subtitle = config_dict.get("subtitle", {})
        zh_font_size = subtitle.get("zh_font_size")
        if zh_font_size is not None:
            ok, msg = self._validate_font_size(zh_font_size)
            if not ok:
                errors["subtitle.zh_font_size"] = msg
        ja_font_size = subtitle.get("ja_font_size")
        if ja_font_size is not None:
            ok, msg = self._validate_font_size(ja_font_size)
            if not ok:
                errors["subtitle.ja_font_size"] = msg

        return len(errors) == 0, errors

    # ============================================================
    # GUI 配置持久化
    # ============================================================

    def load_gui_config(self) -> Dict[str, Any]:
        """
        加载 GUI 配置

        Returns:
            GUI 配置字典，包含以下键：
            - provider: 翻译引擎
            - model: 模型名称
            - whisper_model: Whisper 模型
            - whisper_model_path: Whisper 本地模型路径
            - style: 翻译风格
            - zh_font_size: 中文字号
            - ja_font_size: 日文字号
            - font_name: 字体名称
            - device: 设备类型
        """
        defaults = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "whisper_model": "base",
            "whisper_model_path": "",
            "style": "anime",
            "zh_font_size": 52,
            "ja_font_size": 44,
            "font_name": "Microsoft YaHei",
            "device": "cpu",
        }

        cfg = {
            "provider": self.get("api.provider", defaults["provider"]),
            "model": self.get("api.model", defaults["model"]),
            "whisper_model": self.get("whisper.model", defaults["whisper_model"]),
            "whisper_model_path": self.get("whisper.model_path", defaults["whisper_model_path"]),
            "style": self.get("translation.style", defaults["style"]),
            "zh_font_size": self.get("subtitle.zh_font_size", defaults["zh_font_size"]),
            "ja_font_size": self.get("subtitle.ja_font_size", defaults["ja_font_size"]),
            "font_name": self.get("subtitle.font_name", defaults["font_name"]),
            "device": self.get("whisper.device", defaults["device"]),
        }

        valid_cfg = dict(cfg)

        ok, msg = self._validate_whisper_model(cfg["whisper_model"])
        if not ok:
            logger.warning(f"加载配置验证失败 - whisper_model: {msg}，使用默认值 '{defaults['whisper_model']}'")
            valid_cfg["whisper_model"] = defaults["whisper_model"]

        ok, msg = self._validate_device(cfg["device"])
        if not ok:
            logger.warning(f"加载配置验证失败 - device: {msg}，使用默认值 '{defaults['device']}'")
            valid_cfg["device"] = defaults["device"]

        ok, msg = self._validate_style(cfg["style"])
        if not ok:
            logger.warning(f"加载配置验证失败 - style: {msg}，使用默认值 '{defaults['style']}'")
            valid_cfg["style"] = defaults["style"]

        ok, msg = self._validate_font_size(cfg["zh_font_size"])
        if not ok:
            logger.warning(f"加载配置验证失败 - zh_font_size: {msg}，使用默认值 {defaults['zh_font_size']}")
            valid_cfg["zh_font_size"] = defaults["zh_font_size"]

        ok, msg = self._validate_font_size(cfg["ja_font_size"])
        if not ok:
            logger.warning(f"加载配置验证失败 - ja_font_size: {msg}，使用默认值 {defaults['ja_font_size']}")
            valid_cfg["ja_font_size"] = defaults["ja_font_size"]

        return valid_cfg

    def save_gui_config(
        self,
        provider: str = None,
        model: str = None,
        whisper_model: str = None,
        whisper_model_path: str = None,
        style: str = None,
        zh_font_size: int = None,
        ja_font_size: int = None,
        font_name: str = None,
        device: str = None,
        api_key: str = None,
        api_provider: str = None,
    ):
        """
        保存 GUI 配置

        Args:
            provider: 翻译引擎
            model: 模型名称
            whisper_model: Whisper 模型
            whisper_model_path: Whisper 本地模型路径
            style: 翻译风格
            zh_font_size: 中文字号
            ja_font_size: 日文字号
            font_name: 字体名称
            device: 设备类型
            api_key: API Key
            api_provider: API Key 对应的提供商
        """
        validation_has_error = False

        if whisper_model is not None:
            ok, msg = self._validate_whisper_model(whisper_model)
            if not ok:
                logger.warning(f"保存配置验证失败 - whisper_model: {msg}")
                validation_has_error = True
                whisper_model = None

        if device is not None:
            ok, msg = self._validate_device(device)
            if not ok:
                logger.warning(f"保存配置验证失败 - device: {msg}")
                validation_has_error = True
                device = None

        if style is not None:
            ok, msg = self._validate_style(style)
            if not ok:
                logger.warning(f"保存配置验证失败 - style: {msg}")
                validation_has_error = True
                style = None

        if zh_font_size is not None:
            ok, msg = self._validate_font_size(zh_font_size)
            if not ok:
                logger.warning(f"保存配置验证失败 - zh_font_size: {msg}")
                validation_has_error = True
                zh_font_size = None

        if ja_font_size is not None:
            ok, msg = self._validate_font_size(ja_font_size)
            if not ok:
                logger.warning(f"保存配置验证失败 - ja_font_size: {msg}")
                validation_has_error = True
                ja_font_size = None

        if api_key is not None and api_provider is not None:
            ok, msg = self._validate_api_key(api_key, api_provider)
            if not ok:
                logger.warning(f"保存配置验证失败 - api_key: {msg}")
                validation_has_error = True
                api_key = None

        if provider is not None:
            self.set("api.provider", provider)
        if model is not None:
            self.set("api.model", model)
        if whisper_model is not None:
            self.set("whisper.model", whisper_model)
        if whisper_model_path is not None:
            self.set("whisper.model_path", whisper_model_path)
        if style is not None:
            self.set("translation.style", style)
        if zh_font_size is not None:
            self.set("subtitle.zh_font_size", zh_font_size)
        if ja_font_size is not None:
            self.set("subtitle.ja_font_size", ja_font_size)
        if font_name is not None:
            self.set("subtitle.font_name", font_name)
        if device is not None:
            self.set("whisper.device", device)

        if api_key is not None and api_provider is not None:
            self.set_api_key(api_provider, api_key)

        _, errors = self.validate_config(self.config)
        if errors:
            for key, msg in errors.items():
                logger.warning(f"保存配置整体验证问题 - {key}: {msg}")

        self.save()


# 全局配置实例
config = ConfigManager()


def create_env_example():
    """创建 .env.example 模板文件"""
    env_content = """# SubtitleForge v2 - 环境变量配置示例
# 复制此文件为 .env 并填写实际值

# API Keys
SUBTITLEFORGE_API_DEEPSEEK_KEY=your_deepseek_api_key_here
SUBTITLEFORGE_API_OPENAI_KEY=your_openai_api_key_here

# 翻译设置
SUBTITLEFORGE_API_PROVIDER=deepseek
SUBTITLEFORGE_API_MODEL=deepseek-chat
SUBTITLEFORGE_API_TEMPERATURE=0.4
SUBTITLEFORGE_API_BATCH_SIZE=8

# Whisper 设置
SUBTITLEFORGE_WHISPER_MODEL=base
SUBTITLEFORGE_WHISPER_DEVICE=cpu

# 翻译设置
SUBTITLEFORGE_TRANSLATION_SOURCE_LANG=ja
SUBTITLEFORGE_TRANSLATION_TARGET_LANG=zh
SUBTITLEFORGE_TRANSLATION_STYLE=anime

# 字幕样式
SUBTITLEFORGE_SUBTITLE_ZH_FONT_SIZE=52
SUBTITLEFORGE_SUBTITLE_JA_FONT_SIZE=44
SUBTITLEFORGE_SUBTITLE_FONT_NAME=Microsoft YaHei
"""
    env_example = Path.cwd() / ".env.example"
    if not env_example.exists():
        with open(env_example, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print(f"已创建 .env.example 模板文件")


if __name__ == "__main__":
    create_env_example()
    print("配置管理模块测试")
    print(f"配置目录: {CONFIG_DIR}")
    print(f"当前配置: {json.dumps(config.config, ensure_ascii=False, indent=2)}")