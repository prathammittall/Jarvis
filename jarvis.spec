# PyInstaller spec for JARVIS
# Build with: pyinstaller jarvis.spec

# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run_jarvis.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'app', 'app.core', 'app.brain', 'app.speech', 'app.wakeword',
        'app.tools', 'app.memory', 'app.ui',
        'app.core.hotkey', 'app.core.startup', 'app.core.envfile',
        'app.tools.app_catalog', 'app.ui.settings', 'app.ui.tray',
        'app.brain.providers', 'app.brain.providers.gemini', 'app.brain.providers.ollama',
        'faster_whisper', 'openwakeword', 'piper', 'onnxruntime',
        'PySide6', 'sounddevice', 'mss', 'pycaw', 'win32com', 'win32com.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JARVIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JARVIS',
)
