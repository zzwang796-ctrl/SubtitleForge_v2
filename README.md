# SubtitleForge v2 - 升级版视频字幕翻译工具

## 概述

SubtitleForge v2 是视频字幕翻译流水线的重大升级版本，从逐句直译升级为**上下文感知翻译 + 后处理润色**的两阶段流水线。

### v2 核心升级

| 特性 | v1 (旧版) | v2 (升级版) |
|------|----------|------------|
| 翻译策略 | 逐句直译 | 每批10句带前3句上下文 |
| System Prompt | 通用翻译指令 | 按风格定制的专用指令 |
| 术语表 | 无 | 内置100+条日语→中文映射 |
| ASR 纠错 | 无 | Whisper 常见错误纠正 |
| 后处理 | 无 | 去AI味 + 口语化 + 连贯性检查 |
| 风格支持 | 单一 | 4种风格 (anime/drama/youtube/documentary) |

## 目录结构

```
SubtitleForge_v2/
├── main_v2.py              # 命令行入口
├── pipeline_v2.py          # 升级版流水线（6阶段）
├── translator_v2.py        # 上下文感知翻译引擎
├── post_processor.py       # 后处理润色模块
├── style_profiles.json     # 风格配置文件
├── audio_extractor.py      # 音频提取模块
├── speech_recognizer.py    # 语音识别模块（Whisper）
└── README.md               # 本文件
```

## 快速开始

### 环境要求

- Python 3.8+
- FFmpeg（用于音频提取）
- Whisper（用于语音识别）
- DeepSeek API Key 或 OpenAI API Key

### 安装

```bash
pip install openai-whisper requests
```

### 使用

```bash
# 基础用法（使用 anime 风格，日语→中文）
python main_v2.py --video "视频路径.mp4"

# 指定风格
python main_v2.py --video "video.mp4" --style drama

# 使用 OpenAI API
python main_v2.py --video "video.mp4" --provider openai --api-key sk-xxx

# 从环境变量读取 API Key
set DEEPSEEK_API_KEY=sk-xxx
python main_v2.py --video "video.mp4"

# 生成新旧翻译对比报告
python main_v2.py --video "video.mp4" --compare "旧版翻译.json"
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--video`, `-v` | 视频文件路径 | (必填) |
| `--output`, `-o` | 输出目录 | 视频同目录下自动创建 |
| `--source-lang`, `-s` | 源语言代码 | ja |
| `--target-lang`, `-t` | 目标语言代码 | zh |
| `--style` | 翻译风格 | anime |
| `--api-key` | API Key | 环境变量 DEEPSEEK_API_KEY |
| `--provider` | API 提供商 | deepseek |
| `--model` | 模型名称 | deepseek-chat |
| `--whisper-model` | Whisper 模型 | base |
| `--device` | 推理设备 | cpu |
| `--skip-audio` | 跳过音频提取 | false |
| `--compare` | 旧版翻译JSON对比 | 无 |

## 翻译风格

### anime - 动漫/广播剧
默认风格。口语化强，语气词丰富。病娇/黑化角色有强烈情感表现力。

### drama - 影视剧
自然流畅，保持原文节奏和人物性格。适合日剧、电影。

### youtube - 油管/Vlog
轻松随意，大量网络化表达。适合个人视频频道内容。

### documentary - 纪录片
正式规范，术语准确。适合教育类和纪录片内容。

## 流水线流程

```
输入视频
    │
    ▼
[阶段1] 音频提取 ──── FFmpeg 提取 WAV (16kHz/mono)
    │
    ▼
[阶段2] 语音识别 ──── Whisper 模型 (日语→文本)
    │
    ▼
[阶段3] 语义断句 ──── 标点+停顿规则 (≤8秒/句)
    │
    ▼
[阶段4] 上下文翻译 ──── DeepSeek API (10句/批+前3句上下文)
    │
    ▼
[阶段5] 后处理润色 ──── 去AI味 + 口语化 + 连贯性检查
    │
    ▼
[阶段6] 字幕生成 ──── 双语SRT + 纯文本导出
    │
    ▼
输出文件 (.srt / .json / .txt)
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `subtitle_bilingual_v2.srt` | 双语字幕（日文+中文） |
| `subtitle_zh_v2.srt` | 纯中文字幕 |
| `final_subtitles_v2.json` | 后处理后的完整JSON |
| `video_subtitle_result_v2.txt` | 纯文本翻译结果 |
| `upgrade_report_v2.txt` | 升级报告 |

## API Key 配置

推荐方式：设置环境变量
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-xxx"

# Linux/Mac
export DEEPSEEK_API_KEY="sk-xxx"
```

或通过命令行参数：
```bash
python main_v2.py --video "video.mp4" --api-key "sk-xxx"
```

## 许可

内部工具，仅供个人使用。