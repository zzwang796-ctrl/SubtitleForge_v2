# SubtitleForge v2 - 升级版视频字幕翻译工具

## 概述

SubtitleForge v2 是视频字幕翻译流水线的重大升级版本，从逐句直译升级为**上下文感知翻译 + 后处理润色**的两阶段流水线，并新增 **GUI 界面**、**断点续传**、**日志系统**、**测试框架** 等企业级特性。

### v2 核心升级

| 特性 | v1 (旧版) | v2 (升级版) |
|------|----------|------------|
| 翻译策略 | 逐句直译 | 每批10句带前3句上下文 |
| System Prompt | 通用翻译指令 | 按风格定制的专用指令 |
| 术语表 | 无 | 内置100+条日语→中文映射 |
| ASR 纠错 | 无 | Whisper 常见错误纠正 |
| 后处理 | 无 | 去AI味 + 口语化 + 连贯性检查 |
| 风格支持 | 单一 | 4种风格 (anime/drama/youtube/documentary) |
| 字幕时间对齐 | 有延迟（说完才显示） | **严格按原始时间戳，到时间立即显示** |
| 图形界面 (GUI) | 无 | **PyQt6 完整 GUI** |
| 断点续传 | 无 | **支持断点续传** |
| 配置持久化 | 无 | **JSON 配置文件** |
| 日志系统 | 无 | **分级日志 + 文件轮转** |
| 单元测试 | 无 | **测试框架 + 多模块测试** |

## 目录结构

```
SubtitleForge_v2/
├── main_v2.py              # 命令行入口
├── main_gui.py             # GUI 入口（PyQt6）
├── pipeline_v2.py          # 升级版流水线（8 阶段，含字幕烧录）
├── translator_v2.py        # 上下文感知翻译引擎
├── post_processor.py       # 后处理润色模块
├── audio_extractor.py      # 音频提取模块
├── speech_recognizer.py    # 语音识别模块（Whisper）
├── checkpoint.py           # 断点续传检查点管理
├── config.py               # 配置管理（JSON 持久化）
├── font_utils.py           # 字体工具（字幕样式）
├── logging_setup.py        # 统一日志系统
├── style_profiles.json     # 风格配置文件
├── requirements.txt        # Python 依赖清单
├── .env.example            # 环境变量示例
├── SubtitleForge_v2.spec   # PyInstaller 打包配置
├── tests/                  # 单元测试目录
│   ├── test_checkpoint.py
│   ├── test_font_utils.py
│   ├── test_translator_json_parsing.py
│   └── test_video_probe.py
└── README.md               # 本文件
```

## 快速开始

### 环境要求

- Python 3.8+
- FFmpeg（用于音频提取和字幕烧录）
- Whisper（用于语音识别）
- DeepSeek API Key 或 OpenAI API Key

### 安装

```bash
pip install -r requirements.txt
```

### 使用 - GUI 方式（推荐）

```bash
python main_gui.py
```

图形界面功能：
- 选择视频文件
- 选择/配置 API Key
- 选择翻译风格、语言、Whisper 模型
- 实时进度显示与日志
- 一键生成双语字幕视频

### 使用 - 命令行方式

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

# 启用断点续传（默认自动启用，中途中断后再次运行会从断点继续）
python main_v2.py --video "video.mp4"
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

## 翻译风格

### anime - 动漫/广播剧
默认风格。口语化强，语气词丰富。病娇/黑化角色有强烈情感表现力。

### drama - 影视剧
自然流畅，保持原文节奏和人物性格。适合日剧、电影。

### youtube - 油管/Vlog
轻松随意，大量网络化表达。适合个人视频频道内容。

### documentary - 纪录片
正式规范，术语准确。适合教育类和纪录片内容。

## 流水线流程（8 阶段）

```
输入视频
    │
    ▼
[阶段 1/8] 音频提取 ──── FFmpeg 提取 WAV (16kHz/mono)
    │
    ▼
[阶段 2/8] 语音识别 ──── Whisper 模型 (日语→文本，含时间戳)
    │
    ▼
[阶段 3/8] 语义断句 ──── 标点+停顿规则 (≤8秒/句)
    │
    ▼
[阶段 4/8] 上下文翻译 ──── DeepSeek API (10句/批+前3句上下文)
    │
    ▼
[阶段 5/8] 后处理润色 ──── 去AI味 + 口语化 + 连贯性检查
    │
    ▼
[阶段 6/8] 精修（可选）─── 风格一致性检查
    │
    ▼
[阶段 7/8] 字幕生成 ──── 双语 SRT + 纯文本导出
    │
    ▼
[阶段 8/8] 字幕烧录 ──── FFmpeg 直接烧录 SRT 到视频
    │
    ▼
输出文件 (.mp4 / .srt / .json / .txt)
```

### ⚠️ 关键修复：字幕时间对齐问题

**问题描述：** 之前版本字幕显示存在明显延迟——视频中的台词已经说完，字幕才弹出来。

**根本原因：** 之前使用的是 **ASS 字幕格式** → FFmpeg `ass` 滤镜烧录。ASS 格式支持丰富的动画/样式，但 FFmpeg 在渲染 ASS 时有额外的处理开销，导致时间戳不能精确对齐。

**解决方案：** 改为使用 **SRT 格式直接烧录**——FFmpeg 的 `subtitles` 滤镜直接读取 SRT 文件，保证字幕时间戳与原始识别结果 **100% 对齐**。

**具体修改（`pipeline_v2.py` 中的 `burn_subtitles` 方法）：**
- 移除了 `TimestampOptimizer` 模块和相关的时间戳优化逻辑
- 不再将 SRT 转换为 ASS 格式
- 直接使用 FFmpeg `subtitles` 滤镜烧录 SRT
- 效果：**字幕到时间立即显示，时间结束后迅速消失**

## 核心模块说明

### 断点续传（`checkpoint.py`）
每个流水线阶段完成后写入检查点文件 `pipeline_checkpoint.json`。下次运行时自动跳过已完成的阶段，从中断处继续。

### 配置管理（`config.py`）
支持从 JSON 文件加载/保存配置，包括 API Key、翻译风格、模型选择、字体设置等。

### 日志系统（`logging_setup.py`）
统一的多级别日志（DEBUG/INFO/WARNING/ERROR），支持控制台输出和日志文件轮转。日志保存在 `logs/` 目录。

### 字体工具（`font_utils.py`）
字幕生成时的字体配置和样式管理。

### GUI 界面（`main_gui.py`）
基于 PyQt6 构建的图形界面，提供视频选择、参数配置、进度显示和结果输出的完整交互流程。

### 测试框架（`tests/`）
包含多个单元测试，覆盖检查点、字体工具、翻译器 JSON 解析、视频探测等模块。

运行测试：
```bash
python -m pytest tests/ -v
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `video_with_subtitles.mp4` | **烧录双语字幕的最终视频** |
| `subtitle_bilingual_v2.srt` | 双语字幕（日文+中文） |
| `subtitle_zh_v2.srt` | 纯中文字幕 |
| `final_subtitles_v2.json` | 后处理后的完整 JSON |
| `video_subtitle_result_v2.txt` | 纯文本翻译结果 |
| `pipeline_checkpoint.json` | 断点续传检查点 |
| `logs/subtitleforge_YYYYMMDD.log` | 运行日志 |

## API Key 配置

推荐方式：设置环境变量
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-xxx"

# Linux/Mac
export DEEPSEEK_API_KEY="sk-xxx"
```

或复制 `.env.example` 为 `.env` 并填入密钥。

或通过命令行参数：
```bash
python main_v2.py --video "video.mp4" --api-key "sk-xxx"
```

## 打包为可执行文件（可选）

使用 PyInstaller：
```bash
# 打包 GUI 版本
pyinstaller SubtitleForge_v2_gui.spec

# 打包命令行版本
pyinstaller SubtitleForge_v2.spec
```

## 更新日志

### v2.x（当前版本）
- ✅ **字幕时间对齐修复**：改为 SRT 格式直接烧录，保证字幕与视频完全同步
- ✅ **GUI 界面**：基于 PyQt6 的完整图形界面
- ✅ **断点续传**：中途中断后可从断点继续
- ✅ **配置持久化**：JSON 配置文件管理
- ✅ **统一日志系统**：分级日志 + 文件轮转
- ✅ **测试框架**：单元测试覆盖关键模块
- ✅ **字幕烧录**：直接输出带字幕的 mp4 视频

### v2.0
- 上下文感知翻译（10句/批 + 前3句上下文）
- 4 种翻译风格支持
- 术语表 + ASR 纠错
- 后处理润色

## 许可

内部工具，仅供个人使用。
