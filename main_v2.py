#!/usr/bin/env python3
"""
SubtitleForge v2 - 命令行入口
升级版视频翻译工具，支持上下文感知翻译 + 后处理润色

用法:
    python main_v2.py --video <视频路径> [选项]
    
示例:
    python main_v2.py --video "D:/video/anime.mp4" --style anime
    python main_v2.py --video "D:/video/anime.mp4" --style drama --api-key sk-xxx
    python main_v2.py --video "D:/video/anime.mp4" --source-lang ja --target-lang zh
"""

import os
import sys
import argparse
import json
from pathlib import Path

# 添加模块路径
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from pipeline_v2 import SubtitlePipelineV2
from translator_v2 import ContextAwareTranslator, TranslationConfig, TranslationStyle
from post_processor import PostProcessor


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="SubtitleForge v2 - 升级版视频字幕翻译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
风格说明:
  anime       - 动漫/广播剧（口语化、语气词丰富，默认）
  drama       - 影视剧（自然流畅、保持节奏）
  youtube     - 油管/Vlog（轻松随意、网络化）
  documentary - 纪录片（正式规范、准确优先）

示例:
  python main_v2.py --video "anime.mp4"
  python main_v2.py --video "video.mp4" --style drama
  python main_v2.py --video "video.mp4" --api-key sk-xxx --style anime
        """
    )
    
    parser.add_argument(
        "--video", "-v",
        type=str,
        required=True,
        help="视频文件路径"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出目录（默认与视频同目录下的 SubtitleForge_v2_output）"
    )
    
    parser.add_argument(
        "--source-lang", "-s",
        type=str,
        default="ja",
        help="源语言代码（默认 ja）"
    )
    
    parser.add_argument(
        "--target-lang", "-t",
        type=str,
        default="zh",
        help="目标语言代码（默认 zh）"
    )
    
    parser.add_argument(
        "--style",
        type=str,
        default="anime",
        choices=["anime", "drama", "youtube", "documentary"],
        help="翻译风格（默认 anime）"
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="DeepSeek/OpenAI API Key（默认从环境变量 DEEPSEEK_API_KEY 读取）"
    )
    
    parser.add_argument(
        "--provider",
        type=str,
        default="deepseek",
        choices=["deepseek", "openai"],
        help="API 提供商（默认 deepseek）"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="模型名称（默认 deepseek-chat）"
    )
    
    parser.add_argument(
        "--whisper-model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 模型大小（默认 base）"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="推理设备（默认 cpu）"
    )
    
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="跳过音频提取（使用已有WAV文件）"
    )
    
    parser.add_argument(
        "--audio-path",
        type=str,
        default=None,
        help="已有音频文件路径（配合 --skip-audio 使用）"
    )
    
    parser.add_argument(
        "--compare",
        type=str,
        default=None,
        help="与旧版翻译结果对比（指定旧版JSON文件路径）"
    )
    
    return parser.parse_args()


def generate_comparison_report(new_sentences, old_json_path, output_path):
    """生成新旧翻译对比报告"""
    if not old_json_path or not os.path.exists(old_json_path):
        print("跳过对比：旧版翻译文件不存在")
        return
    
    with open(old_json_path, 'r', encoding='utf-8') as f:
        old_data = json.load(f)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("SubtitleForge 翻译质量升级对比报告\n")
        f.write("=" * 60 + "\n\n")
        f.write("升级内容：\n")
        f.write("1. 上下文感知翻译（每批10句 + 前3句上下文）\n")
        f.write("2. 专用 System Prompt（按风格的定制翻译指令）\n")
        f.write("3. 内置术语表（100+ 条日语→中文映射）\n")
        f.write("4. Whisper ASR 纠错机制\n")
        f.write("5. 后处理润色（去AI味、口语化、连贯性检查）\n")
        f.write("6. 多风格支持（anime/drama/youtube/documentary）\n")
        f.write("\n\n")
        
        # 对比表格
        f.write("新旧翻译对比 (前 30 条):\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'序号':<4} | {'日文原文':<30} | {'旧翻译':<30} | {'新翻译':<30}\n")
        f.write("-" * 80 + "\n")
        
        count = min(30, len(new_sentences), len(old_data))
        for i in range(count):
            old = old_data[i]
            new = new_sentences[i]
            
            jp = new.get("text", "")[:28]
            old_trans = old.get("translated_text", old.get("text", ""))[:28]
            new_trans = new.get("translated_text", "")[:28]
            
            f.write(f"{i+1:<4} | {jp:<30} | {old_trans:<30} | {new_trans:<30}\n")
        
        f.write("\n\n完整翻译（全部）:\n")
        f.write("=" * 60 + "\n")
        for i, s in enumerate(new_sentences):
            jp = s.get("text", "")
            zh = s.get("translated_text", "")
            old_zh = old_data[i].get("translated_text", "") if i < len(old_data) else ""
            
            f.write(f"\n[{i+1}] 日文: {jp}\n")
            if old_zh:
                f.write(f"    旧译: {old_zh}\n")
            f.write(f"    新译: {zh}\n")
    
    print(f"对比报告已保存: {output_path}")


def main():
    """主函数"""
    args = parse_args()
    
    # 验证视频文件
    if not os.path.exists(args.video):
        print(f"错误: 视频文件不存在: {args.video}")
        sys.exit(1)
    
    # 设置 API Key
    api_key = args.api_key or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 未设置 API Key")
        print("请通过 --api-key 参数传入，或设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)
    
    # 设置输出目录
    if args.output:
        output_dir = args.output
    else:
        video_dir = os.path.dirname(os.path.abspath(args.video))
        video_name = os.path.splitext(os.path.basename(args.video))[0]
        output_dir = os.path.join(video_dir, f"{video_name}_SubtitleForge_v2")
    
    # 设置模型
    model = args.model or ("deepseek-chat" if args.provider == "deepseek" else "gpt-4o-mini")
    
    # 打印配置
    print("=" * 60)
    print("SubtitleForge v2")
    print("=" * 60)
    print(f"视频文件:   {args.video}")
    print(f"输出目录:   {output_dir}")
    print(f"源语言:     {args.source_lang}")
    print(f"目标语言:   {args.target_lang}")
    print(f"翻译风格:   {args.style}")
    print(f"API 提供商: {args.provider}")
    print(f"模型:       {model}")
    print("=" * 60)
    
    # 初始化流水线
    pipeline = SubtitlePipelineV2(
        whisper_model=args.whisper_model,
        device=args.device
    )
    
    # 执行完整流水线
    result = pipeline.run_full_pipeline(
        video_path=args.video,
        output_dir=output_dir,
        api_key=api_key,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        style=args.style,
        provider=args.provider,
        model=model,
        skip_audio=args.skip_audio,
        audio_path=args.audio_path
    )
    
    # 生成对比报告
    if args.compare:
        compare_path = os.path.join(output_dir, "translation_comparison_v2.txt")
        # 读取后处理后的字幕
        with open(result["final_json"], 'r', encoding='utf-8') as f:
            final_sentences = json.load(f)
        generate_comparison_report(final_sentences, args.compare, compare_path)
    
    # 升级报告
    report_path = os.path.join(output_dir, "upgrade_report_v2.txt")
    _generate_upgrade_report(result, args, report_path)
    
    print(f"\n升级报告: {report_path}")
    print("\n所有产出物:")
    for key, value in result.items():
        if isinstance(value, str) and os.path.exists(value):
            print(f"  [{key}] {value}")


def _generate_upgrade_report(result: dict, args, report_path: str):
    """生成升级报告"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("SubtitleForge v2 升级报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"处理时间: {__import__('datetime').datetime.now().isoformat()}\n")
        f.write(f"视频文件: {args.video}\n")
        f.write(f"源语言:   {args.source_lang}\n")
        f.write(f"目标语言: {args.target_lang}\n")
        f.write(f"翻译风格: {args.style}\n")
        f.write(f"句子总数: {result.get('sentences_count', 'N/A')}\n")
        f.write(f"翻译句数: {result.get('translated_sentences', 'N/A')}\n")
        f.write("\n")
        f.write("v2 升级内容:\n")
        f.write("-" * 40 + "\n")
        f.write("1. [翻译模块] 上下文感知翻译引擎\n")
        f.write("   - 每批10句带前3句上下文\n")
        f.write("   - 专用 System Prompt（按风格定制）\n")
        f.write("   - 内置术语表（100+ 条日语→中文映射）\n")
        f.write("   - Whisper ASR 纠错机制\n")
        f.write("\n")
        f.write("2. [后处理] 自动润色流水线\n")
        f.write("   - 去AI味：替换书面词汇为口语化表达\n")
        f.write("   - 口语化：添加语气词、缩短短语\n")
        f.write("   - 连贯性：检查代词/时态一致性\n")
        f.write("\n")
        f.write("3. [多风格] 4种翻译风格\n")
        f.write("   - anime: 动漫/广播剧（口语化、语气词丰富）\n")
        f.write("   - drama: 影视剧（自然流畅）\n")
        f.write("   - youtube: 油管/Vlog（轻松随意）\n")
        f.write("   - documentary: 纪录片（正式规范）\n")
        f.write("\n")
        f.write("产出文件:\n")
        f.write("-" * 40 + "\n")
        for key, value in result.items():
            if isinstance(value, str):
                f.write(f"  {key}: {value}\n")


if __name__ == "__main__":
    main()