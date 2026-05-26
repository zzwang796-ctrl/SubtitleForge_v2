#!/usr/bin/env python3
"""
SubtitleForge v2 - 上下文感知翻译引擎
基于 run_upgraded_pipeline.py 中的翻译逻辑
支持上下文感知翻译 + 术语表 + 多种风格
"""

import os
import json
import time
import re
import requests
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum


class TranslationStyle(Enum):
    """翻译风格枚举"""
    ANIME = "anime"        # 动漫/广播剧（口语化，语气词丰富）
    DRAMA = "drama"        # 影视剧（自然，保持节奏）
    YOUTUBE = "youtube"    # 油管/Vlog（轻松随意）
    DOCUMENTARY = "documentary"  # 纪录片（正式规范）


@dataclass
class TranslationConfig:
    """翻译配置"""
    provider: str = "deepseek"  # "openai" 或 "deepseek"
    api_key: str = ""
    model: str = "deepseek-chat"
    target_language: str = "zh-CN"
    temperature: float = 0.4
    max_tokens: int = 3000
    batch_size: int = 10  # 每批翻译的句子数
    context_window: int = 3  # 上下文窗口大小（前N句）
    style: TranslationStyle = TranslationStyle.ANIME


class ContextAwareTranslator:
    """
    上下文感知翻译器
    每批10句带前3句上下文，支持多种风格
    """
    
    def __init__(self, config: TranslationConfig = None):
        self.config = config or TranslationConfig()
        self._validate_config()
        self._load_style_prompts()
        self._load_term_maps()
    
    def _validate_config(self):
        """验证配置"""
        if not self.config.api_key:
            # 尝试从环境变量读取
            self.config.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not self.config.api_key:
                raise ValueError("API Key 不能为空，请设置环境变量 DEEPSEEK_API_KEY 或通过参数传入")
    
    def _load_style_prompts(self):
        """加载不同风格的 System Prompt"""
        self.style_prompts = {
            TranslationStyle.ANIME: """你是一位专业的日语→中文翻译专家，专门翻译动漫/广播剧字幕（病娇/黑化题材）。

翻译要求：
1. 口语化：像真人说话，不要书面语。用「嘛」「啊」「呀」「哦」「呢」等语气词
2. 上下文连贯：注意代词和前后句的逻辑关系，不要每句孤立翻译
3. 语气匹配：病娇角色语气要有压迫感、执念感、扭曲感
4. 避免过度翻译：简短句子保持简短，不要扩充
5. 常见日语句式处理：
   - 「〜よね」→ 「〜吧」「〜不是吗」
   - 「〜だよ」→ 「〜哦」「〜啦」「〜嘛」
   - 「〜なの」→ 「〜的呢」「〜啊」
   - 「〜てくれた」→ 「为我〜」「帮我〜」
   - 「〜ちゃった」→ 体现完成/遗憾感
6. 禁止：不必要的「的」字堆砌、「进行」「加以」等书面词、逐字直译
7. 如果是日语拟声词或简短感叹词，保留语气不要过度翻译

请以JSON数组格式返回翻译结果，每个元素只包含翻译后的中文文本，顺序与原文一致：
["翻译1", "翻译2", ...]""",
            
            TranslationStyle.DRAMA: """你是一位专业的日语→中文翻译专家，专门翻译影视剧字幕。

翻译要求：
1. 自然流畅：像真人对话，不要生硬翻译
2. 上下文连贯：注意人物关系和对话逻辑
3. 语气准确：保持原文的情绪强度和说话风格
4. 文化适配：适当本地化表达，但不要改变原意
5. 简洁明了：字幕长度适中，便于阅读

请以JSON数组格式返回翻译结果，每个元素只包含翻译后的中文文本，顺序与原文一致：
["翻译1", "翻译2", ...]""",
            
            TranslationStyle.YOUTUBE: """你是一位专业的日语→中文翻译专家，专门翻译油管/Vlog视频字幕。

翻译要求：
1. 轻松随意：像朋友聊天，不要太正式
2. 口语化：大量使用口语表达和网络用语
3. 幽默感：保留原文的幽默和趣味性
4. 简洁有力：短句为主，节奏明快
5. 本地化：适当使用中文网络流行语

请以JSON数组格式返回翻译结果，每个元素只包含翻译后的中文文本，顺序与原文一致：
["翻译1", "翻译2", ...]""",
            
            TranslationStyle.DOCUMENTARY: """你是一位专业的日语→中文翻译专家，专门翻译纪录片字幕。

翻译要求：
1. 准确规范：忠实原文，术语准确
2. 正式得体：使用规范的书面语
3. 信息完整：不遗漏任何重要信息
4. 结构清晰：长句合理断句，便于理解
5. 专业术语：专业名词保持原样或标准译法

请以JSON数组格式返回翻译结果，每个元素只包含翻译后的中文文本，顺序与原文一致：
["翻译1", "翻译2", ...]"""
        }
    
    def _load_term_maps(self):
        """加载术语表和纠错映射"""
        # 日语→中文术语映射
        self.term_map = {
            "おはよう": "早啊", "ありがとう": "谢谢啦", "ごめん": "抱歉", "ごめんなさい": "对不起啦",
            "すみません": "不好意思", "大好き": "最喜欢了", "死ぬ": "去死", "死ね": "去死吧",
            "許せない": "不可原谅", "許さない": "绝不原谅", "裏切った": "背叛了",
            "ふさわしい": "配得上", "気持ち": "心意", "うそ": "骗人", "嘘": "骗人",
            "うるさい": "吵死了", "だまれ": "闭嘴", "黙れ": "闭嘴",
            "むかつく": "烦死了", "気持ち悪い": "恶心", "最低": "差劲", "最悪": "糟透了",
            "やめて": "住手", "ほんと": "真的", "本当": "真的", "まじ": "真的假的",
            "お願い": "求你了", "待って": "等等", "ちょっと": "等一下",
            "頑張って": "加油", "すごい": "好厉害", "かわいい": "好可爱",
            "愛してる": "我爱你", "好き": "喜欢", "嫌い": "讨厌",
            "ずっと": "一直", "一緒に": "一起", "ずるい": "耍赖",
            "バカ": "笨蛋", "アホ": "傻瓜", "馬鹿": "笨蛋",
            "ありがと": "谢啦", "ありがとうございます": "非常感谢",
            "すみませんでした": "非常抱歉", "ごめんなさいね": "对不起嘛",
            "大好きだよ": "最喜欢你了", "愛してるよ": "我爱你哦",
            "嫌いだ": "讨厌你", "大嫌い": "最讨厌了",
            "助けて": "救命", "助けてください": "请救救我",
            "怖い": "好可怕", "恐い": "好恐怖",
            "嬉しい": "好开心", "楽しい": "好快乐",
            "悲しい": "好难过", "寂しい": "好寂寞",
            "怒ってる": "生气了", "怒った": "生气了",
            "驚いた": "吓到了", "びっくりした": "吓一跳",
            "困った": "麻烦了", "困ってる": "很困扰",
            "疲れた": "好累", "眠い": "好困",
            "お腹すいた": "肚子饿了", "喉渇いた": "口渴了",
            "行くよ": "走啦", "行こう": "走吧",
            "来て": "过来", "来い": "过来啊",
            "帰る": "回去了", "帰ろう": "回去吧",
            "始める": "开始吧", "始めよう": "开始吧",
            "終わる": "结束了", "終わろう": "结束吧",
            "待ってて": "等着我", "待ってね": "等我哦",
            "見て": "看啊", "見ろ": "看啊",
            "聞いて": "听我说", "聞け": "听着",
            "教えて": "告诉我", "教えろ": "告诉我",
            "分かった": "明白了", "分かりました": "明白了",
            "分からない": "不明白", "分かりません": "不明白",
            "知ってる": "知道", "知りません": "不知道",
            "できる": "能做到", "できない": "做不到",
            "やる": "做", "やらない": "不做",
            "行ける": "能去", "行けない": "不能去",
            "来れる": "能来", "来れない": "不能来",
            "食べる": "吃", "食べない": "不吃",
            "飲む": "喝", "飲まない": "不喝",
            "寝る": "睡", "寝ない": "不睡",
            "起きる": "起床", "起きない": "不起床",
            "働く": "工作", "働かない": "不工作",
            "遊ぶ": "玩", "遊ばない": "不玩",
            "学ぶ": "学习", "学ばない": "不学习",
            "考える": "思考", "考えない": "不思考",
            "感じる": "感受", "感じない": "感受不到",
            "信じる": "相信", "信じない": "不相信",
            "望む": "希望", "望まない": "不希望",
            "愛する": "爱", "愛さない": "不爱",
            "憎む": "恨", "憎まない": "不恨",
            "忘れる": "忘记", "忘れない": "不忘记",
            "覚える": "记住", "覚えない": "记不住",
            "探す": "寻找", "探さない": "不寻找",
            "見つける": "找到", "見つからない": "找不到",
            "失う": "失去", "失わない": "不失去",
            "得る": "得到", "得ない": "得不到",
            "変わる": "改变", "変わらない": "不改变",
            "続ける": "继续", "続けない": "不继续",
            "止める": "停止", "止めない": "不停止",
            "始まる": "开始", "始まらない": "不开始",
            "終わる": "结束", "終わらない": "不结束",
            "生きる": "活着", "生きない": "不活着",
            "死ぬ": "死", "死なない": "不死",
        }
        
        # Whisper ASR 常见错误纠正
        self.whisper_corrections = {
            "きまんまん": "調子に乗って",
            "酸酸": "すやすや",
            "広いろ": "広い",
            "イーグ": "伊格",
            "バリアーメト": "バリアント",
            "倒って": "そんなこと",
            "関差して": "関わって",
            "関差してほしい": "関わってほしい",
            "情談": "冗談",
            "要分": "用事",
            "変態に": "変態ね",
        }
    
    def _preprocess_text(self, text: str) -> str:
        """文本预处理：术语替换 + 纠错"""
        # 术语替换
        for jp, zh in self.term_map.items():
            if jp in text:
                text = text.replace(jp, zh)
        
        # Whisper 纠错
        for wrong, correct in self.whisper_corrections.items():
            if wrong in text:
                text = text.replace(wrong, correct)
        
        return text
    
    def translate_with_context(self, sentences: List[Dict], batch_size: int = None) -> List[Dict]:
        """
        带上下文的批量翻译
        每批10句带前3句上下文，场景分段发送给 DeepSeek
        
        Args:
            sentences: 句子列表，每个字典包含 {"start", "end", "text"}
            batch_size: 批次大小，默认使用配置中的 batch_size
        
        Returns:
            翻译后的句子列表，添加了 "translated_text" 字段
        """
        if not sentences:
            return []
        
        batch_size = batch_size or self.config.batch_size
        results = []
        
        print(f"开始上下文感知翻译，共 {len(sentences)} 句，批次大小: {batch_size}")
        
        for batch_idx in range(0, len(sentences), batch_size):
            batch = sentences[batch_idx:batch_idx + batch_size]
            
            # 构建带上下文的 prompt
            items_text = ""
            for i, s in enumerate(batch):
                idx = batch_idx + i
                # 预处理文本
                text = self._preprocess_text(s["text"])
                items_text += f"[{idx}] {text}\n"
            
            # 添加上下文（前N句）
            context = ""
            if batch_idx > 0:
                prev_start = max(0, batch_idx - self.config.context_window)
                for j in range(prev_start, batch_idx):
                    if j < len(sentences):
                        text = self._preprocess_text(sentences[j]["text"])
                        context += f"上文[{j}]: {text}\n"
            
            system_prompt = self.style_prompts.get(self.config.style, self.style_prompts[TranslationStyle.ANIME])
            
            user_prompt = f"""上下文：
{context}
待翻译句子（序号与上下文接续）：
{items_text}

请将以上 {len(batch)} 个句子翻译成中文，保持上下文连贯和语气一致。返回JSON数组。"""
            
            print(f"  翻译批次 {batch_idx//batch_size + 1}/{(len(sentences)+batch_size-1)//batch_size} "
                  f"(句子 {batch_idx+1}-{min(batch_idx+batch_size, len(sentences))})")
            
            try:
                # 调用 API
                if self.config.provider == "deepseek":
                    translations = self._call_deepseek_api(system_prompt, user_prompt, len(batch))
                else:
                    translations = self._call_openai_api(system_prompt, user_prompt, len(batch))
                
                # 合并结果
                for i, s in enumerate(batch):
                    s_copy = dict(s)
                    if i < len(translations):
                        s_copy["translated_text"] = translations[i]
                    else:
                        s_copy["translated_text"] = s_copy["text"]  # 失败时保留原文
                    results.append(s_copy)
                
                time.sleep(0.5)  # API 限流
                
            except Exception as e:
                print(f"  批次翻译失败: {e}")
                # 失败时保留原文
                for s in batch:
                    s_copy = dict(s)
                    s_copy["translated_text"] = s_copy["text"]
                    results.append(s_copy)
        
        print(f"翻译完成，共处理 {len(results)} 句")
        return results
    
    def _call_deepseek_api(self, system_prompt: str, user_prompt: str, expected_count: int) -> List[str]:
        """调用 DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False
        }
        
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        
        # 提取 JSON 数组
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        
        translations = json.loads(content)
        
        # 确保数量匹配
        if len(translations) != expected_count:
            print(f"警告: 期望 {expected_count} 个翻译，实际返回 {len(translations)} 个")
            if len(translations) > expected_count:
                translations = translations[:expected_count]
            else:
                translations.extend([""] * (expected_count - len(translations)))
        
        return translations
    
    def _call_openai_api(self, system_prompt: str, user_prompt: str, expected_count: int) -> List[str]:
        """调用 OpenAI API"""
        import openai
        
        client = openai.OpenAI(api_key=self.config.api_key)
        
        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        content = response.choices[0].message.content.strip()
        
        # 提取 JSON 数组
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        
        translations = json.loads(content)
        
        # 确保数量匹配
        if len(translations) != expected_count:
            print(f"警告: 期望 {expected_count} 个翻译，实际返回 {len(translations)} 个")
            if len(translations) > expected_count:
                translations = translations[:expected_count]
            else:
                translations.extend([""] * (expected_count - len(translations)))
        
        return translations
    
    def translate_scene(self, sentences: List[Dict], scene_description: str = "") -> List[Dict]:
        """
        场景翻译：整段一起翻译，适合连贯对话
        
        Args:
            sentences: 句子列表
            scene_description: 场景描述（可选）
        
        Returns:
            翻译后的句子列表
        """
        if not sentences:
            return []
        
        # 合并所有句子文本
        combined_text = "\n".join([f"{i+1}. {s['text']}" for i, s in enumerate(sentences)])
        
        system_prompt = self.style_prompts.get(self.config.style, self.style_prompts[TranslationStyle.ANIME])
        
        user_prompt = f"""以下是一个连贯的场景对话，请保持对话的连贯性和人物语气：

{combined_text}

请将以上 {len(sentences)} 个句子翻译成中文，保持对话的流畅自然。返回JSON数组。"""
        
        if scene_description:
            user_prompt = f"场景描述: {scene_description}\n\n" + user_prompt
        
        print(f"开始场景翻译，共 {len(sentences)} 句")
        
        try:
            if self.config.provider == "deepseek":
                translations = self._call_deepseek_api(system_prompt, user_prompt, len(sentences))
            else:
                translations = self._call_openai_api(system_prompt, user_prompt, len(sentences))
            
            results = []
            for i, s in enumerate(sentences):
                s_copy = dict(s)
                if i < len(translations):
                    s_copy["translated_text"] = translations[i]
                else:
                    s_copy["translated_text"] = s_copy["text"]
                results.append(s_copy)
            
            return results
            
        except Exception as e:
            print(f"场景翻译失败: {e}")
            # 失败时保留原文
            return [dict(s, translated_text=s["text"]) for s in sentences]


# 测试函数
def test_translator():
    """测试翻译器"""
    # 测试数据
    test_sentences = [
        {"start": 0.0, "end": 1.0, "text": "おはよう"},
        {"start": 2.0, "end": 3.0, "text": "よく眠れた？"},
        {"start": 4.0, "end": 5.0, "text": "大好きだよ"},
    ]
    
    # 从环境变量读取 API Key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("请设置环境变量 DEEPSEEK_API_KEY")
        return
    
    config = TranslationConfig(
        api_key=api_key,
        style=TranslationStyle.ANIME,
        batch_size=2
    )
    
    translator = ContextAwareTranslator(config)
    
    print("测试上下文感知翻译...")
    translated = translator.translate_with_context(test_sentences)
    
    print("\n翻译结果:")
    for i, s in enumerate(translated):
        print(f"{i+1}. 原文: {s['text']}")
        print(f"   翻译: {s.get('translated_text', 'N/A')}")
        print()


if __name__ == "__main__":
    test_translator()