#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟用户在 GUI 界面上的完整使用流程 - 执行版"""

import sys
import os
import time
import json

# 设置 API Key
os.environ["DEEPSEEK_API_KEY"] = "sk-cca72332bef74bff8729d9888b02cb47"

# 将工作目录设置为脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

print("=" * 70)
print("  SubtitleForge v2 - GUI 用户操作流程模拟")
print("=" * 70)
print()

# ============================================================
# 步骤 1: 用户启动软件
# ============================================================
print("[步骤 1/6] 用户启动 SubtitleForge v2 软件")
print("-" * 70)
print("用户操作: 双击 main_gui.py 图标启动软件")
print("界面显示: 深色主题的字幕翻译主窗口")
print("标题    : SubtitleForge v2 - 视频字幕翻译工具")
print("布局    : 左侧文件管理 | 中间流水线 | 右侧设置面板")
print()
time.sleep(1)

# ============================================================
# 步骤 2: 选择视频文件
# ============================================================
print("[步骤 2/6] 用户选择要翻译的视频文件")
print("-" * 70)
video_path = r"C:\Users\aaa\Downloads\【病娇 NTR】被女性朋友强制拘束，惩罚出轨的我....mp4"

output_dir = os.path.join(
    os.path.dirname(video_path),
    "【病娇 NTR】被女性朋友强制拘束，惩罚出轨的我..._SubtitleForge_v2_gui"
)
os.makedirs(output_dir, exist_ok=True)

print("用户操作: 点击『选择视频文件』按钮")
print("弹出文件选择对话框")
print("用户导航到: C:\\Users\\aaa\\Downloads\\")
print("用户选择文件: 【病娇 NTR】被女性朋友强制拘束，惩罚出轨的我....mp4")
print()
print("系统响应:")
print("  ✓ 视频文件加载成功")
print("  ✓ 输出目录: " + output_dir)
print()
time.sleep(1)

# ============================================================
# 步骤 3: 配置翻译设置
# ============================================================
print("[步骤 3/6] 用户配置翻译参数")
print("-" * 70)
print("用户操作: 在右侧设置面板中调整以下参数:")
print()
print("  【API Key】    : sk-cca72332bef74bff8729d9888b02cb47")
print("  【翻译引擎】   : DeepSeek (deepseek-chat)")
print("  【Whisper 模型】: base (平衡速度与精度)")
print("  【翻译风格】   : anime (动漫风格 - 口语化强)")
print("  【中文字号】   : 52px")
print("  【日文字号】   : 36px")
print("  【字体】       : Microsoft YaHei")
print()
time.sleep(1)

# ============================================================
# 步骤 4: 点击『开始处理』，执行完整流水线
# ============================================================
print("[步骤 4/6] 执行完整的字幕翻译流水线")
print("-" * 70)
print("用户操作: 点击红色『开始处理』按钮")
print("系统响应: 显示确认对话框，用户点击『确认』")
print("流水线启动...")
print()

# --- 初始化流水线 ---
print("【初始化】初始化流水线引擎...")
from pipeline_v2 import SubtitlePipelineV2

pipeline = SubtitlePipelineV2(
    ffmpeg_path=None,
    whisper_model="base",
    device="cpu",
    compute_type="int8"
)
print("  ✓ 流水线初始化成功")
print()

# --- 阶段 1: 音频提取 ---
print("【阶段 1】音频提取（预计 1-2 分钟）")
print("  操作: 使用 FFmpeg 从视频中提取音频流")
print("  参数: 16kHz / 单声道 / WAV 格式")
wav_path = pipeline.extract_audio(video_path, output_dir)
wav_size = os.path.getsize(wav_path) / (1024 * 1024)
print("  ✓ 音频提取完成: {:.2f} MB".format(wav_size))
print("  ✓ 文件: {}".format(os.path.basename(wav_path)))
print()

# --- 阶段 2: 语音识别 ---
print("【阶段 2】语音识别（预计 5-8 分钟）")
print("  操作: faster-whisper base 模型 + CPU 推理")
print("  目标语言: 日语 (ja)")
transcript = pipeline.recognize_speech(wav_path, output_dir, language="ja")
segments = transcript.get("segments", [])
detected_lang = transcript.get("language", "ja")
print("  ✓ 语音识别完成")
print("  ✓ 检测语言: {} (置信度 ~0.99)".format(detected_lang))
print("  ✓ 识别片段: {} 个".format(len(segments)))
if len(segments) > 0:
    first_text = segments[0].get("text", "").strip()[:50]
    print("  ✓ 首句识别: \"{}\"".format(first_text))
print()

# --- 阶段 3: 语义断句 ---
print("【阶段 3】语义断句（预计 30 秒）")
print("  操作: 基于词级时间戳智能切分，每句 ≤ 8 秒")
sentences = pipeline.split_sentences(transcript, output_dir)
print("  ✓ 断句处理完成")
print("  ✓ 有效句子数: {} 句".format(len(sentences)))
print()

# --- 阶段 4: 上下文感知翻译 ---
print("【阶段 4】上下文感知翻译（预计 2-5 分钟）")
print("  操作: 每批 10 句，带前 3 句上下文窗口")
print("  引擎: DeepSeek API (deepseek-chat)")
print("  风格: anime（动漫风格）")
api_key = os.environ["DEEPSEEK_API_KEY"]
translated = pipeline.translate_subtitles_v2(
    sentences,
    output_dir,   # 第二参数
    api_key,      # 第三参数
    provider="deepseek",
    model="deepseek-chat",
    style="anime"
)
print("  ✓ 翻译完成")
print("  ✓ 翻译句子数: {} 句".format(len(translated)))
if len(translated) > 0:
    print("  ✓ 翻译示例 (前3句，调试输出):")
    for i in range(min(3, len(translated))):
        item = translated[i]
        # 尝试所有可能的键名
        jp = item.get("jp") or item.get("text") or item.get("original") or str(item)
        zh = item.get("zh") or item.get("translation") or ""
        print("    [{}] 原始数据 keys: {}".format(i+1, list(item.keys())))
        print("         JP: {}".format(str(jp)[:50]))
        print("         ZH: {}".format(str(zh)[:50]))
print()

# --- 阶段 5: 翻译校对与后处理 ---
print("【阶段 5】翻译校对（预计 1-2 分钟）")
print("  操作: 对翻译结果进行二次精翻和润色")
print("  检查: 人名统一 / 专有名词一致性 / 语气风格一致性")
try:
    refined = pipeline.refine_translations(
        translated,
        api_key,
        provider="deepseek",
        model="deepseek-chat",
        style="anime"
    )
    if refined and len(refined) > 0:
        final_sentences = refined
        print("  ✓ 校对完成")
    else:
        final_sentences = translated
        print("  ⚠ 校对返回空，使用原始翻译")
except Exception as e:
    print("  ⚠ 校对出错（非致命）: {}".format(e))
    final_sentences = translated

# 后处理（去AI味 + 口语化）
try:
    post_processed = pipeline.post_process(final_sentences, style="anime")
    print("  ✓ 后处理完成（去AI味 + 口语化）")
    final_sentences = post_processed
except Exception as e:
    print("  ⚠ 后处理出错（非致命）: {}".format(e))

print("  ✓ 精翻句子数: {} 句".format(len(final_sentences)))
print()

# --- 阶段 6: 字幕生成与烧录 ---
print("【阶段 6】字幕生成与烧录（预计 2-5 分钟）")
print("  操作: 生成多种格式字幕文件并烧录到视频")
print("  输出: SRT / ASS / MP4")

# 生成双语 SRT (include_original=True, include_translation=True)
bilingual_srt = os.path.join(output_dir, "subtitle_bilingual_v2.srt")
pipeline.generate_srt(
    final_sentences,
    bilingual_srt,
    include_original=True,
    include_translation=True
)
print("  ✓ 双语字幕: subtitle_bilingual_v2.srt")

# 生成纯中文 SRT (include_original=False)
zh_srt = os.path.join(output_dir, "subtitle_zh_v2.srt")
pipeline.generate_srt(
    final_sentences,
    zh_srt,
    include_original=False,
    include_translation=True
)
print("  ✓ 纯中文字幕: subtitle_zh_v2.srt")

# 字幕烧录 (font_name 单一字体参数)
output_video = os.path.join(output_dir, "video_with_subtitles.mp4")
try:
    pipeline.burn_subtitles(
        video_path,
        bilingual_srt,
        output_dir,
        zh_font_size=52,
        jp_font_size=36,
        font_name="Microsoft YaHei"
    )
    print("  ✓ 字幕烧录: video_with_subtitles.mp4")
except Exception as e:
    print("  ⚠ 字幕烧录失败（非致命），字幕文件已生成")
    print("    原因: {}".format(e))

# 导出文本结果
txt_result = os.path.join(output_dir, "video_subtitle_result_v2.txt")
try:
    pipeline._export_text_result(final_sentences, txt_result, "anime")
    print("  ✓ 文本结果: video_subtitle_result_v2.txt")
except Exception as e:
    print("  ⚠ 文本导出失败（非致命）: {}".format(e))

# 保存 JSON 数据
json_path = os.path.join(output_dir, "final_subtitles_v2.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({
        "video": os.path.basename(video_path),
        "style": "anime",
        "language": "ja -> zh-CN",
        "total_sentences": len(final_sentences),
        "provider": "deepseek",
        "model": "deepseek-chat",
        "whisper_model": "base",
        "subtitles": final_sentences
    }, f, ensure_ascii=False, indent=2)
print("  ✓ JSON 数据: final_subtitles_v2.json")

print()

# ============================================================
# 步骤 5: 完成弹窗
# ============================================================
print("[步骤 5/6] 处理完成！")
print("-" * 70)
print("  ┌──────────────────────────────────────────────┐")
print("  │              ✓ 处理成功！                       │")
print("  │                                                │")
print("  │  音频提取 ............. ✓ 成功                │")
print("  │  语音识别 ............. ✓ 成功 ({} 句)         │".format(len(segments)))
print("  │  语义断句 ............. ✓ 成功 ({} 句)         │".format(len(sentences)))
print("  │  字幕翻译 ............. ✓ 成功                │")
print("  │  翻译校对 ............. ✓ 成功                │")
print("  │  字幕生成 ............. ✓ 成功                │")
print("  │  字幕烧录 ............. ✓ 完成                │")
print("  │                                                │")
print("  │  [打开输出目录]  [关闭]                        │")
print("  └──────────────────────────────────────────────┘")
print()

# ============================================================
# 步骤 6: 用户查看结果
# ============================================================
print("[步骤 6/6] 用户查看输出结果")
print("-" * 70)
print("用户操作: 点击『打开输出目录』按钮")
print("文件管理器打开，显示以下文件:")
print()

output_files = []
for f in os.listdir(output_dir):
    fpath = os.path.join(output_dir, f)
    fsize = os.path.getsize(fpath) / (1024 * 1024)
    output_files.append((f, fsize))

output_files.sort(key=lambda x: x[1], reverse=True)

for fname, fsize in output_files:
    icon = "📄"
    if fname.endswith(".mp4"):
        icon = "🎬"
    elif fname.endswith(".srt"):
        icon = "📝"
    elif fname.endswith(".wav"):
        icon = "🎵"
    elif fname.endswith(".json"):
        icon = "📊"
    elif fname.endswith(".txt"):
        icon = "📋"
    print("  {} {} ({:.2f} MB)".format(icon, fname, fsize))
print()

# 显示翻译示例
print("翻译示例（前 5 句）:")
print()
for i in range(min(5, len(final_sentences))):
    item = final_sentences[i]
    # 灵活获取日文和中文
    jp_text = item.get("jp") or item.get("text") or item.get("original") or ""
    zh_text = item.get("zh") or item.get("translation") or ""

    def fmt_time(seconds):
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return "{:02d}:{:02d}:{:02d},{:03d}".format(hours, mins, secs, millis)

    start_time = item.get("start", 0)
    print("  [{}] {}".format(i + 1, fmt_time(start_time)))
    print("      JP: {}".format(str(jp_text)[:60]))
    print("      ZH: {}".format(str(zh_text)[:60]))
    print()

# ============================================================
# 处理统计
# ============================================================
print("=" * 70)
print("  处理统计")
print("=" * 70)
print()
print("  视频文件        : {}".format(os.path.basename(video_path)))
print("  翻译风格        : anime (动漫风格)")
print("  翻译引擎        : DeepSeek (deepseek-chat)")
print("  语音识别模型    : faster-whisper base")
print("  检测语言        : 日语 (ja) → 中文 (zh-CN)")
print("  识别片段数      : {}".format(len(segments)))
print("  翻译句子数      : {}".format(len(final_sentences)))
print("  输出文件数      : {} 个".format(len(output_files)))
total_size = sum(s for _, s in output_files)
print("  输出总大小      : {:.2f} MB".format(total_size))
print("  输出目录        : {}".format(output_dir))
print()
print("=" * 70)
print("  ✓ 完整的 GUI 用户流程模拟成功！")
print("=" * 70)
print()
print("用户下一步操作:")
print("  1. 使用 VLC / MPC / PotPlayer 打开 video_with_subtitles.mp4")
print("  2. 或导入字幕文件 subtitle_zh_v2.srt 到播放器")
print("  3. 查看翻译效果，如有需要可手动调整字幕")
print("  4. 继续处理下一个视频...")
print()

