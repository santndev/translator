# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


project_root = Path(SPEC).resolve().parent
version_info_path = Path(
    os.environ.get(
        "TRANSLATOR_VERSION_INFO",
        project_root / "installer" / "version_info.txt",
    )
)
whisper_repo = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--Systran--faster-whisper-tiny.en"
    / "snapshots"
)
whisper_snapshots = sorted(
    path for path in whisper_repo.glob("*") if path.is_dir()
)
if not whisper_snapshots:
    raise SystemExit(
        "The faster-whisper tiny.en model is not cached. Run the app once "
        "with internet access before building the installer."
    )

datas = [
    (str(project_root / "assets"), "assets"),
    (
        str(project_root / "models" / "vosk-model-small-en-us-0.15"),
        "models/vosk-model-small-en-us-0.15",
    ),
    (str(whisper_snapshots[-1]), "models/faster-whisper-tiny.en"),
]
datas += collect_data_files("faster_whisper")
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("vosk")
hiddenimports = [
    "_portaudiowpatch",
    "ctranslate2._ext",
    "faster_whisper",
    "onnxruntime",
    "tokenizers",
]

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "installer" / "runtime_hook_preload.py")],
    # ctranslate2 ships optional model-conversion modules. Runtime inference
    # does not use their ML/data-science stacks, so keep them out of the MSI.
    excludes=[
        "botocore",
        "matplotlib",
        "openpyxl",
        "pandas",
        "pytest",
        "pytest_asyncio",
        "sqlalchemy",
        "tensorflow",
        "torch",
        "transformers",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Translator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "app_icon.ico"),
    version=str(version_info_path),
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Translator",
)
