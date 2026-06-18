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
    batch_size: int = 8   # 每批翻译的句子数
    context_window: int = 5  # 上下文窗口大小（前N句）
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
            TranslationStyle.ANIME: """你是一位专业的日语→中文翻译专家，专门翻译动漫/广播剧字幕。

翻译要求：
1. 口语化：像真人说话，不要书面语。用「嘛」「啊」「呀」「哦」「呢」等语气词
2. 上下文连贯：注意代词和前后句的逻辑关系，不要每句孤立翻译
3. 语气匹配：根据角色性格和当前情绪调整语气，保持角色一致性。愤怒、温柔、冷漠、兴奋等情绪都要准确传达
4. 避免翻译腔：不要逐字直译。中文要自然流畅，符合汉语口语习惯。避免生硬的"的"字堆砌和「进行」「加以」等书面词
5. 避免过度翻译：简短句子保持简短，不要扩充
6. 时长匹配：1秒以内的短句翻译也要短，1秒的句子不要翻译出超长中文
7. 常见日语句式处理：
   - 「〜よね」→ 「〜吧」「〜不是吗」
   - 「〜だよ」→ 「〜哦」「〜啦」「〜嘛」
   - 「〜なの」→ 「〜的呢」「〜啊」
   - 「〜てくれた」→ 「为我〜」「帮我〜」
   - 「〜ちゃった」→ 体现完成/遗憾感
8. 纯拟声词/简短感叹词处理（重要）：
   - 「うま」「ほんとに」「あっ」「えっ」「ふふ」「はぁ」等 —— 不要翻译成完整句子
   - 保留语气简洁处理，如「うま」→「嗯」/「唔」、「ほんとに」→「真的...」/「真是的」
   - 不能用完整主语谓语翻译拟声词，保持与其时长匹配的简短中文

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
    
    def translate_with_context(self, sentences: List[Dict], batch_size: int = None,
                                progress_callback=None) -> List[Dict]:
        """
        带上下文的批量翻译
        每批10句带前3句上下文，场景分段发送给 DeepSeek

        Args:
            sentences: 句子列表，每个字典包含 {"start", "end", "text"}
            batch_size: 批次大小，默认使用配置中的 batch_size
            progress_callback: 进度回调函数，签名: callback(current_batch, total_batches, current_text)

        Returns:
            翻译后的句子列表，添加了 "translated_text" 字段
        """
        if not sentences:
            return []

        batch_size = batch_size or self.config.batch_size
        results = []
        total_batches = (len(sentences) + batch_size - 1) // batch_size

        print(f"开始上下文感知翻译，共 {len(sentences)} 句，批次大小: {batch_size}")

        for batch_idx in range(0, len(sentences), batch_size):
            batch = sentences[batch_idx:batch_idx + batch_size]
            current_batch = batch_idx // batch_size + 1

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

            print(f"  翻译批次 {current_batch}/{total_batches} "
                  f"(句子 {batch_idx+1}-{min(batch_idx+batch_size, len(sentences))})")

            # 发送批次进度回调
            if progress_callback and len(batch) > 0:
                first_text = batch[0].get("text", "")[:40]
                progress_callback(current_batch, total_batches, first_text)

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
    
    def _parse_translation_response(self, content: str, expected_count: int) -> List[str]:
        """增强的JSON解析容错方法"""
        content = content.strip()
        
        # 处理 markdown code block
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join([l for l in lines if not l.strip().startswith("```")])
        
        # 尝试直接解析
        translations = None
        try:
            translations = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: 尝试提取 JSON 数组
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                try:
                    translations = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
        
        # 类型验证
        if translations is None:
            translations = []
        elif not isinstance(translations, list):
            # 如果是字典，尝试提取值
            if isinstance(translations, dict):
                translations = [translations.get(str(i), translations.get("text", "")) 
                              for i in range(len(translations))]
            else:
                translations = []
        
        # 数量匹配
        if len(translations) != expected_count:
            print(f"  JSON解析: 期望 {expected_count} 个翻译，实际返回 {len(translations)} 个")
            if len(translations) > expected_count:
                translations = translations[:expected_count]
            else:
                translations.extend([""] * (expected_count - len(translations)))
        
        return translations
    
    def _call_deepseek_api(self, system_prompt: str, user_prompt: str, expected_count: int) -> List[str]:
        """调用 DeepSeek API（带指数退避重试）"""
        import random
        
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
        
        max_retries = 5
        base_delay = 2  # 基础退避时间（秒）
        max_delay = 60   # 最大退避时间（秒）
        
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90
                )
                
                # 处理 Rate Limit (429)
                if resp.status_code == 429:
                    # 尝试从响应头获取 retry-after
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        delay = int(retry_after)
                    else:
                        # 指数退避 + 随机抖动
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    
                    if attempt < max_retries - 1:
                        print(f"  API 限流 (429)，等待 {delay:.1f} 秒后重试 (第 {attempt+1}/{max_retries} 次)...")
                        time.sleep(delay)
                        continue
                    else:
                        raise RuntimeError(f"API 限流 (429)，已达最大重试次数")
                
                resp.raise_for_status()

                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()

                # 增强的 JSON 解析容错
                translations = self._parse_translation_response(content, expected_count)
                return translations

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    print(f"  API 返回解析失败 ({e})，{delay:.1f} 秒后重试...")
                    time.sleep(delay)
                    continue
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    print(f"  API 请求失败 ({e})，{delay:.1f} 秒后重试...")
                    time.sleep(delay)
                    continue

        raise RuntimeError(f"DeepSeek API 调用失败 (重试{max_retries}次后): {last_error}")
    
    def _call_openai_api(self, system_prompt: str, user_prompt: str, expected_count: int) -> List[str]:
        """调用 OpenAI API（带指数退避重试）"""
        import openai
        import random
        
        max_retries = 5
        base_delay = 2  # 基础退避时间（秒）
        max_delay = 60   # 最大退避时间（秒）
        
        last_error = None
        for attempt in range(max_retries):
            try:
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
                
                # 增强的 JSON 解析容错
                translations = self._parse_translation_response(content, expected_count)
                return translations
                
            except openai.RateLimitError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    print(f"  OpenAI 限流 (RateLimitError)，{delay:.1f} 秒后重试...")
                    time.sleep(delay)
                    continue
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    print(f"  API 返回解析失败 ({e})，{delay:.1f} 秒后重试...")
                    time.sleep(delay)
                    continue
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    print(f"  API 请求失败 ({e})，{delay:.1f} 秒后重试...")
                    time.sleep(delay)
                    continue
        
        raise RuntimeError(f"OpenAI API 调用失败 (重试{max_retries}次后): {last_error}")
    
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


    def refine_translations(self, sentences: List[Dict], api_key: str = None, 
                          provider: str = None, model: str = None, style: str = None) -> List[Dict]:
        """
        二次精翻校对：批量审查并修正翻译

        每批 10 句，对每句提供前后各 2 句的上下文（原文+当前译文），
        由"字幕校对员"审查并修正。

        Args:
            sentences: 已翻译的句子列表，每句含 text 和 translated_text
            api_key: API Key（可选，默认使用配置中的 key）
            provider: 翻译引擎提供商（可选，默认使用配置中的 provider）
            model: 翻译模型（可选，默认使用配置中的 model）
            style: 翻译风格（可选，默认使用配置中的 style）

        Returns:
            修正后的句子列表（结构与输入一致）
        """
        if not sentences:
            return []

        if api_key:
            self.config.api_key = api_key
        
        if provider:
            self.config.provider = provider
        
        if model:
            self.config.model = model
        
        if style:
            self.config.style = style

        BATCH_SIZE = 10
        CONTEXT_WINDOW = 2  # 前后各 2 句
        results = []

        system_prompt = """你是一位「字幕校对员」，专门审查和修正日语→中文翻译字幕。

你的职责是逐句审查以下客观问题并修正：

1. **漏译 / 日文残留**：如果译文中仍有未翻译的日文，请翻译成中文
2. **译文过长或过短**：参考原文时长，译文应匹配原文长度。1秒以内的短句翻译也要短。
   如果译文明显过长或过短，请调整。
3. **明显错译**：如果译文与原文意思明显不符，请纠正。
4. **明显翻译腔**：如果译文有明显的翻译腔（生硬的直译、不符合汉语口语习惯），请改为自然流畅的中文。
5. **翻译已经合理的**：请保持原样，标注为「保持原样」，不要为了追求某种风格而无意义改写。
   不要强制统一所有句子的语气——不同角色、不同场景应有不同的语气，除非译文明显不符合上下文语境。

上下文信息会提供前后各 2 句的原文和当前译文，用于判断语气连贯性和上下文一致性。

请以 JSON 数组格式返回修正后的翻译，每个元素只包含修正后的中文文本，顺序与输入一致：
["修正翻译1", "修正翻译2", ...]"""

        total = len(sentences)
        print(f"开始二次精翻校对，共 {total} 句，批次大小: {BATCH_SIZE}")

        for batch_idx in range(0, total, BATCH_SIZE):
            batch = sentences[batch_idx:batch_idx + BATCH_SIZE]

            # 构建上下文
            context_parts = []
            for i_in_batch, s in enumerate(batch):
                idx = batch_idx + i_in_batch

                # 前 2 句上下文
                for offset in range(CONTEXT_WINDOW, 0, -1):
                    ctx_idx = idx - offset
                    if ctx_idx >= 0:
                        ctx = sentences[ctx_idx]
                        context_parts.append(
                            f"上文[{ctx_idx}]: 原文={ctx.get('text', '')}  当前译文={ctx.get('translated_text', '')}"
                        )

                # 当前句
                context_parts.append(
                    f"待审查[{idx}]: 原文={s.get('text', '')}  当前译文={s.get('translated_text', '')}"
                )

                # 后 2 句上下文
                for offset in range(1, CONTEXT_WINDOW + 1):
                    ctx_idx = idx + offset
                    if ctx_idx < total:
                        ctx = sentences[ctx_idx]
                        context_parts.append(
                            f"下文[{ctx_idx}]: 原文={ctx.get('text', '')}  当前译文={ctx.get('translated_text', '')}"
                        )

                context_parts.append("---")

            user_prompt = "上下文与待审查句子（「待审查」标记的为本批需要审查修正的句子）：\n\n" + "\n".join(context_parts)
            user_prompt += f"\n\n请审查以上 {len(batch)} 个「待审查」句子，返回修正后的 JSON 数组。"

            print(f"  校对批次 {batch_idx // BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1) // BATCH_SIZE} "
                  f"(句子 {batch_idx + 1}-{min(batch_idx + BATCH_SIZE, total)})")

            try:
                if self.config.provider == "deepseek":
                    refined_texts = self._call_deepseek_api(system_prompt, user_prompt, len(batch))
                else:
                    refined_texts = self._call_openai_api(system_prompt, user_prompt, len(batch))

                for i, s in enumerate(batch):
                    s_copy = dict(s)
                    if i < len(refined_texts):
                        s_copy["translated_text"] = refined_texts[i]
                    results.append(s_copy)

                time.sleep(0.5)

            except Exception as e:
                print(f"  校对批次失败: {e}，保留原译文")
                for s in batch:
                    results.append(dict(s))

        print(f"二次精翻校对完成，共处理 {len(results)} 句")
        return results


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