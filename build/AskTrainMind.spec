# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('openpyxl')
    + collect_submodules('fitz')
    + [
        'fitz',
        'fitz._fitz',
        'docx',
        'docx.oxml',
        'docx.oxml.ns',
        'msal',
        'msal.application',
        'msal.token_cache',
        'openai',
        'openai._client',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'PySide6.QtSvg',
    ]
)

datas = [
    ('asktrainmind/ui/style.qss', 'asktrainmind/ui'),
    ('asktrainmind/resources', 'asktrainmind/resources'),
]

# Collect PyMuPDF data files (native libs) if available
try:
    datas += collect_data_files('fitz')
except Exception:
    pass


a = Analysis(
    ['asktrainmind/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='AskTrainMind',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=None,
)
