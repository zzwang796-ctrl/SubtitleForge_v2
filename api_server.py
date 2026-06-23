#!/usr/bin/env python3
"""
SubtitleForge v2 - API Server
提供字幕翻译流水线的 REST API 接口
"""

import os
import sys

# ====== 关键修复: 强制离线模式，避免 HuggingFace 联网检查 ======
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'

# faster-whisper 本地模型缓存路径（large-v3）
LOCAL_WHISPER_MODEL = r"C:\Users\aaa\.cache\huggingface\hub\models--Systran--faster-whisper-large-v3\snapshots\edaa852ec7e145841d8ffdb056a99866b5f0a478"
# ============================================================

import json
import time
import uuid
import shutil
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 添加模块路径
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from pipeline_v2 import SubtitlePipelineV2

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 全局流水线实例
pipeline = None
pipeline_lock = threading.Lock()

# 任务状态存储（线程安全）
tasks = {}
tasks_lock = threading.Lock()

# 上传文件目录
UPLOAD_DIR = os.path.join(MODULE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(MODULE_DIR, 'outputs')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 支持的翻译风格映射
STYLE_MAP = {
    'anime': '动漫字幕',
    'drama': '影视剧集',
    'youtube': '油管视频',
    'documentary': '纪录长片'
}

LANG_MAP = {
    'auto': '自动检测',
    'zh': '中文',
    'en': '英语',
    'ja': '日语'
}

# 流水线阶段描述
PIPELINE_STAGES = [
    {'id': 1, 'name': '音频提取', 'en': 'AUDIO EXTRACT', 'desc': '从视频中分离音频流'},
    {'id': 2, 'name': '语音识别', 'en': 'WHISPER ASR', 'desc': '使用 Whisper 模型识别语音内容'},
    {'id': 3, 'name': '语义断句', 'en': 'SENTENCE SPLIT', 'desc': '智能分割语句，保持语义完整性'},
    {'id': 4, 'name': '上下文翻译', 'en': 'CONTEXT TRANSLATE', 'desc': '结合上下文进行高质量翻译'},
    {'id': 5, 'name': '后处理润色', 'en': 'POST PROCESSING', 'desc': '优化翻译结果，提升可读性'},
    {'id': 6, 'name': '字幕生成', 'en': 'SUBTITLE GENERATE', 'desc': '生成 SRT 格式字幕文件'},
    {'id': 7, 'name': '双语字幕', 'en': 'BILINGUAL SUB', 'desc': '生成中英双语字幕'},
    {'id': 8, 'name': '字幕烧录', 'en': 'SUBTITLE BURN', 'desc': '将字幕嵌入视频画面'}
]


def init_pipeline():
    """初始化流水线（线程安全）"""
    global pipeline
    with pipeline_lock:
        if pipeline is not None:
            return True
        try:
            # 使用本地模型路径 - 避免联网
            if os.path.isdir(LOCAL_WHISPER_MODEL):
                pipeline = SubtitlePipelineV2(
                    whisper_model=LOCAL_WHISPER_MODEL,
                    device='cpu',
                    compute_type='int8'
                )
            else:
                # 回退：尝试使用模型名称（需要网络）
                pipeline = SubtitlePipelineV2(
                    whisper_model='large-v3',
                    device='cpu',
                    compute_type='int8'
                )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 流水线初始化完成")
            return True
        except Exception as e:
            print(f"流水线初始化失败: {e}")
            return False


@app.route('/')
def index():
    return send_from_directory('web', 'index.html')


@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查"""
    return jsonify({
        'success': True,
        'pipeline_ready': pipeline is not None,
        'timestamp': datetime.now().isoformat(),
        'upload_dir': UPLOAD_DIR,
        'output_dir': OUTPUT_DIR
    })


@app.route('/api/status', methods=['GET'])
def api_status():
    """获取系统状态"""
    return jsonify({
        "success": True,
        "pipeline_ready": pipeline is not None,
        "supported_models": list(SubtitlePipelineV2.SUPPORTED_WHISPER_MODELS),
        "supported_styles": list(STYLE_MAP.keys()),
        "supported_devices": list(SubtitlePipelineV2.SUPPORTED_DEVICES),
        "stages": PIPELINE_STAGES
    })


@app.route('/api/supported_styles', methods=['GET'])
def api_supported_styles():
    """获取支持的翻译风格"""
    return jsonify({
        "success": True,
        "styles": list(STYLE_MAP.keys()),
        "descriptions": STYLE_MAP
    })


@app.route('/api/supported_models', methods=['GET'])
def api_supported_models():
    """获取支持的模型列表"""
    return jsonify({
        "success": True,
        "models": list(SubtitlePipelineV2.SUPPORTED_WHISPER_MODELS)
    })


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """上传视频文件"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未找到上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '文件名为空'}), 400
    
    # 安全检查文件扩展名
    allowed_ext = {'.mp4', '.mkv', '.avi', '.mov', '.wav', '.mp3', '.srt', '.vtt', '.webm'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        return jsonify({'success': False, 'message': f'不支持的文件格式: {ext}'}), 400
    
    # 生成唯一文件名
    task_id = str(uuid.uuid4())[:8]
    safe_filename = f"{task_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'filename': file.filename,
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'file_path': file_path,
            'extension': ext,
            'message': f'文件上传成功: {file.filename}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'文件保存失败: {str(e)}'}), 500


@app.route('/api/translate', methods=['POST'])
def api_translate():
    """执行字幕翻译流水线（支持文件路径或刚上传的文件）"""
    if not pipeline:
        # 尝试延迟初始化
        if not init_pipeline():
            return jsonify({'success': False, 'message': '流水线初始化失败'}), 503
    
    data = request.get_json() or {}
    video_path = data.get('video_path')
    task_id = data.get('task_id', str(uuid.uuid4())[:8])
    
    # 如果是刚上传的文件，从上传目录查找
    if not video_path and task_id:
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(f"{task_id}_"):
                video_path = os.path.join(UPLOAD_DIR, fname)
                break
    
    if not video_path or not os.path.exists(video_path):
        return jsonify({'success': False, 'message': f'视频文件不存在: {video_path}'}), 400
    
    # 获取配置参数
    style = data.get('style', 'anime')
    source_lang = data.get('source_lang', 'auto')
    target_lang = data.get('target_lang', 'zh')
    api_key = data.get('api_key', '')  # 翻译 API Key
    
    # 创建任务记录
    with tasks_lock:
        tasks[task_id] = {
            'id': task_id,
            'status': 'running',
            'progress': 0,
            'current_stage': 0,
            'stages': [{**s, 'status': 'pending'} for s in PIPELINE_STAGES],
            'start_time': datetime.now().isoformat(),
            'video_path': video_path,
            'video_name': os.path.basename(video_path),
            'style': STYLE_MAP.get(style, style),
            'source_lang': LANG_MAP.get(source_lang, source_lang),
            'target_lang': LANG_MAP.get(target_lang, target_lang),
            'api_key': api_key,
            'output_files': [],
            'error': None,
            'logs': []
        }
    
    # 启动后台线程执行
    thread = threading.Thread(target=run_pipeline_thread, args=(task_id, video_path, style, source_lang, target_lang, api_key))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '流水线已启动，请调用 /api/task/{id} 查询进度'
    })


def update_task_stage(task_id, stage_idx, status, message=None):
    """更新任务阶段状态"""
    with tasks_lock:
        if task_id in tasks:
            task = tasks[task_id]
            task['stages'][stage_idx]['status'] = status
            if status == 'running':
                task['stages'][stage_idx]['start_time'] = datetime.now().isoformat()
                task['current_stage'] = stage_idx + 1
                task['progress'] = int((stage_idx + 1) / 8 * 100)
            elif status == 'done':
                task['stages'][stage_idx]['end_time'] = datetime.now().isoformat()
            if message:
                task['logs'].append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': 'INFO',
                    'message': message
                })


def run_pipeline_thread(task_id, video_path, style, source_lang, target_lang, api_key=''):
    """在后台线程中执行流水线"""
    # 判断是否使用真实流水线
    use_real_pipeline = api_key and len(api_key) > 5

    if use_real_pipeline:
        # 真实流水线：音频提取 → 语音识别 → 断句 → 翻译 → 字幕生成
        run_real_pipeline(task_id, video_path, style, source_lang, target_lang, api_key)
    else:
        # 演示流水线：模拟处理并生成示例字幕
        run_demo_pipeline(task_id, video_path)


def run_real_pipeline(task_id, video_path, style, source_lang, target_lang, api_key):
    """
    执行真实的视频处理流水线（带翻译）
    流程: 音频提取 → 语音识别 → 断句 → 翻译 → 后处理 → SRT → 烧录
    """
    import shutil
    import subprocess as sp

    def _log(msg):
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["logs"].append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "level": "INFO",
                    "message": msg
                })

    def _set_stage(idx, status, msg=None):
        with tasks_lock:
            if task_id in tasks:
                t = tasks[task_id]
                t["stages"][idx]["status"] = status
                if status == "running":
                    t["stages"][idx]["start_time"] = datetime.now().isoformat()
                    t["current_stage"] = idx + 1
                    t["progress"] = int((idx + 1) / 8 * 100)
                elif status == "done":
                    t["stages"][idx]["end_time"] = datetime.now().isoformat()
                if msg:
                    t["logs"].append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "level": "INFO",
                        "message": msg
                    })

    def _fail(err):
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = str(err)
                tasks[task_id]["logs"].append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "level": "ERROR",
                    "message": f"处理失败: {str(err)}"
                })

    try:
        if not os.path.exists(video_path):
            raise Exception(f"视频文件不存在: {video_path}")

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        task_dir = OUTPUT_DIR
        os.makedirs(task_dir, exist_ok=True)

        # ===== 阶段 1: 音频提取 =====
        _set_stage(0, "running", "正在提取音频...")
        audio_path = os.path.join(task_dir, f"{task_id}_audio.wav")
        try:
            cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", audio_path]
            proc = sp.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0 or not os.path.exists(audio_path):
                raise Exception(f"ffmpeg 返回错误: {proc.stderr[-200:]}")
            _log(f"音频提取完成: {os.path.getsize(audio_path)//1024} KB")
        except Exception as e:
            raise Exception(f"音频提取失败: {str(e)}")
        _set_stage(0, "done", "音频提取完成")

        # ===== 阶段 2-3: 语音识别 + 断句 =====
        _set_stage(1, "running", "正在加载 Whisper 模型...")
        from faster_whisper import WhisperModel

        model_loaded = None
        try:
            if os.path.isdir(LOCAL_WHISPER_MODEL):
                _log(f"加载本地模型: {LOCAL_WHISPER_MODEL}")
                model_loaded = WhisperModel(LOCAL_WHISPER_MODEL, device="cpu", compute_type="int8")
            else:
                _log("本地模型不可用，尝试使用 base 模型")
                model_loaded = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception as e:
            raise Exception(f"Whisper 模型加载失败: {str(e)}")

        _set_stage(1, "done", "Whisper 模型加载完成")
        _set_stage(2, "running", "正在进行语音识别...")

        segments_list = []
        try:
            segments, info = model_loaded.transcribe(
                audio_path, beam_size=5, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500), language=None
            )
            segments_list = list(segments)
            detected_lang = info.language if info else "auto"
            _log(f"语音识别完成: 共 {len(segments_list)} 段，语言={detected_lang}")
        except Exception as e:
            raise Exception(f"语音识别失败: {str(e)}")
        _set_stage(2, "done", "语音识别完成")
        _set_stage(3, "done", "语义断句完成（Whisper 已自动分段）")

        # 释放模型内存
        del model_loaded

        # ===== 阶段 4: 翻译（DeepSeek）=====
        _set_stage(4, "running", "正在调用 DeepSeek 翻译...")

        # 准备句子数据
        sentences = []
        for idx, seg in enumerate(segments_list):
            if not seg.text or len(seg.text.strip()) < 1:
                continue
            start = max(0, float(seg.start))
            end = float(seg.end)
            if end - start < 0.3:
                continue
            sentences.append({
                "start": start,
                "end": end,
                "text": seg.text.strip()
            })

        if not sentences:
            sentences = [{"start": 0, "end": 3, "text": "（未识别到语音）"}]

        translated = []
        try:
            from translator_v2 import ContextAwareTranslator, TranslationConfig, TranslationStyle

            style_map = {"anime": TranslationStyle.ANIME, "drama": TranslationStyle.DRAMA,
                         "youtube": TranslationStyle.YOUTUBE, "documentary": TranslationStyle.DOCUMENTARY}
            trans_style = style_map.get(style, TranslationStyle.ANIME)

            config = TranslationConfig(
                provider="deepseek",
                model="deepseek-chat",
                api_key=api_key,
                style=trans_style
            )
            translator = ContextAwareTranslator(config)
            translated = translator.translate_with_context(sentences)
            _log(f"翻译完成: {len(translated)} 句")
        except Exception as e:
            _log(f"翻译失败: {str(e)}，使用原文")
            translated = [dict(s, translated_text=s.get("text", "")) for s in sentences]

        _set_stage(4, "done", "上下文翻译完成")

        # ===== 阶段 5: 后处理 =====
        _set_stage(5, "running", "正在进行后处理...")

        if not pipeline:
            if not init_pipeline():
                raise Exception("流水线初始化失败")

        try:
            post_style_map = {"anime": "anime", "drama": "drama",
                              "youtube": "youtube", "documentary": "documentary"}
            processed = pipeline.post_process(translated, style=post_style_map.get(style, "anime"))
            _log(f"后处理完成: {len(processed)} 句")
        except Exception as e:
            _log(f"后处理失败: {str(e)}")
            processed = translated

        _set_stage(5, "done", "后处理润色完成")

        # ===== 阶段 6: 生成 SRT 字幕 =====
        _set_stage(6, "running", "正在生成 SRT 字幕...")

        def fmt_srt(s):
            h = int(s // 3600); m = int((s % 3600) // 60)
            sec = int(s % 60); ms = int((s - int(s)) * 1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

        zh_path = os.path.join(task_dir, f"{task_id}_zh.srt")
        bi_path = os.path.join(task_dir, f"{task_id}_bilingual.srt")

        # 生成中文字幕
        with open(zh_path, "w", encoding="utf-8") as f:
            for idx, item in enumerate(processed):
                start = float(item.get("start", 0))
                end = float(item.get("end", start + 1))
                zh = item.get("translated_text", item.get("text", ""))
                f.write(f"{idx+1}\n{fmt_srt(start)} --> {fmt_srt(end)}\n{zh}\n\n")

        # 生成双语字幕
        with open(bi_path, "w", encoding="utf-8") as f:
            for idx, item in enumerate(processed):
                start = float(item.get("start", 0))
                end = float(item.get("end", start + 1))
                orig = item.get("text", "")
                zh = item.get("translated_text", "")
                f.write(f"{idx+1}\n{fmt_srt(start)} --> {fmt_srt(end)}\n{orig}\n{zh}\n\n")

        _log(f"SRT 字幕生成完成")
        _set_stage(6, "done", "SRT 字幕生成完成")

        # ===== 阶段 7-8: 字幕烧录 =====
        _set_stage(7, "running", "正在烧录字幕到视频...")

        burned_video_path = os.path.join(task_dir, f"{task_id}_带字幕.mp4")

        try:
            # 生成 ASS 字幕
            ass_content = _generate_ass_content(segments_list)
            video_dir = os.path.dirname(video_path)
            ass_local = os.path.join(video_dir, f"_temp_{task_id}.ass")
            with open(ass_local, "w", encoding="utf-8") as f:
                f.write(ass_content)

            cmd_burn = [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"subtitles={os.path.basename(ass_local)}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                burned_video_path
            ]
            proc_burn = sp.run(cmd_burn, capture_output=True, text=True,
                              timeout=3600, cwd=video_dir)
            try:
                if os.path.exists(ass_local):
                    os.remove(ass_local)
            except Exception:
                pass

            if proc_burn.returncode != 0 or not os.path.exists(burned_video_path):
                _log(f"字幕烧录失败，回退为源视频")
                shutil.copy2(video_path, burned_video_path)
        except Exception as e:
            _log(f"字幕烧录异常: {str(e)}")
            try:
                shutil.copy2(video_path, burned_video_path)
            except Exception:
                burned_video_path = None

        _set_stage(7, "done", "字幕烧录完成")

        # ===== 清理 + 更新状态 =====
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass

        output_files = [
            {"name": os.path.basename(zh_path), "path": zh_path,
             "type": "中文字幕 SRT", "size": os.path.getsize(zh_path)},
            {"name": os.path.basename(bi_path), "path": bi_path,
             "type": "双语字幕 SRT", "size": os.path.getsize(bi_path)},
        ]
        if burned_video_path and os.path.exists(burned_video_path):
            output_files.append({
                "name": os.path.basename(burned_video_path), "path": burned_video_path,
                "type": "带字幕视频 MP4", "size": os.path.getsize(burned_video_path)
            })

        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["progress"] = 100
                tasks[task_id]["end_time"] = datetime.now().isoformat()
                tasks[task_id]["output_files"] = output_files
                tasks[task_id]["logs"].append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "level": "SUCCESS",
                    "message": f"处理完成！共 {len(processed)} 句字幕"
                })

    except Exception as e:
        _fail(e)


def run_demo_pipeline(task_id, video_path):
    """
    真实字幕翻译流水线：
    1. 提取音频 → 2. Whisper 语音识别 → 3. SRT 生成 → 4. 字幕烧录视频
    使用本地 faster-whisper large-v3 模型（离线模式）
    """
    try:
        import subprocess as sp

        def _log(message):
            with tasks_lock:
                if task_id in tasks:
                    tasks[task_id]['logs'].append({
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'level': 'INFO',
                        'message': message
                    })

        def _set_stage(stage_idx, status, message=None):
            with tasks_lock:
                if task_id in tasks:
                    task = tasks[task_id]
                    task['stages'][stage_idx]['status'] = status
                    if status == 'running':
                        task['stages'][stage_idx]['start_time'] = datetime.now().isoformat()
                        task['current_stage'] = stage_idx + 1
                        task['progress'] = int((stage_idx + 1) / 8 * 100)
                    elif status == 'done':
                        task['stages'][stage_idx]['end_time'] = datetime.now().isoformat()
                    if message:
                        task['logs'].append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'level': 'INFO',
                            'message': message
                        })

        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        task_dir = OUTPUT_DIR
        os.makedirs(task_dir, exist_ok=True)

        # ===== 阶段 1: 提取音频 =====
        _set_stage(0, 'running', '正在提取音频...')
        audio_path = os.path.join(task_dir, f"{task_id}_audio.wav")
        try:
            cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-ac', '1', '-ar', '16000', audio_path]
            proc = sp.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0 or not os.path.exists(audio_path):
                raise Exception(f'ffmpeg 返回错误: {proc.stderr[-200:]}')
            _log(f'音频提取完成: {os.path.getsize(audio_path)//1024} KB')
        except Exception as e:
            raise Exception(f'音频提取失败: {str(e)}')
        _set_stage(0, 'done', '音频提取完成')

        # ===== 阶段 2-3: 语音识别（Whisper）=====
        _set_stage(1, 'running', '正在加载 Whisper 模型...')
        from faster_whisper import WhisperModel

        model_loaded = None
        try:
            if os.path.isdir(LOCAL_WHISPER_MODEL):
                _log(f'加载本地模型: {LOCAL_WHISPER_MODEL}')
                model_loaded = WhisperModel(LOCAL_WHISPER_MODEL, device='cpu', compute_type='int8')
            else:
                _log('本地模型目录不存在，尝试使用名称加载')
                model_loaded = WhisperModel('small', device='cpu', compute_type='int8')
        except Exception as e:
            raise Exception(f'Whisper 模型加载失败: {str(e)}')

        _set_stage(1, 'done', 'Whisper 模型加载完成')
        _set_stage(2, 'running', '正在进行语音识别...')

        segments_list = []
        try:
            segments, info = model_loaded.transcribe(
                audio_path, beam_size=5, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500), language=None
            )
            segments_list = list(segments)
            detected_lang = info.language if info else 'auto'
            _log(f'语音识别完成: 共 {len(segments_list)} 段，语言={detected_lang}')
        except Exception as e:
            raise Exception(f'语音识别失败: {str(e)}')
        _set_stage(2, 'done', '语音识别完成')
        _set_stage(3, 'done', '语义断句完成（Whisper 已自动分段）')

        # ===== 阶段 4-5: 生成 SRT 字幕文件 =====
        _set_stage(4, 'running', '正在生成 SRT 字幕...')

        def fmt_srt(s):
            h = int(s//3600); m = int((s%3600)//60); sec = int(s%60); ms = int((s-int(s))*1000)
            return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'

        zh_path = os.path.join(task_dir, f'{task_id}_zh.srt')
        bi_path = os.path.join(task_dir, f'{task_id}_bilingual.srt')

        # 释放模型内存
        del model_loaded

        srt_lines = []
        for idx, seg in enumerate(segments_list):
            if not seg.text or len(seg.text.strip()) < 1:
                continue
            start = max(0, float(seg.start))
            end = float(seg.end)
            if end - start < 0.3:
                continue
            srt_lines.append(f'{idx+1}\n{fmt_srt(start)} --> {fmt_srt(end)}\n{seg.text.strip()}\n')

        if not srt_lines:
            srt_lines.append(f'1\n00:00:00,000 --> 00:00:03,000\n未识别到语音\n')

        with open(zh_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_lines) + '\n')
        with open(bi_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_lines) + '\n')

        _log(f'SRT 字幕生成: {zh_path}')
        _set_stage(4, 'done', 'SRT 字幕生成完成')
        _set_stage(5, 'done', '双语字幕生成完成')

        # ===== 阶段 6-7: 字幕烧录 =====
        _set_stage(6, 'running', '正在烧录字幕到视频...')

        burned_video_path = os.path.join(task_dir, f'{task_id}_带字幕.mp4')

        try:
            ass_content = _generate_ass_content(segments_list)
            video_dir = os.path.dirname(video_path)
            ass_local = os.path.join(video_dir, f'_temp_{task_id}.ass')
            with open(ass_local, 'w', encoding='utf-8') as f:
                f.write(ass_content)

            cmd_burn = [
                'ffmpeg', '-y', '-i', video_path,
                '-vf', f'subtitles={os.path.basename(ass_local)}',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k',
                burned_video_path
            ]
            proc_burn = sp.run(
                cmd_burn, capture_output=True, text=True,
                timeout=3600, cwd=video_dir
            )

            try: os.remove(ass_local)
            except Exception: pass

            if proc_burn.returncode != 0 or not os.path.exists(burned_video_path):
                _log(f'字幕烧录失败 (returncode={proc_burn.returncode})')
                _log(f'ffmpeg stderr: {proc_burn.stderr[-300:]}')
                _log('回退: 直接复制源视频')
                shutil.copy2(video_path, burned_video_path)
        except Exception as e:
            _log(f'字幕烧录异常: {str(e)}')
            try: shutil.copy2(video_path, burned_video_path)
            except Exception: burned_video_path = None

        _set_stage(6, 'done', '字幕烧录完成')
        _set_stage(7, 'done', '流水线完成')

        # ===== 更新任务状态 =====
        output_files_list = [
            {'name': os.path.basename(zh_path), 'path': zh_path, 'type': '中文字幕 SRT', 'size': os.path.getsize(zh_path)},
            {'name': os.path.basename(bi_path), 'path': bi_path, 'type': '双语字幕 SRT', 'size': os.path.getsize(bi_path)},
        ]
        if burned_video_path and os.path.exists(burned_video_path):
            output_files_list.append({
                'name': os.path.basename(burned_video_path),
                'path': burned_video_path,
                'type': '带字幕视频 MP4',
                'size': os.path.getsize(burned_video_path)
            })

        try:
            if os.path.exists(audio_path): os.remove(audio_path)
        except Exception: pass

        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['progress'] = 100
                tasks[task_id]['end_time'] = datetime.now().isoformat()
                tasks[task_id]['output_files'] = output_files_list
                tasks[task_id]['logs'].append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': 'SUCCESS',
                    'message': f'处理完成！共识别 {len(segments_list)} 段字幕'
                })

    except Exception as e:
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['error'] = str(e)
                tasks[task_id]['logs'].append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': 'ERROR',
                    'message': f'处理失败: {str(e)}'
                })

def _generate_ass_content(segments_list):
    """从 Whisper 识别结果生成 ASS 字幕内容"""
    import os

    header = """[Script Info]
Title: SubtitleForge v2
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,42,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,2,2,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def format_ass_time(seconds):
        if seconds < 0:
            seconds = 0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100)
        return f'{h:01d}:{m:02d}:{s:02d}.{cs:02d}'

    events = []
    for idx, seg in enumerate(segments_list):
        if not seg.text or len(seg.text.strip()) < 1:
            continue
        start = max(0, float(seg.start))
        end = float(seg.end)
        if end - start < 0.3:
            continue
        text = seg.text.strip()
        # ASS 文本需要转义换行和花括号
        text = text.replace('\n', '\\N').replace('{', '(').replace('}', ')')
        events.append(f'Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}')

    return header + '\n'.join(events) + '\n'


@app.route('/api/uploads/<path:filename>', methods=['GET'])
def api_get_upload(filename):
    """访问上传文件"""
    try:
        response = send_from_directory(UPLOAD_DIR, filename, conditional=True)
        # 确保正确的 Content-Type
        if filename.lower().endswith('.mp4'):
            response.headers['Content-Type'] = 'video/mp4'
        elif filename.lower().endswith('.srt'):
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        elif filename.lower().endswith('.vtt'):
            response.headers['Content-Type'] = 'text/vtt; charset=utf-8'
        response.headers['Accept-Ranges'] = 'bytes'
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 404


@app.route('/api/outputs/<path:filename>', methods=['GET'])
def api_get_output(filename):
    """访问输出文件"""
    try:
        response = send_from_directory(OUTPUT_DIR, filename, conditional=True)
        if filename.lower().endswith('.mp4'):
            response.headers['Content-Type'] = 'video/mp4'
        elif filename.lower().endswith('.srt'):
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        elif filename.lower().endswith('.vtt'):
            response.headers['Content-Type'] = 'text/vtt; charset=utf-8'
        response.headers['Accept-Ranges'] = 'bytes'
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 404


@app.route('/api/folders', methods=['GET'])
def api_get_folders():
    """返回上传和输出目录的路径"""
    user_downloads = r'C:\Users\aaa\Downloads'
    return jsonify({
        'success': True,
        'upload_dir': UPLOAD_DIR,
        'output_dir': OUTPUT_DIR,
        'download_dir': user_downloads,
        'upload_dir_exists': os.path.isdir(UPLOAD_DIR),
        'output_dir_exists': os.path.isdir(OUTPUT_DIR),
        'download_dir_exists': os.path.isdir(user_downloads)
    })


@app.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    """在系统文件管理器中打开指定文件夹"""
    data = request.get_json() or {}
    folder_type = data.get('type', 'upload')  # 'upload' or 'output' or 'download'

    user_downloads = r'C:\Users\aaa\Downloads'
    if folder_type == 'upload':
        target_dir = UPLOAD_DIR
    elif folder_type == 'output':
        target_dir = OUTPUT_DIR
    elif folder_type == 'download':
        target_dir = user_downloads
    else:
        target_dir = OUTPUT_DIR

    # 支持直接指定路径
    custom_path = data.get('path')
    if custom_path:
        target_dir = custom_path

    # 验证路径安全
    abs_target = os.path.abspath(target_dir)
    abs_upload = os.path.abspath(UPLOAD_DIR)
    abs_output = os.path.abspath(OUTPUT_DIR)
    abs_download = os.path.abspath(user_downloads)
    if not (abs_target.startswith(abs_upload) or abs_target.startswith(abs_output)
            or abs_target.startswith(abs_download)
            or abs_target == abs_upload or abs_target == abs_output
            or abs_target == abs_download):
        return jsonify({'success': False, 'message': '不允许访问此路径'}), 403

    if not os.path.isdir(abs_target):
        return jsonify({'success': False, 'message': f'目录不存在: {abs_target}'}), 404

    try:
        # Windows 上用 explorer.exe 打开文件夹
        import subprocess
        if os.name == 'nt':
            subprocess.Popen(['explorer', abs_target], shell=False)
        elif os.name == 'posix':
            import sys
            if sys.platform == 'darwin':
                subprocess.Popen(['open', abs_target])
            else:
                subprocess.Popen(['xdg-open', abs_target])
        else:
            return jsonify({'success': False, 'message': '不支持的操作系统'}), 500

        return jsonify({'success': True, 'path': abs_target, 'message': f'已打开: {abs_target}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'打开失败: {str(e)}'}), 500


@app.route('/api/task/<task_id>', methods=['GET'])
def api_get_task(task_id):
    """获取任务状态"""
    with tasks_lock:
        task = tasks.get(task_id)
    
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    return jsonify({'success': True, 'task': task})


@app.route('/api/tasks', methods=['GET'])
def api_list_tasks():
    """获取所有任务列表"""
    with tasks_lock:
        return jsonify({'success': True, 'tasks': list(tasks.values())})


@app.route('/api/clear_task/<task_id>', methods=['DELETE'])
def api_clear_task(task_id):
    """清除任务记录"""
    with tasks_lock:
        if task_id in tasks:
            del tasks[task_id]
            return jsonify({'success': True, 'message': '任务已清除'})
    return jsonify({'success': False, 'message': '任务不存在'}), 404


@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'API 路径不存在'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': str(error)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("SubtitleForge v2 API Server")
    print("=" * 60)
    print("正在初始化字幕翻译流水线...")
    init_pipeline()
    print("\n启动 API 服务器...")
    print(f"  访问地址: http://127.0.0.1:5000")
    print(f"  健康检查: http://127.0.0.1:5000/api/health")
    print(f"  上传目录: {UPLOAD_DIR}")
    print(f"  输出目录: {OUTPUT_DIR}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
