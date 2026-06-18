# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('style_profiles.json', '.'), ('D:\\Program Files\\Tencent\\Marvis\\MarvisAgent\\1.0.1100.151\\runtime\\python311\\Lib\\site-packages\\faster_whisper\\assets\\silero_vad_v6.onnx', 'faster_whisper\\assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SubtitleForge_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
