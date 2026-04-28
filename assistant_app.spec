# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve()


def existing_file(relative_path: str, target_dir: str):
    """
    Добавляет файл в datas только если он реально существует.
    Это удобно, чтобы сборка не падала из-за отсутствующих optional-файлов.
    """
    source = PROJECT_ROOT / relative_path
    if source.exists() and source.is_file():
        return [(str(source), target_dir)]
    return []


def existing_tree(relative_path: str, target_dir: str):
    """
    Добавляет папку в datas только если она реально существует.
    """
    source = PROJECT_ROOT / relative_path
    if source.exists() and source.is_dir():
        return [(str(source), target_dir)]
    return []


hiddenimports = []

# Весь проект app собираем целиком, включая plugins.
hiddenimports += collect_submodules("app")

# GUI / системные модули.
hiddenimports += [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",

    "sounddevice",
    "numpy",
    "wave",

    "faster_whisper",
    "faster_whisper.transcribe",
    "ctranslate2",
    "onnxruntime",
    "av",
    "tokenizers",
    "huggingface_hub",

    "pynput",
    "keyboard",
    "pyperclip",

    "sqlite3",
    "rapidfuzz",

    "pyttsx3",
    "comtypes",
    "comtypes.client",
]

datas = []

# faster-whisper assets: особенно важен silero_vad_v6.onnx.
datas += collect_data_files(
    "faster_whisper",
    includes=[
        "assets/*",
        "assets/*.onnx",
    ],
)

# Основной конфиг.
datas += existing_file(
    "config/default_settings.json",
    "config",
)

# NLU-ресурсы.
datas += existing_tree(
    "config/nlu",
    "config/nlu",
)

# Ресурсы плагинов.
datas += existing_file(
    "app/plugins/builtin/commands.json",
    "app/plugins/builtin",
)

# Assets приложения.
datas += existing_tree(
    "assets",
    "assets",
)

# Локальные модели, если папка есть.
datas += existing_tree(
    "models",
    "models",
)

excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "IPython",
    "jupyter",
    "matplotlib",
    "scipy",
    "pandas",

    # Обычно не нужен, сильно утяжеляет сборку.
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
]


a = Analysis(
    ["assistant_app.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LocalAssistant",
)