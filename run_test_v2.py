#!/usr/bin/env python3
"""
SubtitleForge v2 测试脚本
使用已有断句数据运行翻译 + 后处理 + 新旧对比
"""

import os
import sys
import json
import time

# 添加 v2 模块路径
V2_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, V2_DIR)

from translator_v2 import ContextAwareTranslator, TranslationConfig, TranslationStyle
from post_processor import PostProcessor

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(V2_DIR)), "temp")
OUTPUT_DIR = V2_DIR  # 输出到 v2 目录

# API 配置（从 run_upgraded_pipeline.py 获取）
API_KEY = "sk-33287af77d884f43bfdb3b37d1946682"
MODEL = "deepseek-v4-flash"

def main():
    # 加载断句结果
    sentences_path = os.path.join(TEMP_DIR, "sentences.json")
    old_trans_path = os.path.join(TEMP_DIR, "translated_subtitles.json")
    
    if not os.path.exists(sentences_path):
        print(f"错误: 断句文件不存在: {sentences_path}")
        return
    
    with open(sentences_path, "r", encoding="utf-8") as f:
        sentences = json.load(f)
    
    # 加载旧翻译
    old_translations = []
    if os.path.exists(old_trans_path):
        with open(old_trans_path, "r", encoding="utf-8") as f:
            old_translations = json.load(f)
    
    print(f"加载了 {len(sentences)} 个句子")
    print(f"旧翻译: {len(old_translations)} 条")
    print()
    
    # ========== 阶段 1: 上下文感知翻译 ==========
    print("=" * 60)
    print("阶段 1: 上下文感知翻译 (ContextAwareTranslator)")
    print("=" * 60)
    
    config = TranslationConfig(
        provider="deepseek",
        api_key=API_KEY,
        model=MODEL,
        style=TranslationStyle.ANIME,
        batch_size=10,
        context_window=3,
        temperature=0.4,
        max_tokens=3000
    )
    
    translator = ContextAwareTranslator(config)
    new_sentences = translator.translate_with_context(sentences, batch_size=10)
    
    # 保存新翻译
    new_trans_path = os.path.join(OUTPUT_DIR, "new_translated_v2.json")
    with open(new_trans_path, "w", encoding="utf-8") as f:
        json.dump(new_sentences, f, ensure_ascii=False, indent=2)
    print(f"\n新翻译已保存: {new_trans_path}")
    
    # ========== 阶段 2: 后处理润色 ==========
    print("\n" + "=" * 60)
    print("阶段 2: 后处理润色 (PostProcessor)")
    print("=" * 60)
    
    processor = PostProcessor(style="anime")
    processed = processor.process(new_sentences)
    
    # 保存后处理结果
    final_path = os.path.join(OUTPUT_DIR, "final_subtitles_v2.json")
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
    print(f"后处理结果已保存: {final_path}")
    
    # ========== 阶段 3: 生成对比报告 ==========
    print("\n" + "=" * 60)
    print("阶段 3: 新旧翻译对比")
    print("=" * 60)
    
    comparison_lines = []
    comparison_lines.append(f"{'序号':<4} | {'日文原文':<28} | {'旧翻译':<28} | {'新翻译':<28}")
    comparison_lines.append("-" * 95)
    
    n = min(30, len(processed), len(old_translations))
    for i in range(n):
        jp = processed[i]["text"][:26]
        old = old_translations[i].get("translated_text", "")[:26] if i < len(old_translations) else "(无)"
        new = processed[i].get("translated_text", "")[:26]
        comparison_lines.append(f"{i+1:<4} | {jp:<28} | {old:<28} | {new:<28}")
    
    comparison_text = "\n".join(comparison_lines)
    print(comparison_text)
    
    # 保存完整对比报告
    report_path = os.path.join(OUTPUT_DIR, "translation_comparison_v2.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("SubtitleForge v2 翻译质量升级对比报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"句子总数: {len(processed)}\n\n")
        f.write("v2 升级内容：\n")
        f.write("1. 上下文感知翻译（每批10句 + 前3句上下文）\n")
        f.write("2. 专用 System Prompt（病娇/黑化语气）\n")
        f.write("3. 内置术语表（100+ 条日语→中文映射）\n")
        f.write("4. Whisper ASR 常见错误纠正\n")
        f.write("5. 后处理润色（去AI味、口语化、连贯性检查）\n")
        f.write("6. 多风格支持（anime/drama/youtube/documentary）\n")
        f.write("\n")
        f.write(comparison_text)
        f.write("\n\n")
        
        f.write("完整翻译（全部）:\n")
        f.write("=" * 60 + "\n")
        for i, s in enumerate(processed):
            jp = s.get("text", "")
            zh = s.get("translated_text", "")
            old_zh = old_translations[i].get("translated_text", "") if i < len(old_translations) else ""
            ts = s.get("start", 0)
            te = s.get("end", 0)
            f.write(f"\n[{i+1}] {ts:.1f}s-{te:.1f}s\n")
            f.write(f"    日文: {jp}\n")
            if old_zh:
                f.write(f"    旧译: {old_zh}\n")
            f.write(f"    新译: {zh}\n")
    
    print(f"\n对比报告已保存: {report_path}")
    
    # 导出纯文本结果
    text_path = os.path.join(OUTPUT_DIR, "video_subtitle_result_v2.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write("SubtitleForge v2 翻译结果\n")
        f.write(f"风格: anime\n")
        f.write("=" * 40 + "\n\n")
        for i, s in enumerate(processed):
            jp = s.get("text", "")
            zh = s.get("translated_text", "")
            ts = s.get("start", 0)
            te = s.get("end", 0)
            f.write(f"[{i+1}] {ts:.1f}s-{te:.1f}s\n")
            f.write(f"    日文: {jp}\n")
            f.write(f"    中文: {zh}\n\n")
    
    print(f"纯文本结果已保存: {text_path}")
    
    # 生成升级报告
    upgrade_path = os.path.join(OUTPUT_DIR, "upgrade_report_v2.txt")
    with open(upgrade_path, "w", encoding="utf-8") as f:
        f.write("SubtitleForge v2 升级报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"句子总数: {len(processed)}\n")
        f.write(f"翻译引擎: ContextAwareTranslator (DeepSeek v4-flash)\n")
        f.write(f"翻译风格: anime\n")
        f.write(f"后处理: PostProcessor (去AI味 + 口语化 + 连贯性检查)\n")
        f.write("\n")
        f.write("项目文件清单:\n")
        f.write("-" * 40 + "\n")
        for root, dirs, files in os.walk(V2_DIR):
            for file in files:
                f.write(f"  {os.path.join(root, file)}\n")
    
    print(f"升级报告已保存: {upgrade_path}")
    
    print("\n" + "=" * 60)
    print("SubtitleForge v2 测试完成！")
    print("=" * 60)
    print(f"翻译结果:     {new_trans_path}")
    print(f"后处理结果:   {final_path}")
    print(f"对比报告:     {report_path}")
    print(f"纯文本结果:   {text_path}")
    print(f"升级报告:     {upgrade_path}")

if __name__ == "__main__":
    main()