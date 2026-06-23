/* =========================================================
   SubtitleForge · v2 — 字幕翻译工作室
   Interaction Logic
   ========================================================= */

(function () {
  'use strict';

  const pad2 = function(n) { return String(n).padStart(2, '0'); };
  const $ = function(sel, root) { return (root || document).querySelector(sel); };
  const $$ = function(sel, root) { return Array.from((root || document).querySelectorAll(sel)); };

  // 全局状态
  const API_BASE = '/api';
  let currentTaskId = null;
  let uploadedFile = null;
  let pollInterval = null;
  let running = false;
  let currentSubtitles = [];  // 当前字幕条目 [{start, end, zh, en}]
  let localVideoUrl = null;   // 本地视频预览 URL
  let serverVideoUrl = null;  // 服务器视频 URL
  let serverVideoName = null; // 服务器视频文件名

  // 日志
  function addLog(kind, msg) {
    const ts = pad2(new Date().getHours()) + ':' + pad2(new Date().getMinutes()) + ':' + pad2(new Date().getSeconds());
    console.log('[' + ts + '] [' + kind + '] ' + msg);

    // 更新状态栏
    const statusEl = $('#pipelineStatus');
    if (statusEl) {
      if (kind === 'SUCCESS') {
        statusEl.textContent = 'DONE';
        statusEl.className = 'qc-status status-ready';
      } else if (kind === 'RUN') {
        statusEl.textContent = 'RUN...';
        statusEl.className = 'qc-status status-loading';
      }
    }
  }

  // ========================================================
  // 1) 主题切换
  // ========================================================
  const THEME_KEY = 'sf-theme';

  function setTheme(theme) {
    if (theme !== 'light' && theme !== 'dark') theme = 'dark';
    document.body.classList.toggle('theme-light', theme === 'light');
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}

    const txt = $('#themeToggle .tt-state');
    if (txt) txt.textContent = theme === 'light' ? 'LIGHT → DARK' : 'DARK → LIGHT';
    const label = $('#themeToggle .tt-label');
    if (label) label.textContent = theme === 'light' ? '浅色主题' : '深色主题';
  }

  // 初始化主题
  setTheme(localStorage.getItem(THEME_KEY) || 'dark');

  if ($('#themeToggle')) {
    $('#themeToggle').addEventListener('click', function() {
      const next = (localStorage.getItem(THEME_KEY) || 'dark') === 'light' ? 'dark' : 'light';
      setTheme(next);
    });
  }

  // ========================================================
  // 2) 实时时钟
  // ========================================================
  setInterval(function() {
    const d = new Date();
    const t = pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
    $$('.clock').forEach(function(el) { el.textContent = t; });
  }, 1000);

  // ========================================================
  // 3) 页面导航
  // ========================================================
  $$('.nav-item').forEach(function(nav, idx) {
    nav.addEventListener('click', function() {
      $$('.nav-item').forEach(function(n) { n.classList.remove('active'); });
      nav.classList.add('active');

      $$('.page').forEach(function(p) { p.classList.remove('active'); });
      const pages = $$('.page');
      if (pages[idx]) pages[idx].classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  // ========================================================
  // 4) API 工具
  // ========================================================
  async function apiGet(endpoint) {
    try {
      const res = await fetch(API_BASE + endpoint);
      return await res.json();
    } catch (e) {
      addLog('ERR', 'API 错误: ' + e.message);
      return { success: false, message: e.message };
    }
  }

  async function apiPost(endpoint, data, isJson) {
    try {
      const opts = { method: 'POST' };
      if (isJson === undefined || isJson) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(data);
      } else {
        opts.body = data;
      }
      const res = await fetch(API_BASE + endpoint, opts);
      return await res.json();
    } catch (e) {
      addLog('ERR', 'API 错误: ' + e.message);
      return { success: false, message: e.message };
    }
  }

  // ========================================================
  // 5) SRT 字幕解析与视频同步
  // ========================================================

  // 把 SRT 时间戳 "HH:MM:SS,mmm" 转成秒
  function parseSrtTime(t) {
    try {
      const parts = t.trim().split(':');
      const h = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10);
      const rest = parts[2].replace(',', '.');
      const s = parseFloat(rest);
      return h * 3600 + m * 60 + s;
    } catch (e) {
      return 0;
    }
  }

  // 把秒数格式化成 SRT 时间戳字符串
  function formatSrtTime(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return pad2(h) + ':' + pad2(m) + ':' + pad2(s) + ',' + String(ms).padStart(3, '0');
  }

  // 解析整个 SRT 内容，支持双语（中文在上，英文在下）
  function parseSRT(content) {
    const subs = [];
    // 统一换行符
    const text = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
    // 按空行分块
    const blocks = text.split(/\n\s*\n/);

    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i].trim();
      if (!block) continue;

      const lines = block.split('\n');
      // 跳过纯数字序号行（有时候存在，有时候不存在）
      let idx = 0;
      if (/^\d+$/.test(lines[0].trim())) {
        idx = 1;
      }

      // 时间行
      if (idx >= lines.length) continue;
      const timeLine = lines[idx];
      const timeMatch = timeLine.match(/(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})/);
      if (!timeMatch) continue;

      const start = parseSrtTime(timeMatch[1]);
      const end = parseSrtTime(timeMatch[2]);

      // 剩余的都是文本内容
      const textLines = lines.slice(idx + 1).filter(function(l) { return l.trim().length > 0; });
      let zh = '';
      let en = '';

      // 简单双语检测：英文行包含较多英文字母
      for (let j = 0; j < textLines.length; j++) {
        const line = textLines[j].trim();
        // 检测是否主要为英文
        const englishChars = (line.match(/[a-zA-Z]/g) || []).length;
        const chineseChars = (line.match(/[\u4e00-\u9fa5]/g) || []).length;
        if (chineseChars > 0 || (englishChars === 0 && zh === '')) {
          zh = zh ? (zh + ' ' + line) : line;
        } else {
          en = en ? (en + ' ' + line) : line;
        }
      }

      // 如果只有一行文本，判断是中文还是英文
      if (zh && !en) {
        // 都是中文
      } else if (!zh && en) {
        zh = en;
        en = '';
      }

      subs.push({
        start: start,
        end: end,
        zh: zh,
        en: en,
        raw: textLines.join('\n')
      });
    }

    return subs;
  }

  // 渲染字幕时间轴列表
  function renderTimeline(subtitles) {
    const tlList = $('#tlList');
    const tlCount = $('#tlCount');
    if (!tlList) return;

    if (!subtitles || subtitles.length === 0) {
      tlList.innerHTML = '<div class="tl-empty">暂无字幕内容</div>';
      if (tlCount) tlCount.textContent = '0 LINES';
      return;
    }

    let html = '';
    for (let i = 0; i < subtitles.length; i++) {
      const sub = subtitles[i];
      const tcStr = formatSrtTime(sub.start) + ' \u2192 ' + formatSrtTime(sub.end);
      html = html + '<div class="tl-row" data-idx="' + i + '" data-start="' + sub.start.toFixed(3) + '">' +
        '<div class="tl-tc">' + tcStr + '</div>' +
        '<div class="tl-content">' +
          '<div class="tl-zh">' + (sub.zh || '') + '</div>' +
          (sub.en ? ('<div class="tl-en">' + sub.en + '</div>') : '') +
        '</div>' +
      '</div>';
    }

    tlList.innerHTML = html;
    if (tlCount) tlCount.textContent = subtitles.length + ' LINES';

    // 给每一行绑定点击事件 - 点击跳转到对应时间
    const rows = tlList.querySelectorAll('.tl-row');
    rows.forEach(function(row) {
      row.addEventListener('click', function() {
        const start = parseFloat(row.getAttribute('data-start'));
        const video = $('#videoPlayer');
        if (video && !isNaN(start)) {
          video.currentTime = start;
          video.play().catch(function() {});
        }
      });
    });
  }

  // 更新屏幕字幕显示
  function updateScreenSubtitle(currentTime) {
    const ssCn = $('#ssCn');
    const ssEn = $('#ssEn');
    const screenSubtitle = $('#screenSubtitle');
    if (!ssCn || !ssEn) return;

    // 查找当前时间对应的字幕
    let activeIdx = -1;
    for (let i = 0; i < currentSubtitles.length; i++) {
      const s = currentSubtitles[i];
      if (currentTime >= s.start && currentTime <= s.end) {
        activeIdx = i;
        break;
      }
      // 找到超过当前时间的条目，停止（因为字幕是按时间顺序的）
      if (s.start > currentTime) break;
    }

    if (activeIdx >= 0) {
      const sub = currentSubtitles[activeIdx];
      ssCn.textContent = sub.zh || '';
      ssEn.textContent = sub.en || '';
      if (screenSubtitle) screenSubtitle.style.opacity = '1';

      // 高亮时间轴中对应的行
      const tlList = $('#tlList');
      if (tlList) {
        const rows = tlList.querySelectorAll('.tl-row');
        rows.forEach(function(row, idx) {
          if (idx === activeIdx) {
            row.classList.add('active');
            // 滚动到可见区域
            if (!row.dataset.scrolled) {
              row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
          } else {
            row.classList.remove('active');
          }
        });
      }
    } else {
      ssCn.textContent = '';
      ssEn.textContent = '';
      if (screenSubtitle) screenSubtitle.style.opacity = '0.6';

      // 清除所有 active
      const tlList = $('#tlList');
      if (tlList) {
        tlList.querySelectorAll('.tl-row.active').forEach(function(row) {
          row.classList.remove('active');
        });
      }
    }
  }

  // 更新监视器上的时间码
  function updateMonTimecode(currentTime, duration) {
    const mt = $('#monTimecode');
    if (!mt) return;
    mt.textContent = formatSrtTime(currentTime).replace(',', ':').slice(0, 8) + ':' + String(Math.floor((currentTime % 1) * 100)).padStart(2, '0');

    const mz = $('#monZoom');
    if (mz && duration && isFinite(duration)) {
      const pct = Math.floor((currentTime / duration) * 100);
      mz.textContent = pct + '%';
    }
  }

  // 加载视频到播放器
  function loadVideo(url, name) {
    const video = $('#videoPlayer');
    if (!video) return;

    video.src = url;
    video.load();

    // 更新监视器信息
    const monInfo = $('#monInfo');
    if (monInfo) monInfo.textContent = name || '已加载视频';
    const ssCn = $('#ssCn');
    const ssEn = $('#ssEn');
    if (ssCn) ssCn.textContent = '视频已就绪';
    if (ssEn) ssEn.textContent = 'VIDEO READY';

    addLog('INFO', '视频已加载到预览');
  }

  // 加载字幕文件（从服务器或本地字符串）
  async function loadSubtitles(url) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        addLog('WARN', '字幕加载失败: ' + response.status);
        return;
      }
      const content = await response.text();
      currentSubtitles = parseSRT(content);
      renderTimeline(currentSubtitles);
      addLog('OK', '已加载 ' + currentSubtitles.length + ' 条字幕');
    } catch (e) {
      addLog('WARN', '字幕加载出错: ' + e.message);
    }
  }

  // ========================================================
  // 6) 文件上传处理
  // ========================================================
  const fileInput = $('#fileInput');
  const dropZone = $('#dropZone');
  const fileBtn = $('#fileBtn');

  function handleFiles(files) {
    if (!files || !files.length) return;
    uploadedFile = files[0];

    const sizeMB = (uploadedFile.size / (1024 * 1024)).toFixed(2);
    addLog('OK', '文件已选择: ' + uploadedFile.name + ' (' + sizeMB + ' MB)');

    const fi = $('#fileInfo');
    if (fi) {
      fi.innerHTML = '<div class="fi-icon">🎬</div>' +
        '<div class="fi-details">' +
          '<div class="fi-name">' + uploadedFile.name + '</div>' +
          '<div class="fi-meta">大小: ' + sizeMB + ' MB · 类型: ' + (uploadedFile.type || 'video') + '</div>' +
        '</div>' +
        '<div class="fi-status ready">● READY</div>';
    }

    // 立即用本地 URL 预览视频
    if (localVideoUrl) {
      try { URL.revokeObjectURL(localVideoUrl); } catch (e) {}
    }
    localVideoUrl = URL.createObjectURL(uploadedFile);
    loadVideo(localVideoUrl, uploadedFile.name);

    // 显示文件位置面板
    const fileLoc = $('#fileLocation');
    if (fileLoc && window.folderInfo) {
      fileLoc.style.display = 'block';
    }

    if (dropZone) dropZone.classList.add('file-selected');
    addLog('INFO', '文件已准备就绪，可启动翻译');
  }

  if (fileInput) {
    fileInput.addEventListener('change', function(e) { handleFiles(e.target.files); });
  }

  if (fileBtn && fileInput) {
    fileBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropZone) {
    dropZone.addEventListener('click', function(e) {
      if (e.target.closest('button')) return;
      if (fileInput) fileInput.click();
    });

    ['dragenter', 'dragover'].forEach(function(evt) {
      dropZone.addEventListener(evt, function(e) {
        e.preventDefault();
        dropZone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(function(evt) {
      dropZone.addEventListener(evt, function(e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
      });
    });

    dropZone.addEventListener('drop', function(e) {
      const files = e.dataTransfer ? e.dataTransfer.files : null;
      handleFiles(files);
    });
  }

  // ========================================================
  // 6) 启动流水线
  // ========================================================
  async function runPipeline() {
    if (running) {
      addLog('WARN', '流水线已在运行中...');
      return;
    }

    if (!uploadedFile) {
      addLog('WARN', '请先选择视频文件');
      alert('请先选择视频文件');
      return;
    }

    running = true;
    addLog('RUN', '正在上传文件...');
    resetPipelineUI();

    // 上传
    const formData = new FormData();
    formData.append('file', uploadedFile);

    const uploadResult = await apiPost('/upload', formData, false);

    if (!uploadResult.success) {
      addLog('ERR', uploadResult.message || '上传失败');
      running = false;
      return;
    }

    currentTaskId = uploadResult.task_id;
    addLog('OK', '文件上传成功 (ID: ' + currentTaskId + ')');

    // 配置
    const sourceLang = $('#sourceLang') ? $('#sourceLang').value : 'auto';
    const targetLang = $('#targetLang') ? $('#targetLang').value : 'zh';
    const style = $('#styleSelect') ? $('#styleSelect').value : 'anime';
    const apiKey = $('#apiKey') ? $('#apiKey').value.trim() : '';

    addLog('INFO', '源语言: ' + sourceLang + ' · 目标语言: ' + targetLang + ' · 风格: ' + style);
    if (apiKey) {
      addLog('INFO', 'API Key: ' + apiKey.substring(0, 8) + '***');
      addLog('RUN', '将使用 DeepSeek 翻译...');
    } else {
      addLog('WARN', '未填写 API Key，将直接输出原文（不翻译）');
    }
    addLog('RUN', '正在启动翻译流水线...');

    // 启动翻译
    const translateResult = await apiPost('/translate', {
      task_id: currentTaskId,
      source_lang: sourceLang,
      target_lang: targetLang,
      style: style,
      api_key: apiKey
    });

    if (!translateResult.success) {
      addLog('ERR', translateResult.message || '启动流水线失败');
      running = false;
      return;
    }

    addLog('OK', '流水线已启动，正在处理...');
    startProgressPoll();
  }

  function resetPipelineUI() {
    // 重置所有流水线帧
    $$('.fframe').forEach(function(frame) {
      frame.classList.remove('active', 'done');
      const progressFill = frame.querySelector('.fframe-progress-fill');
      if (progressFill) progressFill.style.width = '0%';
    });

    // 重置总进度
    const progressFill = $('#progressFill');
    const progressEl = $('#progressValue');
    const stageHint = $('#stageHint');
    if (progressFill) progressFill.style.width = '0%';
    if (progressEl) progressEl.textContent = '0%';
    if (stageHint) stageHint.textContent = '正在初始化...';

    // 禁用启动按钮
    const rb = $('#runBtn');
    if (rb) rb.disabled = true;

    // 更新状态
    const se = $('#pipelineStatus');
    if (se) {
      se.textContent = 'RUN...';
      se.className = 'qc-status status-loading';
    }

    // 显示进度面板 - 始终显示
    const progressPanel = $('#taskProgress');
    if (progressPanel) progressPanel.style.display = 'flex';
  }

  // ========================================================
  // 7) 进度轮询
  // ========================================================
  function startProgressPoll() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async function() {
      if (!currentTaskId) return;

      const result = await apiGet('/task/' + currentTaskId);
      if (!result.success) {
        addLog('ERR', result.message);
        clearInterval(pollInterval);
        running = false;
        return;
      }

      const task = result.task;
      addLog('INFO', '进度: ' + task.progress + '% · 当前阶段: ' + task.current_stage + '/8 · 状态: ' + task.status);

      updatePipelineUI(task);

      if (task.status === 'completed') {
        clearInterval(pollInterval);
        addLog('SUCCESS', '✅ 流水线处理完成！');
        showOutputFiles(task);
        const rb = $('#runBtn');
        if (rb) rb.disabled = false;
        running = false;
      } else if (task.status === 'failed') {
        clearInterval(pollInterval);
        addLog('ERR', '处理失败: ' + task.error);
        const rb = $('#runBtn');
        if (rb) rb.disabled = false;
        running = false;
      }
    }, 800);
  }

  function updatePipelineUI(task) {
    const frames = $$('.fframe');

    // 1. 更新每个阶段的状态
    if (task.stages && task.stages.length) {
      task.stages.forEach(function(stage, i) {
        if (i < frames.length) {
          const frame = frames[i];
          const progressFill = frame.querySelector('.fframe-progress-fill');

          frame.classList.remove('active', 'done');

          if (stage.status === 'done') {
            frame.classList.add('done');
            if (progressFill) progressFill.style.width = '100%';
          } else if (stage.status === 'running') {
            frame.classList.add('active');
            if (progressFill) {
              const subProgress = stage.progress || 50;
              progressFill.style.width = subProgress + '%';
            }
          } else {
            if (progressFill) progressFill.style.width = '0%';
          }
        }
      });
    }

    // 2. 更新总进度
    const progressEl = $('#progressValue');
    const progressFill = $('#progressFill');
    const progressPanel = $('#taskProgress');

    if (progressPanel) progressPanel.style.display = 'flex';
    if (progressEl) progressEl.textContent = task.progress + '%';
    if (progressFill) progressFill.style.width = task.progress + '%';

    // 3. 更新当前阶段提示
    const stageHint = $('#stageHint');
    if (stageHint) {
      let stageName = '正在初始化...';
      if (task.stages && task.current_stage > 0 && task.current_stage <= task.stages.length) {
        stageName = task.stages[task.current_stage - 1].name;
      } else if (task.stages && task.stages.length > 0) {
        for (let i = 0; i < task.stages.length; i++) {
          if (task.stages[i].status === 'running') {
            stageName = task.stages[i].name;
            break;
          }
          if (task.stages[i].status === 'pending') {
            stageName = task.stages[i].name;
            break;
          }
        }
      }
      stageHint.textContent = '正在处理: ' + stageName;
    }

    // 4. 更新文件状态
    const fileStatus = $('.fi-status');
    if (fileStatus) {
      if (task.status === 'running') {
        fileStatus.textContent = '● PROCESSING';
        fileStatus.className = 'fi-status running';
      } else if (task.status === 'completed') {
        fileStatus.textContent = '● DONE';
        fileStatus.className = 'fi-status ready';
      } else if (task.status === 'failed') {
        fileStatus.textContent = '● ERROR';
        fileStatus.className = 'fi-status';
      }
    }
  }

  // ========================================================
  // 8) 显示输出文件
  // ========================================================
  function showOutputFiles(task) {
    const outputArea = $('#outputArea');
    if (!outputArea) return;

    // ===== 加载服务器上的视频和字幕到预览 =====
    if (task.video_name) {
      serverVideoName = task.video_name;
      serverVideoUrl = API_BASE + '/uploads/' + encodeURIComponent(task.video_name);
      // 切到服务器上的视频（确保后续播放与字幕文件匹配）
      loadVideo(serverVideoUrl, task.video_name);
    }

    if (task.output_files && task.output_files.length > 0) {
      // 找到第一个 SRT 字幕文件加载到预览
      for (let i = 0; i < task.output_files.length; i++) {
        const f = task.output_files[i];
        if (f.name && f.name.toLowerCase().endsWith('.srt')) {
          const subUrl = API_BASE + '/outputs/' + encodeURIComponent(f.name);
          loadSubtitles(subUrl);
          break;
        }
      }
    }

    if (!task.output_files || !task.output_files.length) {
      outputArea.innerHTML = '<div class="ol-head">📁 输出文件</div><div class="ol-list"><div class="ol-empty">暂无输出文件</div></div>';
      return;
    }

    let html = '<div class="ol-head">📁 输出文件</div><div class="ol-list">';

    task.output_files.forEach(function(file) {
      const sizeKB = (file.size / 1024).toFixed(1);
      const fileUrl = API_BASE + '/outputs/' + encodeURIComponent(file.name);
      html = html + '<div class="ol-row">' +
        '<div class="ol-icon">📄</div>' +
        '<div class="ol-main">' +
          '<div class="ol-name">' + file.name + '</div>' +
          '<div class="ol-meta">' + (file.type || 'SRT') + ' · ' + sizeKB + ' KB</div>' +
        '</div>' +
        '<div class="ol-action"><a class="btn-download" href="' + fileUrl + '" download="' + file.name + '">下载</a></div>' +
      '</div>';
    });

    html = html + '</div>';
    outputArea.innerHTML = html;
  }

  // ========================================================
  // 9) 配置保存
  // ========================================================
  const saveBtn = $('#saveBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', function() {
      try {
        localStorage.setItem('sf-api-key', $('#apiKey') ? $('#apiKey').value : '');
        localStorage.setItem('sf-font-size', $('#fontSize') ? $('#fontSize').value : '52');
        addLog('OK', '配置已保存');
        const orig = saveBtn.textContent;
        saveBtn.textContent = '✓ 已保存';
        setTimeout(function() { saveBtn.textContent = orig; }, 1400);
      } catch (e) {
        addLog('ERR', '配置保存失败');
      }
    });
  }

  // 字号滑块
  const fontSize = $('#fontSize');
  const fsLabel = $('#fsLabel');
  if (fontSize && fsLabel) {
    const savedSize = localStorage.getItem('sf-font-size');
    if (savedSize) fontSize.value = savedSize;
    fsLabel.textContent = fontSize.value + 'px';
    fontSize.addEventListener('input', function() {
      fsLabel.textContent = fontSize.value + 'px';
    });
  }

  // ========================================================
  // 10) 启动按钮
  // ========================================================
  const runBtn = $('#runBtn');
  if (runBtn) {
    runBtn.addEventListener('click', runPipeline);
  }

  // ========================================================
  // 11) 初始化
  // ========================================================
  document.addEventListener('DOMContentLoaded', async function() {
    addLog('OK', 'SubtitleForge v2 · 已就绪');

    // 绑定视频播放器事件
    const video = $('#videoPlayer');
    if (video) {
      video.addEventListener('timeupdate', function() {
        updateScreenSubtitle(video.currentTime);
        updateMonTimecode(video.currentTime, video.duration);
      });
      video.addEventListener('loadedmetadata', function() {
        const monInfo = $('#monInfo');
        if (monInfo && video.videoWidth) {
          monInfo.textContent = video.videoWidth + '\u00D7' + video.videoHeight;
        }
        addLog('INFO', '视频元数据已加载，时长: ' + video.duration.toFixed(1) + ' 秒');
      });
      video.addEventListener('play', function() {
        addLog('INFO', '视频开始播放');
      });
    }

    // 绑定文件夹按钮点击事件
    $$('.btn-folder').forEach(function(btn) {
      btn.addEventListener('click', async function() {
        const folderType = btn.getAttribute('data-folder') || 'upload';
        const originalText = btn.getAttribute('data-original-text') || btn.textContent.trim();
        btn.setAttribute('data-original-text', originalText);
        btn.textContent = '打开中...';
        try {
          const r = await apiPost('/open-folder', { type: folderType });
          if (r.success) {
            btn.textContent = '✓ 已打开';
            addLog('OK', '已打开文件夹: ' + r.path);
          } else {
            btn.textContent = '✗ 失败';
            addLog('WARN', r.message || '打开文件夹失败');
          }
        } catch (e) {
          btn.textContent = '✗ 失败';
          addLog('WARN', '打开文件夹出错: ' + e.message);
        }
        setTimeout(function() { btn.textContent = originalText; }, 1800);
      });
    });

    // 获取目录信息
    const folders = await apiGet('/folders');
    if (folders.success) {
      const upEl = $('#uploadPath');
      const outEl = $('#outputPath');
      const dlEl = $('#downloadPath');
      if (upEl) upEl.textContent = folders.upload_dir;
      if (outEl) outEl.textContent = folders.output_dir;
      if (dlEl && folders.download_dir) dlEl.textContent = folders.download_dir;
      // 存储供后续使用
      window.folderInfo = folders;
    }

    const health = await apiGet('/health');
    if (health.success) {
      const statusText = health.pipeline_ready ? '已就绪' : '初始化中...';
      addLog('INFO', '后端服务已连接 · 流水线' + statusText);
    } else {
      addLog('WARN', '后端服务连接失败，请确认服务是否启动');
    }
  });

})();
