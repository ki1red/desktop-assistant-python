from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("PySide6")
hiddenimports += [
    "app.bootstrap",
    "app.app_paths",
    "app.indexing.index_state",
]

a = Analysis(
    ["assistant_app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("config/default_settings.json", "config"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
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