# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files


project_root = Path.cwd()

datas = [
    ("config/default_settings.json", "config"),
]

if (project_root / "config" / "nlu").exists():
    datas.append(("config/nlu", "config/nlu"))

if (project_root / "assets").exists():
    datas.append(("assets", "assets"))

if (project_root / "models").exists():
    datas.append(("models", "models"))

# ВАЖНО:
# faster-whisper использует ONNX-файл silero_vad_v6.onnx для VAD.
# Без этого файла собранное приложение падает при распознавании речи.
datas += collect_data_files(
    "faster_whisper",
    includes=[
        "assets/*",
        "assets/*.onnx"
    ]
)


hiddenimports = []

hiddenimports += collect_submodules("app")

hiddenimports += [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",

    "sounddevice",
    "numpy",

    "faster_whisper",
    "faster_whisper.transcribe",
    "faster_whisper.vad",

    "ctranslate2",
    "onnxruntime",

    "pynput",
    "pynput.keyboard",
    "keyboard",
    "pyperclip"
]


a = Analysis(
    ["assistant_app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        "numpy.tests",
        "numpy.f2py.tests",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick"
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalAssistant",
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LocalAssistant",
)