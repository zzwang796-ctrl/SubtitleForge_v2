#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SubtitleForge v2 - 后处理模块单元测试"""

import os
import sys
import json
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from post_processor import PostProcessor, load_sentences, save_sentences


class TestPostProcessorInit(unittest.TestCase):
    """测试 PostProcessor 的初始化"""

    def test_default_style(self):
        """测试默认使用 anime 风格"""
        pp = PostProcessor()
        self.assertEqual(pp.style, "anime")

    def test_custom_style(self):
        """测试使用自定义风格"""
        pp = PostProcessor(style="drama")
        self.assertEqual(pp.style, "drama")

    def test_ai_patterns_loaded(self):
        """测试 ai_patterns 不为空"""
        pp = PostProcessor()
        self.assertTrue(len(pp.ai_patterns) > 0)

    def test_style_profiles_loaded(self):
        """测试 style_profiles 包含预定义风格"""
        pp = PostProcessor()
        for key in ["anime", "drama", "youtube", "documentary"]:
            self.assertIn(key, pp.style_profiles)

    def test_current_style_is_dict(self):
        """测试 current_style 为字典结构"""
        pp = PostProcessor(style="anime")
        self.assertIsInstance(pp.current_style, dict)
        self.assertIn("max_sentence_length", pp.current_style)


class TestRemoveAiFlavor(unittest.TestCase):
    """测试 remove_ai_flavor 方法"""

    def setUp(self):
        self.pp = PostProcessor(style="anime")

    def test_replace_jin_xing_le(self):
        """测试 '进行了' 替换为 '做了'"""
        result = self.pp.remove_ai_flavor("他进行了检查")
        self.assertNotIn("进行了", result)
        self.assertIn("做了", result)

    def test_remove_suo(self):
        """测试 '所' 被移除"""
        result = self.pp.remove_ai_flavor("他所说的话")
        self.assertNotIn("所", result)

    def test_keep_other_words(self):
        """测试不影响其他普通文字"""
        text = "今天天气不错"
        result = self.pp.remove_ai_flavor(text)
        self.assertIn("今天", result)

    def test_empty_string(self):
        """测试空字符串输入"""
        self.assertEqual(self.pp.remove_ai_flavor(""), "")

    def test_de_duplication(self):
        """测试连续重复 '的' '了' 会被去除"""
        result = self.pp.remove_ai_flavor("好好的的的")
        self.assertEqual(result.count("的"), 1)


class TestConversationalize(unittest.TestCase):
    """测试 conversationalize 方法"""

    def test_replace_bu_yao_in_anime(self):
        """测试 anime 风格下 '不要' 替换为 '别'"""
        pp = PostProcessor(style="anime")
        result = pp.conversationalize("不要走")
        self.assertIn("别", result)
        self.assertNotIn("不要", result)

    def test_replace_mei_you_in_anime(self):
        """测试 anime 风格下 '没有' 替换为 '没'"""
        pp = PostProcessor(style="anime")
        result = pp.conversationalize("没有时间")
        self.assertIn("没", result)
        self.assertNotIn("没有", result)

    def test_drama_no_contractions(self):
        """测试 drama 风格不进行 contractions 替换"""
        pp = PostProcessor(style="drama")
        text = "不要走没有时间"
        result = pp.conversationalize(text)
        self.assertIn("不要", result)
        self.assertIn("没有", result)

    def test_empty_string(self):
        """测试空字符串输入"""
        pp = PostProcessor(style="anime")
        self.assertEqual(pp.conversationalize(""), "")


class TestEnsureCoherence(unittest.TestCase):
    """测试 ensure_coherence 方法"""

    def setUp(self):
        self.pp = PostProcessor()

    def test_empty_prev(self):
        """测试 prev_text 为空时直接返回 current"""
        result = self.pp.ensure_coherence("", "当前句")
        self.assertEqual(result, "当前句")

    def test_returns_string(self):
        """测试确保返回字符串"""
        result = self.pp.ensure_coherence("前一句内容", "当前句内容")
        self.assertIsInstance(result, str)

    def test_does_not_drop_content(self):
        """测试不会丢失当前句主要内容"""
        current = "今天去公园散步"
        result = self.pp.ensure_coherence("昨天在学校", current)
        self.assertIn("今天", result)


class TestCheckLength(unittest.TestCase):
    """测试 check_length 方法"""

    def test_short_text_unchanged(self):
        """测试短文本保持不变"""
        pp = PostProcessor(style="anime")
        short = "早上好"
        self.assertEqual(pp.check_length(short), short)

    def test_long_text_truncated(self):
        """测试长文本被截断并附加省略号"""
        pp = PostProcessor(style="anime")
        long_text = "今天的天气非常好阳光明媚万里无云我们决定一起去公园散步然后吃个饭再回家"
        result = pp.check_length(long_text)
        max_len = pp.current_style.get("max_sentence_length", 30)
        self.assertLessEqual(len(result), len(long_text))
        self.assertTrue(result.endswith("\u2026") or len(result) <= max_len)

    def test_long_text_with_punctuation(self):
        """测试带标点符号的长文本"""
        pp = PostProcessor(style="anime")
        text = "今天，我们去公园，然后一起去吃个饭，再回家看电影。"
        result = pp.check_length(text)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_documentary_longer_allowed(self):
        """测试 documentary 允许更长的句子"""
        pp_doc = PostProcessor(style="documentary")
        pp_anime = PostProcessor(style="anime")
        text = "这是一段描述历史背景的陈述性文字用于测试纪录片的长度限制"
        # 不同风格的 max_sentence_length 应不同
        self.assertGreater(
            pp_doc.current_style["max_sentence_length"],
            pp_anime.current_style["max_sentence_length"],
        )


class TestAnalyzeEmotion(unittest.TestCase):
    """测试 analyze_emotion 方法"""

    def setUp(self):
        self.pp = PostProcessor()

    def test_angry(self):
        """测试识别愤怒情绪"""
        self.assertEqual(self.pp.analyze_emotion("你这个混蛋，去死吧！"), "angry")

    def test_sad(self):
        """测试识别悲伤情绪"""
        self.assertEqual(self.pp.analyze_emotion("他难过地流下了眼泪"), "sad")

    def test_happy(self):
        """测试识别开心情绪"""
        self.assertEqual(self.pp.analyze_emotion("今天真开心，好幸福！"), "happy")

    def test_normal(self):
        """测试普通文本识别为 normal"""
        self.assertEqual(self.pp.analyze_emotion("今天天气不错"), "normal")


class TestProcess(unittest.TestCase):
    """测试 process 方法对完整句子列表的处理"""

    def setUp(self):
        self.pp = PostProcessor(style="anime")

    def test_empty_list(self):
        """测试空列表输入"""
        self.assertEqual(self.pp.process([]), [])

    def test_single_sentence(self):
        """测试单句处理"""
        sentences = [{"start": 0.0, "end": 1.0, "text": "おはよう", "translated_text": "早上好"}]
        result = self.pp.process(sentences)
        self.assertEqual(len(result), 1)
        self.assertIn("translated_text", result[0])

    def test_multiple_sentences(self):
        """测试多句处理"""
        sentences = [
            {"start": 0.0, "end": 1.0, "text": "おはよう", "translated_text": "早上好"},
            {"start": 2.0, "end": 3.0, "text": "よく", "translated_text": "睡得好不好"},
            {"start": 4.0, "end": 5.0, "text": "大好き", "translated_text": "非常喜欢你"},
        ]
        result = self.pp.process(sentences)
        self.assertEqual(len(result), 3)
        for sent in result:
            self.assertIn("translated_text", sent)

    def test_original_preserved(self):
        """测试原始字典不会被修改"""
        sentences = [{"translated_text": "进行了检查"}]
        original_text = sentences[0]["translated_text"]
        self.pp.process(sentences)
        self.assertEqual(sentences[0]["translated_text"], original_text)

    def test_empty_text_skipped(self):
        """测试空文本句保持原样"""
        sentences = [{"translated_text": ""}, {"translated_text": "   "}]
        result = self.pp.process(sentences)
        self.assertEqual(len(result), 2)

    def test_processed_text_is_string(self):
        """测试处理结果的 translated_text 是字符串"""
        sentences = [{"translated_text": "这是进行了检查的句子"}]
        result = self.pp.process(sentences)
        self.assertIsInstance(result[0]["translated_text"], str)

    def test_preserves_other_fields(self):
        """测试除文本外的字段被保留"""
        sentences = [
            {"start": 0.1, "end": 2.5, "text": "元の文", "translated_text": "做了一些事情"}
        ]
        result = self.pp.process(sentences)
        self.assertEqual(result[0]["start"], 0.1)
        self.assertEqual(result[0]["end"], 2.5)
        self.assertEqual(result[0]["text"], "元の文")


class TestDifferentStyles(unittest.TestCase):
    """测试不同风格配置的差异"""

    def test_anime_has_contractions(self):
        """测试 anime 风格启用 contractions"""
        pp = PostProcessor(style="anime")
        self.assertTrue(pp.current_style.get("contractions"))

    def test_drama_no_contractions(self):
        """测试 drama 风格禁用 contractions"""
        pp = PostProcessor(style="drama")
        self.assertFalse(pp.current_style.get("contractions"))

    def test_youtube_has_contractions(self):
        """测试 youtube 风格启用 contractions"""
        pp = PostProcessor(style="youtube")
        self.assertTrue(pp.current_style.get("contractions"))

    def test_documentary_no_contractions(self):
        """测试 documentary 风格禁用 contractions"""
        pp = PostProcessor(style="documentary")
        self.assertFalse(pp.current_style.get("contractions"))

    def test_max_sentence_length_variation(self):
        """测试各风格 max_sentence_length 不同"""
        pp_anime = PostProcessor(style="anime")
        pp_drama = PostProcessor(style="drama")
        pp_doc = PostProcessor(style="documentary")
        self.assertGreater(pp_doc.current_style["max_sentence_length"], pp_anime.current_style["max_sentence_length"])
        self.assertGreaterEqual(pp_drama.current_style["max_sentence_length"], pp_anime.current_style["max_sentence_length"])

    def test_anime_vs_drama_contraction_effect(self):
        """测试 anime 会收缩而 drama 不会"""
        pp_anime = PostProcessor(style="anime")
        pp_drama = PostProcessor(style="drama")
        text = "不要走没有时间"
        anime_result = pp_anime.conversationalize(text)
        drama_result = pp_drama.conversationalize(text)
        self.assertNotEqual(anime_result, drama_result)
        self.assertIn("不要", drama_result)

    def test_unknown_style_falls_back_to_anime(self):
        """测试未知风格会回退到 anime 配置"""
        pp = PostProcessor(style="nonexistent")
        self.assertEqual(pp.style, "nonexistent")
        # current_style 应该回退为 anime 的配置
        self.assertEqual(pp.current_style, pp.style_profiles["anime"])


class TestFileUtilities(unittest.TestCase):
    """测试 load_sentences / save_sentences 文件工具函数"""

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self.test_file.close()

    def tearDown(self):
        if os.path.exists(self.test_file.name):
            os.remove(self.test_file.name)

    def test_save_and_load(self):
        """测试 save 后 load 能还原内容"""
        data = [{"text": "おはよう", "translated_text": "早上好"}]
        save_sentences(data, self.test_file.name)
        loaded = load_sentences(self.test_file.name)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["text"], "おはよう")

    def test_saved_file_is_valid_json(self):
        """测试保存的文件可以被 json.load 解析"""
        data = [{"translated_text": "测试"}]
        save_sentences(data, self.test_file.name)
        with open(self.test_file.name, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        self.assertEqual(parsed, data)


if __name__ == "__main__":
    unittest.main()
