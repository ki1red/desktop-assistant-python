# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


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


hiddenimports = []
hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("PySide6")
hiddenimports += collect_submodules("sounddevice")
hiddenimports += collect_submodules("numpy")
hiddenimports += collect_submodules("faster_whisper")
hiddenimports += collect_submodules("ctranslate2")
hiddenimports += collect_submodules("pynput")
hiddenimports += collect_submodules("keyboard")
hiddenimports += collect_submodules("pyperclip")


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
        "tkinter"
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