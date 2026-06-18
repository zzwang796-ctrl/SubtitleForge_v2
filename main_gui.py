#!/usr/bin/env python3
"""
SubtitleForge v2 - PyQt6 深色主题 GUI
三栏式布局 + 底部控制栏 + 流水线可视化
"""

import os
import sys
import json
import io
import threading
import requests

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSlider, QTextEdit,
    QGroupBox, QFileDialog, QMessageBox, QProgressBar, QFrame,
    QScrollArea, QSizePolicy, QSpacerItem, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve,
    QSize, QRect, QVariantAnimation, QParallelAnimationGroup, QSequentialAnimationGroup
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPainter, QPen, QBrush, QLinearGradient,
    QFontMetrics, QIcon
)

if getattr(sys, 'frozen', False):
    MODULE_DIR = os.path.dirname(sys.executable)
else:
    MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from pipeline_v2 import SubtitlePipelineV2
from config import config as subtitleforge_config


# ── 深色主题样式表 ──────────────────────────────────────────
DARK_THEME_QSS = """
QMainWindow {
    background-color: #1e1e2e;
}
QWidget {
    background-color: #1e1e2e;
    color: #e0e0e0;
    font-size: 13px;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
}

/* 卡片 / GroupBox */
QGroupBox {
    background-color: transparent;
    border: none;
    margin-top: 20px;
    padding: 16px 0px 12px 0px;
    font-weight: bold;
    font-size: 14px;
    color: #cdd6f4;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 0px;
    color: #cdd6f4;
}

/* 输入框 */
QLineEdit {
    background-color: #2d2d3f;
    border: 1px solid #3d3d5c;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e0e0;
    selection-background-color: #667eea;
}
QLineEdit:focus {
    border-color: #667eea;
}

/* 下拉框 */
QComboBox {
    background-color: #2d2d3f;
    border: 1px solid #3d3d5c;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e0e0;
}
QComboBox:hover { border-color: #667eea; }
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d3f;
    border: 1px solid #3d3d5c;
    border-radius: 6px;
    color: #e0e0e0;
    selection-background-color: #667eea;
}

/* 普通按钮 */
QPushButton {
    background-color: #363652;
    border: 1px solid #4a4a6a;
    border-radius: 8px;
    padding: 7px 18px;
    color: #e0e0e0;
    font-weight: bold;
    transition: background-color 300ms, border-color 300ms;
}
QPushButton:hover {
    background-color: #454575;
    border-color: #667eea;
}
QPushButton:pressed {
    background-color: #2a2a45;
}
QPushButton:disabled {
    background-color: #2a2a3e;
    color: #666;
    border-color: #333;
}

/* 验证按钮 */
QPushButton#validateBtn {
    background-color: #363652;
    border: 1px solid #4a4a6a;
    border-radius: 8px;
    padding: 7px 10px;
    color: #e0e0e0;
    font-size: 12px;
    font-weight: bold;
}
QPushButton#validateBtn:hover {
    background-color: #454575;
    border-color: #667eea;
}
QPushButton#validateBtn:pressed {
    background-color: #2a2a45;
}
QPushButton#validateBtn:disabled {
    background-color: #2a2a3e;
    color: #666;
    border-color: #333;
}

/* 开始处理按钮 */
QPushButton#startBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #667eea, stop:1 #764ba2);
    border: none;
    border-radius: 8px;
    padding: 10px 32px;
    color: white;
    font-size: 15px;
    font-weight: bold;
    transition: background 300ms;
}
QPushButton#startBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7b93f5, stop:1 #8c61b8);
}
QPushButton#startBtn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #5568d0, stop:1 #653b8e);
}
QPushButton#startBtn:disabled {
    background: #3a3a55;
    color: #777;
}

/* 停止按钮 */
QPushButton#stopBtn {
    background-color: #c0392b;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    color: white;
    font-size: 13px;
    font-weight: bold;
    transition: background-color 300ms;
}
QPushButton#stopBtn:hover { background-color: #e74c3c; }
QPushButton#stopBtn:disabled {
    background-color: #5a3535;
    color: #888;
}

/* 进度条 */
QProgressBar {
    background-color: transparent;
    border: 1px solid #3d3d5c;
    border-radius: 6px;
    text-align: center;
    color: white;
    height: 10px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #667eea, stop:1 #764ba2);
    border-radius: 5px;
}

/* 日志区 */
QTextEdit {
    background-color: #1a1a2e;
    border: 1px solid #3d3d5c;
    border-radius: 8px;
    padding: 8px;
    color: #c0c0d0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
}

/* 滑块 */
QSlider::groove:horizontal {
    background: #2d2d3f;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #667eea;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: #7b93f5; }

/* 滚动条 */
QScrollBar:vertical {
    background: #1e1e2e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3d3d5c;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #4a4a6a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* 分隔线 */
QFrame[HLine="true"] {
    background-color: #3d3d5c;
}
QFrame[VLine="true"] {
    background-color: #3d3d5c;
}
"""


# ── 流水线工作线程 ──────────────────────────────────────────
class PipelineWorker(QThread):
    """在后台线程执行流水线"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)        # 整体进度 0-100
    step_signal = pyqtSignal(int, str)       # 步骤编号, 状态(pending/running/done/error)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    batch_progress_signal = pyqtSignal(int, int, str)  # 当前批次, 总批次, 当前句子文本

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        original_stdout = sys.stdout
        redirector = _StdoutRedirector(self.log_signal.emit)
        sys.stdout = redirector

        try:
            pipeline = SubtitlePipelineV2(
                whisper_model=self.params.get("whisper_model", "base"),
                device=self.params.get("device", "cpu"),
            )

            # 阶段 1：音频提取
            self.step_signal.emit(1, "running")
            self.progress_signal.emit(5)
            wav_path = pipeline.extract_audio(
                self.params["video_path"],
                self.params["output_dir"]
            )
            self.step_signal.emit(1, "done")
            self.progress_signal.emit(20)

            # 阶段 2：语音识别
            self.step_signal.emit(2, "running")
            self.progress_signal.emit(25)
            transcript = pipeline.recognize_speech(
                wav_path, self.params["output_dir"],
                language=self.params.get("source_lang", "ja")
            )
            self.step_signal.emit(2, "done")
            self.progress_signal.emit(45)

            # 阶段 3：语义断句
            self.step_signal.emit(2, "done")  # 断句在 v2 中合并
            self.progress_signal.emit(50)
            sentences = pipeline.split_sentences(transcript, self.params["output_dir"])
            self.progress_signal.emit(55)

            # 阶段 4：上下文感知翻译
            self.step_signal.emit(3, "running")
            self.progress_signal.emit(60)

            # 创建批次进度回调
            def batch_progress_callback(current_batch, total_batches, current_text):
                self.batch_progress_signal.emit(current_batch, total_batches, current_text)

            translated = pipeline.translate_subtitles_v2(
                sentences, self.params["output_dir"],
                self.params["api_key"],
                style=self.params.get("style", "anime"),
                provider=self.params.get("provider", "deepseek"),
                model=self.params.get("model", "deepseek-chat"),
                progress_callback=batch_progress_callback,
            )
            self.step_signal.emit(3, "done")
            self.progress_signal.emit(65)

            # 阶段 5：后处理润色
            processed = pipeline.post_process(
                translated,
                style=self.params.get("style", "anime")
            )
            self.progress_signal.emit(72)

            # 阶段 6：生成字幕文件
            self.step_signal.emit(4, "running")
            processed_path = os.path.join(self.params["output_dir"], "final_subtitles_v2.json")
            with open(processed_path, 'w', encoding='utf-8') as f:
                json.dump(processed, f, ensure_ascii=False, indent=2)

            bilingual_srt = os.path.join(self.params["output_dir"], "subtitle_bilingual_v2.srt")
            pipeline.generate_srt(processed, bilingual_srt, True, True)

            chinese_srt = os.path.join(self.params["output_dir"], "subtitle_zh_v2.srt")
            pipeline.generate_srt(processed, chinese_srt, False, True)

            text_path = os.path.join(self.params["output_dir"], "video_subtitle_result_v2.txt")
            pipeline._export_text_result(processed, text_path, self.params.get("style", "anime"))

            self.step_signal.emit(4, "done")
            self.progress_signal.emit(90)

            # 阶段 7：字幕烧录
            self.step_signal.emit(5, "running")
            self.progress_signal.emit(95)
            video_output = pipeline.burn_subtitles(
                self.params["video_path"],
                bilingual_srt,
                self.params["output_dir"],
                zh_font_size=self.params.get("zh_font_size", 52),
                jp_font_size=self.params.get("jp_font_size", 44),
                font_name=self.params.get("font_name", "微软雅黑")
            )
            self.step_signal.emit(5, "done")
            self.progress_signal.emit(100)

            result = {
                "wav_path": wav_path,
                "bilingual_srt": bilingual_srt,
                "chinese_srt": chinese_srt,
                "final_json": processed_path,
                "text_result": text_path,
                "video_with_subtitles": video_output,
                "sentences_count": len(processed),
            }
            self.finished_signal.emit(result)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log_signal.emit(f"[错误] {e}")
            self.log_signal.emit(tb)
            self.error_signal.emit(str(e))

        finally:
            sys.stdout = original_stdout


class _StdoutRedirector(io.StringIO):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def write(self, s):
        super().write(s)
        if self.callback and s.strip():
            self.callback(s.rstrip())

    def flush(self):
        pass


# ── 步骤卡片组件 ────────────────────────────────────────────
class StepCard(QFrame):
    """流水线步骤卡片，带圆形编号和状态指示"""

    def __init__(self, step_num: int, title: str, parent=None):
        super().__init__(parent)
        self.step_num = step_num
        self.title = title
        self.status = "pending"  # pending / running / done / error

        self.setFixedHeight(68)
        self.setStyleSheet("""
            QFrame#stepCard {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
        """)
        self.setObjectName("stepCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        # 圆形编号
        self.circle = QLabel()
        self.circle.setFixedSize(36, 36)
        self.circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.circle.setStyleSheet(self._circle_style())
        layout.addWidget(self.circle)

        # 标题 + 副标题
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        text_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(self._subtitle())
        self.subtitle_label.setStyleSheet("font-size: 11px; color: #888;")
        text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout)
        layout.addStretch()

        # 状态指示
        self.status_label = QLabel("等待中")
        self.status_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self.status_label)

        # 旋转动画计时器
        self._anim_timer = None
        self._anim_angle = 0

        # 状态切换动画
        self.circle_anim = QPropertyAnimation(self.circle, b"styleSheet")
        self.circle_anim.setDuration(400)
        self.circle_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.status_anim = QPropertyAnimation(self.status_label, b"styleSheet")
        self.status_anim.setDuration(400)
        self.status_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _circle_style(self):
        return """
            background-color: transparent;
            border: 2px solid #4a4a6a;
            border-radius: 18px;
            font-size: 16px;
            font-weight: bold;
            color: #888;
        """

    def _subtitle(self):
        subtitles = {
            1: "从视频中提取音频轨道",
            2: "Whisper 语音转文字",
            3: "上下文感知智能翻译",
            4: "生成 SRT 字幕文件",
        }
        return subtitles.get(self.step_num, "")

    def set_status(self, status: str):
        self.status = status
        colors = {
            "pending": ("等待中", "#666", "transparent", "#4a4a6a", "#888"),
            "running": ("进行中", "#667eea", "transparent", "#667eea", "#667eea"),
            "done":    ("已完成", "#27ae60", "transparent", "#27ae60", "#27ae60"),
            "error":   ("失败",   "#e74c3c", "transparent", "#e74c3c", "#e74c3c"),
        }
        text, fg, bg, border, circle_fg = colors.get(status, colors["pending"])

        # 状态文字动画
        self.status_anim.setStartValue(self.status_label.styleSheet())
        self.status_anim.setEndValue(f"font-size: 12px; color: {fg}; font-weight: bold;")
        self.status_anim.start()

        if status == "done":
            self.circle.setText("\u2713")  # 绿色勾
        elif status == "error":
            self.circle.setText("\u2717")  # 红色叉
        else:
            self.circle.setText(f"{self.step_num}")

        # 圆形动画
        circle_style = f"""
            background-color: {bg};
            border: 2px solid {border};
            border-radius: 18px;
            font-size: 16px;
            font-weight: bold;
            color: {circle_fg};
        """
        self.circle_anim.setStartValue(self.circle.styleSheet())
        self.circle_anim.setEndValue(circle_style)
        self.circle_anim.start()

        if status == "running":
            self._start_animation()
        else:
            self._stop_animation()

    def _start_animation(self):
        if self._anim_timer is None:
            self._anim_timer = QTimer(self)
            self._anim_timer.timeout.connect(self._anim_tick)
            self._anim_timer.start(50)

    def _stop_animation(self):
        if self._anim_timer:
            self._anim_timer.stop()
            self._anim_timer = None

    def _anim_tick(self):
        self._anim_angle = (self._anim_angle + 12) % 360
        a = self._anim_angle
        self.circle.setStyleSheet(f"""
            background: qconicalgradient(cx:0.5, cy:0.5, angle:{a},
                stop:0 #667eea, stop:0.5 transparent, stop:1 #667eea);
            border: 2px solid #667eea;
            border-radius: 18px;
            font-size: 16px;
            font-weight: bold;
            color: #667eea;
        """)


# ── 连接线组件 ──────────────────────────────────────────────
class ConnectorLine(QFrame):
    """步骤之间的竖线连接"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(2, 18)
        self.setStyleSheet("background-color: #3d3d5c; border: none;")


# ── 主窗口 ──────────────────────────────────────────────────
class SubtitleForgeMainWindow(QMainWindow):
    VIDEO_EXTENSIONS = "视频文件 (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm *.m4v);;所有文件 (*.*)"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SubtitleForge v2")
        self.resize(1100, 750)
        self.setMinimumSize(950, 650)
        self.setStyleSheet(DARK_THEME_QSS)

        self.processing = False
        self.worker = None

        # 加载保存的配置
        self._load_settings()

        self._center_window()
        self._build_ui()

        # 应用保存的设置到控件
        self._apply_saved_settings()

        # 窗口淡入动画
        self._window_opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._window_opacity_anim.setDuration(300)
        self._window_opacity_anim.setStartValue(0.0)
        self._window_opacity_anim.setEndValue(1.0)

        # 进度条动画
        self._progress_anim = QPropertyAnimation(self.progress_bar, b"value")
        self._progress_anim.setDuration(300)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _load_settings(self):
        """从配置文件加载设置"""
        try:
            from config import config
            self._saved_config = config.load_gui_config()
        except Exception:
            self._saved_config = {}

    def _apply_saved_settings(self):
        """应用保存的设置到UI控件"""
        # 应用 Whisper 模型
        if hasattr(self, 'whisper_combo') and 'whisper_model' in self._saved_config:
            model = self._saved_config.get('whisper_model', 'base')
            index = self.whisper_combo.findText(model)
            if index >= 0:
                self.whisper_combo.setCurrentIndex(index)

        # 应用翻译风格
        if hasattr(self, 'style_combo') and 'style' in self._saved_config:
            style = self._saved_config.get('style', 'anime')
            index = self.style_combo.findText(style)
            if index >= 0:
                self.style_combo.setCurrentIndex(index)

        # 应用字体设置
        if hasattr(self, 'zh_font_size') and 'zh_font_size' in self._saved_config:
            size = self._saved_config.get('zh_font_size', 52)
            self.zh_font_size.setValue(size)
            self._update_font_label('zh', size)

        if hasattr(self, 'ja_font_size') and 'ja_font_size' in self._saved_config:
            size = self._saved_config.get('ja_font_size', 44)
            self.ja_font_size.setValue(size)
            self._update_font_label('jp', size)

        if hasattr(self, 'font_combo') and 'font_name' in self._saved_config:
            font = self._saved_config.get('font_name', 'Microsoft YaHei')
            index = self.font_combo.findText(font)
            if index >= 0:
                self.font_combo.setCurrentIndex(index)

    def _center_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - 1100) // 2
        y = (screen.height() - 750) // 2
        self.move(x, y)

    def showEvent(self, event):
        """窗口显示时触发淡入动画"""
        super().showEvent(event)
        self._window_opacity_anim.start()

    def closeEvent(self, event):
        """窗口关闭时保存配置"""
        try:
            from config import config

            # 获取当前控件的值
            whisper_model = self.whisper_combo.currentText() if hasattr(self, 'whisper_combo') else 'base'
            style = self.style_combo.currentText() if hasattr(self, 'style_combo') else 'anime'
            zh_font_size = self.zh_font_size.value() if hasattr(self, 'zh_font_size') else 52
            ja_font_size = self.ja_font_size.value() if hasattr(self, 'ja_font_size') else 44
            font_name = self.font_combo.currentText() if hasattr(self, 'font_combo') else 'Microsoft YaHei'

            # 获取 API Key（如果有输入的话）
            api_key = None
            api_provider = None
            if hasattr(self, 'api_key_input'):
                key = self.api_key_input.text().strip()
                if key and not key.startswith("*") and not key.startswith("sk-"):
                    # 如果是新输入的 key（明文形式）
                    provider_combo = self.provider_combo.currentText().lower() if hasattr(self, 'provider_combo') else 'deepseek'
                    api_key = key
                    api_provider = provider_combo

            # 保存配置
            config.save_gui_config(
                whisper_model=whisper_model,
                style=style,
                zh_font_size=zh_font_size,
                ja_font_size=ja_font_size,
                font_name=font_name,
                api_key=api_key,
                api_provider=api_provider,
            )

            print(f"[SubtitleForge] 配置已保存")
        except Exception as e:
            print(f"[SubtitleForge] 保存配置时出错: {e}")

        # 接受关闭事件
        event.accept()

    # ── 构建界面 ───────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 8)
        root_layout.setSpacing(8)

        # ─── 三栏主体 ───
        main_row = QHBoxLayout()
        main_row.setSpacing(10)

        main_row.addLayout(self._build_left_panel(), 3)    # 300px
        main_row.addLayout(self._build_center_panel(), 5)  # 500px
        main_row.addLayout(self._build_right_panel(), 3)   # 300px

        root_layout.addLayout(main_row, 1)

        # ─── 底部控制栏 ───
        root_layout.addLayout(self._build_bottom_bar())

    # ── 左侧面板：文件管理 ──────────────────────────────────
    def _build_left_panel(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # 标题
        title = QLabel("文件管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4; padding: 4px 0;")
        layout.addWidget(title)

        # 拖拽区域
        self.drop_frame = QFrame()
        self.drop_frame.setStyleSheet("""
            QFrame#dropFrame {
                background-color: transparent;
                border: 2px dashed #4a4a6a;
                border-radius: 12px;
            }
            QFrame#dropFrame:hover {
                border-color: #667eea;
                background-color: #1e1e2e;
            }
        """)
        self.drop_frame.setObjectName("dropFrame")
        self.drop_frame.setFixedHeight(80)
        self.drop_frame.setAcceptDrops(True)

        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_hint = QLabel("拖拽视频文件到此处")
        drop_hint.setStyleSheet("color: #666; font-size: 13px;")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_hint)

        self.drop_frame.dragEnterEvent = self._drag_enter
        self.drop_frame.dropEvent = self._drop_file

        layout.addWidget(self.drop_frame)

        # 选择文件按钮
        self.select_btn = QPushButton("选择文件")
        self.select_btn.setStyleSheet("padding: 6px 14px;")
        self.select_btn.clicked.connect(self._browse_video)
        layout.addWidget(self.select_btn)

        # 文件信息卡片
        info_group = QGroupBox("文件信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(6)

        self.info_name = QLabel("未选择文件")
        self.info_name.setStyleSheet("color: #888; font-size: 12px;")
        self.info_name.setWordWrap(True)
        info_layout.addWidget(self.info_name)

        self.info_size = QLabel("")
        self.info_size.setStyleSheet("color: #777; font-size: 12px;")
        info_layout.addWidget(self.info_size)

        layout.addWidget(info_group)

        # 日志区域
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(6, 6, 6, 6)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e;
                border: 1px solid #3d3d5c;
                border-radius: 8px;
                padding: 8px;
                color: #c0c0d0;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group, 1)

        return layout

    # ── 中间面板：流水线可视化 ───────────────────────────────
    def _build_center_panel(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)

        title = QLabel("处理流水线")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4; padding: 4px 0;")
        layout.addWidget(title)

        # 流水线容器
        pipe_container = QFrame()
        pipe_container.setStyleSheet("""
            QFrame#pipeContainer {
                background-color: transparent;
                border: none;
            }
        """)
        pipe_container.setObjectName("pipeContainer")
        pipe_layout = QVBoxLayout(pipe_container)
        pipe_layout.setSpacing(0)
        pipe_layout.setContentsMargins(16, 16, 16, 16)
        pipe_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        steps_info = [
            (1, "音频提取"),
            (2, "语音识别"),
            (3, "字幕翻译"),
            (4, "字幕生成"),
            (5, "字幕烧录"),
        ]

        self.step_cards = []

        for i, (num, name) in enumerate(steps_info):
            card = StepCard(num, name)
            pipe_layout.addWidget(card)
            self.step_cards.append(card)

            if i < len(steps_info) - 1:
                conn = ConnectorLine()
                pipe_layout.addWidget(conn, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(pipe_container)

        # 整体进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setFormat("就绪")
        layout.addWidget(self.progress_bar)

        layout.addStretch()

        return layout

    # ── 右侧面板：设置 ──────────────────────────────────────
    def _build_right_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4; padding: 4px 0;")
        layout.addWidget(title)

        # 语言设置
        lang_group = QGroupBox("语言设置")
        lang_layout = QVBoxLayout(lang_group)
        lang_layout.setSpacing(6)

        lang_layout.addWidget(QLabel("源语言"))
        self.source_lang = QComboBox()
        self.source_lang.addItems(["日语", "英语", "中文", "自动检测"])
        self.source_lang.setCurrentIndex(0)
        lang_layout.addWidget(self.source_lang)

        lang_layout.addWidget(QLabel("目标语言"))
        self.target_lang = QComboBox()
        self.target_lang.addItems(["中文", "英语", "日语"])
        self.target_lang.setCurrentIndex(0)
        lang_layout.addWidget(self.target_lang)

        layout.addWidget(lang_group)

        # 引擎设置
        engine_group = QGroupBox("引擎设置")
        engine_layout = QVBoxLayout(engine_group)
        engine_layout.setSpacing(6)

        engine_layout.addWidget(QLabel("翻译引擎"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["DeepSeek", "OpenAI"])
        self.engine_combo.setCurrentIndex(0)
        engine_layout.addWidget(self.engine_combo)

        engine_layout.addWidget(QLabel("API Key"))
        api_key_row = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        # 从配置中加载保存的 API Key
        default_provider = subtitleforge_config.get("api.provider", "deepseek")
        saved_key = subtitleforge_config.get_api_key(default_provider)
        if saved_key:
            self.api_key_input.setText(saved_key)
        self.api_key_input.setMinimumWidth(200)
        api_key_row.addWidget(self.api_key_input)
        self.validate_key_btn = QPushButton("验证")
        self.validate_key_btn.setObjectName("validateBtn")
        self.validate_key_btn.setFixedWidth(48)
        self.validate_key_btn.clicked.connect(self._validate_api_key)
        api_key_row.addWidget(self.validate_key_btn)
        engine_layout.addLayout(api_key_row)

        engine_layout.addWidget(QLabel("翻译风格"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["anime", "drama", "youtube", "documentary"])
        self.style_combo.setCurrentIndex(0)
        engine_layout.addWidget(self.style_combo)

        engine_layout.addWidget(QLabel("Whisper 模型"))
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.whisper_combo.setCurrentIndex(1)
        engine_layout.addWidget(self.whisper_combo)

        engine_layout.addWidget(QLabel("设备"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "cuda"])
        self.device_combo.setCurrentIndex(0)
        engine_layout.addWidget(self.device_combo)

        layout.addWidget(engine_group)

        # 字幕样式
        style_group = QGroupBox("字幕样式")
        style_layout = QVBoxLayout(style_group)
        style_layout.setSpacing(6)

        # 中文字号
        style_layout.addWidget(QLabel("中文字号 (20-60)"))
        zh_font_row = QHBoxLayout()
        self.zh_font_size = QSlider(Qt.Orientation.Horizontal)
        self.zh_font_size.setRange(20, 60)
        self.zh_font_size.setValue(52)
        self.zh_font_label = QLabel("52px")
        self.zh_font_label.setStyleSheet("color: #888; font-size: 12px; min-width: 36px;")
        self.zh_font_size.valueChanged.connect(lambda v: self.zh_font_label.setText(f"{v}px"))
        zh_font_row.addWidget(self.zh_font_size)
        zh_font_row.addWidget(self.zh_font_label)
        style_layout.addLayout(zh_font_row)

        # 日文字号
        style_layout.addWidget(QLabel("日文字号 (20-60)"))
        ja_font_row = QHBoxLayout()
        self.ja_font_size = QSlider(Qt.Orientation.Horizontal)
        self.ja_font_size.setRange(20, 60)
        self.ja_font_size.setValue(44)
        self.ja_font_label = QLabel("44px")
        self.ja_font_label.setStyleSheet("color: #888; font-size: 12px; min-width: 36px;")
        self.ja_font_size.valueChanged.connect(lambda v: self.ja_font_label.setText(f"{v}px"))
        ja_font_row.addWidget(self.ja_font_size)
        ja_font_row.addWidget(self.ja_font_label)
        style_layout.addLayout(ja_font_row)

        style_layout.addWidget(QLabel("字体"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(["微软雅黑", "黑体", "宋体"])
        self.font_combo.setCurrentIndex(0)
        style_layout.addWidget(self.font_combo)

        layout.addWidget(style_group)

        # 输出目录
        out_group = QGroupBox("输出目录")
        out_layout = QVBoxLayout(out_group)
        out_layout.setSpacing(6)

        out_row = QHBoxLayout()
        default_output = os.path.join(MODULE_DIR, "output")
        self.output_dir_input = QLineEdit(default_output)
        out_row.addWidget(self.output_dir_input)

        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(50)
        browse_btn.clicked.connect(self._browse_output)
        out_row.addWidget(browse_btn)
        out_layout.addLayout(out_row)

        layout.addWidget(out_group)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout()
        outer.addWidget(scroll)
        return outer

    # ── 底部控制栏 ──────────────────────────────────────────
    def _build_bottom_bar(self):
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.start_btn = QPushButton("开始处理")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setFixedHeight(42)
        self.start_btn.clicked.connect(self._start_processing)
        bar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setFixedHeight(42)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_processing)
        bar.addWidget(self.stop_btn)

        self.open_output_btn = QPushButton("打开输出目录")
        self.open_output_btn.setFixedHeight(42)
        self.open_output_btn.clicked.connect(self._open_output)
        bar.addWidget(self.open_output_btn)

        bar.addStretch()

        self.status_indicator = QLabel("就绪")
        self.status_indicator.setStyleSheet("""
            font-size: 13px; font-weight: bold; color: #666;
            padding: 6px 16px;
            background-color: transparent;
        """)
        bar.addWidget(self.status_indicator)

        return bar

    # ── 拖拽事件 ────────────────────────────────────────────
    def _drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_frame.setStyleSheet("""
                QFrame#dropFrame {
                    background-color: #1e1e2e;
                    border: 2px dashed #667eea;
                    border-radius: 12px;
                }
            """)

    def dropEvent(self, event):
        """兼容旧版 Qt 命名"""
        self._drop_file(event)

    def _drop_file(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_video_path(path)
        self.drop_frame.setStyleSheet("""
            QFrame#dropFrame {
                background-color: transparent;
                border: 2px dashed #4a4a6a;
                border-radius: 12px;
            }
            QFrame#dropFrame:hover {
                border-color: #667eea;
                background-color: #1e1e2e;
            }
        """)

    # ── 浏览视频文件 ────────────────────────────────────────
    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "", self.VIDEO_EXTENSIONS
        )
        if path:
            self._set_video_path(path)

    def _set_video_path(self, path):
        self.video_path = path
        self.info_name.setText(os.path.basename(path))
        size_bytes = os.path.getsize(path)
        if size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            size_str = f"{size_bytes / (1024*1024):.1f} MB"
        else:
            size_str = f"{size_bytes / (1024*1024*1024):.2f} GB"
        self.info_size.setText(f"大小: {size_str}")
        self._append_log(f"已选择: {path}")

    # ── 浏览输出目录 ────────────────────────────────────────
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_input.setText(path)

    # ── 字体设置更新 ───────────────────────────────────────────
    def _update_font_label(self, lang: str, size: int):
        """更新字体大小标签"""
        if lang == 'zh':
            if hasattr(self, 'zh_font_label'):
                self.zh_font_label.setText(f"{size}px")
        elif lang == 'jp':
            if hasattr(self, 'jp_font_label'):
                self.jp_font_label.setText(f"{size}px")

    # ── 日志 ────────────────────────────────────────────────
    def _append_log(self, msg: str):
        self.log_text.append(msg)

    # ── 验证 API Key ───────────────────────────────────────────
    def _validate_api_key(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "验证失败", "请输入 API Key")
            return

        provider = "deepseek" if self.engine_combo.currentText() == "DeepSeek" else "openai"
        self.validate_key_btn.setText("...")
        self.validate_key_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            if provider == "deepseek":
                url = "https://api.deepseek.com/v1/models"
            else:
                url = "https://api.openai.com/v1/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                QMessageBox.information(self, "验证通过",
                    f"{self.engine_combo.currentText()} API Key 有效")
            elif resp.status_code == 401:
                QMessageBox.critical(self, "验证失败",
                    "API Key 无效或已过期，请检查后重试\n\n可前往对应平台重新生成 Key：\n"
                    "DeepSeek: https://platform.deepseek.com/api_keys\n"
                    "OpenAI:   https://platform.openai.com/api-keys")
            else:
                body = resp.text[:300]
                QMessageBox.warning(self, "验证异常", f"HTTP {resp.status_code}：\n{body}")
        except Exception as e:
            QMessageBox.critical(self, "验证失败", f"网络请求异常：\n{e}")
        finally:
            self.validate_key_btn.setText("验证")
            self.validate_key_btn.setEnabled(True)

    # ── 开始处理 ────────────────────────────────────────────
    def _start_processing(self):
        if not hasattr(self, 'video_path') or not self.video_path:
            QMessageBox.warning(self, "提示", "请先选择视频文件")
            return
        if not os.path.exists(self.video_path):
            QMessageBox.warning(self, "提示", "视频文件不存在")
            return

        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return

        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            output_dir = os.path.join(MODULE_DIR, "output")
            self.output_dir_input.setText(output_dir)

        src_lang_map = {"日语": "ja", "英语": "en", "中文": "zh", "自动检测": None}
        src_lang = src_lang_map.get(self.source_lang.currentText(), "ja")

        provider_map = {"DeepSeek": "deepseek", "OpenAI": "openai"}
        provider = provider_map.get(self.engine_combo.currentText(), "deepseek")

        params = {
            "video_path": self.video_path,
            "output_dir": output_dir,
            "api_key": api_key,
            "source_lang": src_lang,
            "style": self.style_combo.currentText(),
            "provider": provider,
            "model": "deepseek-chat" if provider == "deepseek" else "gpt-4o",
            "whisper_model": self.whisper_combo.currentText(),
            "device": self.device_combo.currentText(),
            "zh_font_size": self.zh_font_size.value(),
            "jp_font_size": 44,  # 日语字号固定为中文的85%
            "font_name": self.font_combo.currentText(),
        }

        self.processing = True
        self._set_controls_enabled(False)

        self.log_text.clear()
        self._append_log("=" * 60)
        self._append_log("SubtitleForge v2 - 开始处理")
        self._append_log("=" * 60)
        self._append_log(f"视频:   {self.video_path}")
        self._append_log(f"风格:   {params['style']}")
        self._append_log(f"引擎:   {params['provider']}")
        self._append_log(f"模型:   {params['whisper_model']} @ {params['device']}")
        self._append_log(f"输出:   {output_dir}")
        self._append_log("=" * 60)

        # 重置步骤状态
        for card in self.step_cards:
            card.set_status("pending")
        
        # 进度条动画
        self._progress_anim.setStartValue(self.progress_bar.value())
        self._progress_anim.setEndValue(0)
        self._progress_anim.start()
        
        self.progress_bar.setFormat("处理中...")
        self.status_indicator.setText("处理中...")
        self.status_indicator.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #667eea; padding: 6px 16px; background-color: transparent;"
        )

        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)

        self.worker = PipelineWorker(params)
        self.worker.log_signal.connect(self._append_log)
        self.worker.progress_signal.connect(self._update_progress)
        self.worker.step_signal.connect(self._update_step)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.batch_progress_signal.connect(self._update_batch_progress)
        self.worker.start()

    def _update_progress(self, value: int):
        """更新进度条，带动画效果"""
        self._progress_anim.setStartValue(self.progress_bar.value())
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()

    def _update_batch_progress(self, current_batch: int, total_batches: int, current_text: str):
        """更新批次进度信息"""
        # 更新日志显示当前翻译的句子
        if current_text:
            # 截断过长的文本
            display_text = current_text[:60] + "..." if len(current_text) > 60 else current_text
            self._append_log(f"[翻译进度] 批次 {current_batch}/{total_batches} - {display_text}")

    # ── 停止处理 ────────────────────────────────────────────
    def _stop_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(2000)
            self._append_log("\n[用户中止] 处理已停止")
            self._reset_ui("已停止")
            QMessageBox.information(self, "提示", "处理已停止")

    # ── 更新步骤状态 ────────────────────────────────────────
    def _update_step(self, step_num: int, status: str):
        idx = step_num - 1
        if 0 <= idx < len(self.step_cards):
            self.step_cards[idx].set_status(status)
        if status == "error":
            self._on_error(f"步骤 {step_num} 执行失败")

    # ── 完成回调 ────────────────────────────────────────────
    def _on_finished(self, result: dict):
        self._append_log("\n" + "=" * 60)
        self._append_log("处理完成！")
        self._append_log("=" * 60)
        for key, value in result.items():
            if isinstance(value, str) and os.path.exists(value):
                self._append_log(f"  [{key}] {value}")

        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("完成")
        self.status_indicator.setText("完成")
        self.status_indicator.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #27ae60; padding: 6px 16px; background-color: transparent;"
        )
        self._reset_ui("完成")
        QMessageBox.information(self, "完成", "处理完成！")

    # ── 错误回调 ────────────────────────────────────────────
    def _on_error(self, error_msg: str):
        self.status_indicator.setText("失败")
        self.status_indicator.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #e74c3c; padding: 6px 16px; background-color: transparent;"
        )
        self._reset_ui("失败")
        # 标记出错步骤
        for card in self.step_cards:
            if card.status == "running":
                card.set_status("error")
                break

        if error_msg:
            QMessageBox.critical(self, "错误", f"处理失败:\n{error_msg}")

    # ── 重置 UI ─────────────────────────────────────────────
    def _reset_ui(self, status_text: str):
        self.processing = False
        self._set_controls_enabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setFormat(status_text)

    # ── 控件启用/禁用 ───────────────────────────────────────
    def _set_controls_enabled(self, enabled: bool):
        self.select_btn.setEnabled(enabled)
        self.source_lang.setEnabled(enabled)
        self.target_lang.setEnabled(enabled)
        self.engine_combo.setEnabled(enabled)
        self.api_key_input.setEnabled(enabled)
        self.validate_key_btn.setEnabled(enabled)
        self.style_combo.setEnabled(enabled)
        self.whisper_combo.setEnabled(enabled)
        self.device_combo.setEnabled(enabled)
        self.zh_font_size.setEnabled(enabled)
        self.ja_font_size.setEnabled(enabled)
        self.font_combo.setEnabled(enabled)
        self.output_dir_input.setEnabled(enabled)

    # ── 打开输出目录 ────────────────────────────────────────
    def _open_output(self):
        out_dir = self.output_dir_input.text().strip()
        if out_dir and os.path.exists(out_dir):
            os.startfile(out_dir)
        else:
            QMessageBox.warning(self, "提示", "输出目录不存在")


# ── 入口 ────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 强制深色调色板
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e2e"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#2d2d3f"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#363652"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#667eea"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = SubtitleForgeMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()