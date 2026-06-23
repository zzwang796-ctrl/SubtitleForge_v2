# SubtitleForge v2

一个简单实用的视频字幕翻译工具，从原始视频到双语字幕视频的完整解决方案。

## 功能特性

- **上下文感知翻译** - 每批10句 + 前3句上下文，翻译更连贯准确
- **4种翻译风格** - 动漫、影视剧、油管、纪录片
- **字幕时间精确对齐** - 到时间立即显示，时间结束迅速消失
- **网页版界面** - 电影制片室风格，支持深色/浅色主题切换
- **断点续传** - 大文件处理不怕中断
- **完整输出** - 双语字幕视频、SRT文件、纯文本对照

## 快速开始

### 环境要求

- Python 3.10+
- FFmpeg（已内置）
- DeepSeek API Key（用于翻译功能，**必须自行申请**）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 获取 API Key

1. 访问 [DeepSeek API](https://platform.deepseek.com/)
2. 注册账号并获取 API Key
3. **不要将 API Key 提交到 GitHub！**

### 配置 API Key（保护你的密钥）

**方法1：使用环境变量（推荐）**

```bash
# Windows (PowerShell)
$env:DEEPSEEK_API_KEY="sk-xxx"

# Linux/Mac
export DEEPSEEK_API_KEY="sk-xxx"
```

**方法2：使用 .env 文件**

复制 `.env.example` 为 `.env`，并填写你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```bash
SUBTITLEFORGE_API_DEEPSEEK_KEY=your_deepseek_api_key_here
```

**方法3：在网页界面输入**

启动服务后，在设置页面输入你的 API Key（仅在当前会话有效）。

### 启动服务

```bash
python api_server.py
```

然后访问 `http://localhost:8080` 即可使用。

## 使用流程

1. 上传视频文件
2. 选择翻译风格（默认动漫风格）
3. 输入 DeepSeek API Key（在设置中）
4. 点击开始处理
5. 等待处理完成后下载结果

## 技术栈

- **前端**: HTML/CSS/JavaScript
- **后端**: Flask + Python
- **语音识别**: faster-whisper
- **翻译**: DeepSeek API
- **视频处理**: FFmpeg

## 项目结构

```
SubtitleForge_v2/
├── api_server.py        # API服务器
├── pipeline_v2.py       # 字幕处理流水线
├── translator_v2.py     # 上下文翻译器
├── post_processor.py    # 后处理润色
├── speech_recognizer.py # 语音识别
├── checkpoint.py        # 断点续传
├── config.py            # 配置管理
├── .env.example         # 环境变量模板（不含真实密钥）
├── .gitignore           # Git忽略配置（已排除 .env）
├── web/                 # 前端界面
│   ├── index.html
│   ├── style.css
│   └── app.js
└── tests/               # 测试文件
```

## 8阶段处理流程

1. **音频提取** - 从视频分离音频
2. **语音识别** - Whisper 转文字
3. **语义断句** - 智能分割语句
4. **上下文翻译** - DeepSeek API翻译
5. **后处理润色** - 去AI味、口语化
6. **翻译校对** - 二次精翻
7. **字幕生成** - SRT格式输出
8. **字幕烧录** - 嵌入视频

## 安全注意事项

### 保护你的 API Key

1. **永远不要将 API Key 提交到 GitHub**
   - `.gitignore` 已包含 `.env`，确保不会误提交
   - 代码中没有硬编码的 API Key

2. **使用环境变量或配置文件**
   - API Key 仅在运行时加载
   - 不会存储在代码仓库中

3. **API Key 在传输中加密**
   - 前端通过 HTTPS 发送 API Key（生产环境）
   - 本地开发时使用 HTTP

4. **API Key 验证**
   - 系统会验证 API Key 格式
   - 无效的 Key 会被拒绝

### 隐私保护

- 视频文件仅保存在本地
- 不会上传到任何云端
- 所有处理都在本地完成

## 更新日志

### v2.x
- 字幕时间对齐修复（SRT直接烧录）
- 网页版UI（电影制片室风格）
- 上下文感知翻译
- 断点续传支持
- API Key 安全保护

### v2.0
- 首次发布

## 许可

MIT License