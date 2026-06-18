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
from typing import Optional, Dict, Any

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
        return {
            "provider": self.get("api.provider", "deepseek"),
            "model": self.get("api.model", "deepseek-chat"),
            "whisper_model": self.get("whisper.model", "base"),
            "whisper_model_path": self.get("whisper.model_path", ""),
            "style": self.get("translation.style", "anime"),
            "zh_font_size": self.get("subtitle.zh_font_size", 52),
            "ja_font_size": self.get("subtitle.ja_font_size", 44),
            "font_name": self.get("subtitle.font_name", "Microsoft YaHei"),
            "device": self.get("whisper.device", "cpu"),
        }

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

        # 保存 API Key（如果提供）
        if api_key is not None and api_provider is not None:
            self.set_api_key(api_provider, api_key)

        # 保存到文件
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