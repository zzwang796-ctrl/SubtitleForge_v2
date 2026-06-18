#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDD 测试: T12 - JSON解析容错增强
验证 _parse_translation_response 方法的正确性
"""

import unittest
import sys
import os

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translator_v2 import ContextAwareTranslator


class TestParseTranslationResponse(unittest.TestCase):
    """测试 JSON 解析容错方法"""

    def setUp(self):
        """设置测试 fixtures"""
        # 创建一个带配置的翻译器实例（不需要真实 API key）
        from translator_v2 import TranslationConfig
        config = TranslationConfig(api_key="fake-key-for-testing")
        self.translator = ContextAwareTranslator(config)

    def test_parse_simple_json_array(self):
        """测试解析标准 JSON 数组"""
        content = '["翻译1", "翻译2", "翻译3"]'
        result = self.translator._parse_translation_response(content, 3)
        self.assertEqual(result, ["翻译1", "翻译2", "翻译3"])

    def test_parse_json_with_markdown_code_block(self):
        """测试解析带 markdown code block 的 JSON"""
        content = '''```json
["翻译1", "翻译2"]
```'''
        result = self.translator._parse_translation_response(content, 2)
        self.assertEqual(result, ["翻译1", "翻译2"])

    def test_parse_json_with_triple_backticks(self):
        """测试解析带三引号的 JSON"""
        content = '''```
["翻译1", "翻译2", "翻译3"]
```'''
        result = self.translator._parse_translation_response(content, 3)
        self.assertEqual(result, ["翻译1", "翻译2", "翻译3"])

    def test_parse_json_with_extra_text(self):
        """测试解析带前后多余文本的 JSON"""
        content = '''以下是翻译结果：
["翻译1", "翻译2"]

请查收。'''
        result = self.translator._parse_translation_response(content, 2)
        self.assertEqual(result, ["翻译1", "翻译2"])

    def test_parse_dict_instead_of_list(self):
        """测试当 API 返回字典而非数组时的处理"""
        content = '{"0": "翻译1", "1": "翻译2"}'
        result = self.translator._parse_translation_response(content, 2)
        self.assertEqual(result, ["翻译1", "翻译2"])

    def test_truncate_when_too_many(self):
        """测试翻译数量超过预期时截断"""
        content = '["翻译1", "翻译2", "翻译3", "翻译4", "翻译5"]'
        result = self.translator._parse_translation_response(content, 3)
        self.assertEqual(result, ["翻译1", "翻译2", "翻译3"])
        self.assertEqual(len(result), 3)

    def test_pad_when_too_few(self):
        """测试翻译数量不足时填充空字符串"""
        content = '["翻译1"]'
        result = self.translator._parse_translation_response(content, 3)
        self.assertEqual(result, ["翻译1", "", ""])
        self.assertEqual(len(result), 3)

    def test_parse_invalid_json_with_regex_fallback(self):
        """测试无效 JSON 时的正则 fallback"""
        content = '翻译1, 翻译2, 翻译3'
        # 这种情况下正则可能无法完美提取，先测试不会崩溃
        result = self.translator._parse_translation_response(content, 3)
        # 应该返回空列表或部分结果，不会抛出异常
        self.assertIsInstance(result, list)

    def test_empty_content(self):
        """测试空内容"""
        content = ''
        result = self.translator._parse_translation_response(content, 2)
        self.assertEqual(result, ["", ""])
        self.assertEqual(len(result), 2)

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        content = '   ["翻译1", "翻译2"]   '
        result = self.translator._parse_translation_response(content, 2)
        self.assertEqual(result, ["翻译1", "翻译2"])


if __name__ == '__main__':
    unittest.main()
