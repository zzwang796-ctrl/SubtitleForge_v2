#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译后处理模块 - 去AI味、口语化、连贯性检查
SubtitleForge v2 后处理流水线
"""

import json
import re
import random
from typing import List, Dict


class PostProcessor:
    """翻译后处理：去AI味、口语化、连贯性检查"""
    
    def __init__(self, style: str = "anime"):
        self.style = style
        self.load_style_rules()
        
        # 常见AI翻译痕迹
        self.ai_patterns = [
            (r"进行的", "做的"), (r"进行了", "做了"), (r"加以", ""),
            (r"被拴住", "被绑着"), (r"被拴", "被绑"), (r"拴住", "绑住"),
            (r"拴着", "绑着"), (r"拴", "绑"), (r"进行", "做"),
            (r"加以处理", "处理"), (r"进行处理", "处理"),
            (r"所", ""), (r"之", ""), (r"于", "在"),
            (r"便", "就"), (r"亦", "也"), (r"皆", "都"), (r"均", "都"),
            (r"较为", "比较"), (r"颇为", "挺"), (r"甚为", "很"),
            (r"极为", "极其"), (r"极其", "非常"), (r"非常之", "非常"),
            (r"非常地", "非常"), (r"的的", "的"), (r"了了", "了"),
            (r"吗吗", "吗"), (r"呢呢", "呢"), (r"啊啊", "啊"),
            (r"呀呀", "呀"), (r"哦哦", "哦"), (r"嘛嘛", "嘛"),
            (r"一个", "个"),
        ]
        
        # 语气词库（按情感强度）
        self.particles_by_emotion = {
            "normal": ["呢", "啊", "呀"],
            "happy": ["啦", "哟", "嘿"],
            "sad": ["唉", "呜", "嗯"],
            "angry": ["哼", "呸", "切"],
            "surprised": ["哇", "诶", "哈"],
            "confused": ["呃", "嗯", "这个"],
            "yandere": ["呵呵", "嘻嘻", "亲爱的"],
        }
    
    def load_style_rules(self):
        """加载风格配置"""
        try:
            with open("style_profiles.json", "r", encoding="utf-8") as f:
                self.style_profiles = json.load(f)
        except FileNotFoundError:
            self.style_profiles = {
                "anime": {
                    "name": "动漫/广播剧",
                    "tone": "conversational",
                    "use_honorifics": False,
                    "contractions": True,
                    "max_sentence_length": 25,
                    "particles": ["嘛", "啊", "呀", "哦", "呢"],
                },
                "drama": {
                    "name": "影视剧",
                    "tone": "natural",
                    "use_honorifics": True,
                    "contractions": False,
                    "max_sentence_length": 30,
                },
                "youtube": {
                    "name": "油管/Vlog",
                    "tone": "casual",
                    "use_honorifics": False,
                    "contractions": True,
                    "max_sentence_length": 30,
                },
                "documentary": {
                    "name": "纪录片",
                    "tone": "formal",
                    "use_honorifics": True,
                    "contractions": False,
                    "max_sentence_length": 35,
                }
            }
        
        self.current_style = self.style_profiles.get(self.style, self.style_profiles["anime"])
    
    def process(self, sentences: List[Dict]) -> List[Dict]:
        """对翻译后的句子列表进行后处理"""
        processed = []
        
        for i, sent in enumerate(sentences):
            processed_sent = sent.copy()
            text = sent.get("translated_text", sent.get("text", ""))
            
            if not text or text.strip() == "":
                processed.append(processed_sent)
                continue
            
            # 1. 去AI味
            text = self.remove_ai_flavor(text)
            
            # 2. 口语化
            text = self.conversationalize(text)
            
            # 3. 连贯性检查
            if i > 0 and i - 1 < len(processed):
                prev_text = processed[i-1].get("translated_text", "")
                if prev_text:
                    text = self.ensure_coherence(prev_text, text)
            
            # 4. 长度检查
            text = self.check_length(text)
            
            processed_sent["translated_text"] = text.strip()
            processed.append(processed_sent)
        
        return processed
    
    def remove_ai_flavor(self, text: str) -> str:
        """去除机器翻译痕迹"""
        for pattern, replacement in self.ai_patterns:
            text = re.sub(pattern, replacement, text)
        
        # 去除多余重复字
        text = re.sub(r"的+", "的", text)
        text = re.sub(r"了+", "了", text)
        
        return text
    
    def conversationalize(self, text: str) -> str:
        """口语化处理"""
        if self.current_style.get("contractions", False):
            contractions = {
                "不要": "别", "没有": "没", "不可以": "不能",
                "为什么": "为啥", "怎么办": "咋办",
                "做什么": "做啥", "说什么": "说啥",
            }
            for formal, casual in contractions.items():
                if formal in text:
                    text = text.replace(formal, casual)
        
        return text
    
    def ensure_coherence(self, prev_text: str, current_text: str) -> str:
        """检查与前句的连贯性"""
        if not prev_text:
            return current_text
        
        # 时态一致性（简化）
        if "了" in prev_text and len(current_text) < 15:
            if not any(marker in current_text for marker in ["了", "过", "正在", "在"]):
                pass  # 简单规则，避免过度修改
        
        # 避免过多重复词
        prev_words = set(re.findall(r'[\u4e00-\u9fff]+', prev_text))
        curr_words = set(re.findall(r'[\u4e00-\u9fff]+', current_text))
        
        return current_text
    
    def check_length(self, text: str) -> str:
        """检查句子长度"""
        max_len = self.current_style.get("max_sentence_length", 30)
        
        if len(text) > max_len:
            parts = re.split(r'[，,。!！?？；;]', text)
            if len(parts) > 1:
                text = parts[0] + "\u2026"
            else:
                text = text[:max_len-1] + "\u2026"
        
        return text
    
    def analyze_emotion(self, text: str) -> str:
        """简单情感分析"""
        anger_words = ["死", "杀", "恨", "讨厌", "可恶", "混蛋", "笨蛋"]
        sad_words = ["哭", "泪", "悲伤", "难过", "寂寞", "孤独"]
        happy_words = ["笑", "开心", "高兴", "喜欢", "爱", "幸福"]
        
        if any(word in text for word in anger_words):
            return "angry"
        elif any(word in text for word in sad_words):
            return "sad"
        elif any(word in text for word in happy_words):
            return "happy"
        else:
            return "normal"


# 工具函数
def load_sentences(filepath: str) -> List[Dict]:
    """加载句子数据"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sentences(sentences: List[Dict], filepath: str):
    """保存句子数据"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sentences, f, ensure_ascii=False, indent=2)


def compare_translations(old_sentences: List[Dict], new_sentences: List[Dict], n: int = 20) -> str:
    """对比新旧翻译"""
    comparison = "序号 | 日文原文 | 旧翻译 | 新翻译\n"
    comparison += "-" * 80 + "\n"
    
    for i in range(min(n, len(old_sentences), len(new_sentences))):
        old = old_sentences[i]
        new = new_sentences[i]
        
        jp = old.get("text", "")
        old_trans = old.get("translated_text", "")
        new_trans = new.get("translated_text", "")
        
        comparison += f"{i+1:3d} | {jp[:30]:30} | {old_trans[:30]:30} | {new_trans[:30]:30}\n"
    
    return comparison


if __name__ == "__main__":
    # 测试
    test_sentences = [
        {"start": 0.0, "end": 1.0, "text": "おはよう", "translated_text": "早上好"},
        {"start": 2.0, "end": 3.0, "text": "よく眠れた？", "translated_text": "睡得好吗？"},
        {"start": 4.0, "end": 5.0, "text": "大好きだよ", "translated_text": "非常喜欢你"},
    ]
    
    processor = PostProcessor(style="anime")
    processed = processor.process(test_sentences)
    
    for orig, proc in zip(test_sentences, processed):
        print(f"原: {orig['translated_text']}")
        print(f"后: {proc['translated_text']}")
        print()