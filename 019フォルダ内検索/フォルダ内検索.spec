# -*- mode: python ; coding: utf-8 -*-

import os

python_dir = r'C:\Users\i58400am\AppData\Local\Programs\Python\Python312'
tcl_dir = os.path.join(python_dir, 'tcl')
dll_dir = os.path.join(python_dir, 'DLLs')


a = Analysis(
    ['フォルダを検索複数設定.py'],
    pathex=[],
    binaries=[
        (os.path.join(dll_dir, 'tcl86t.dll'), '.'),
        (os.path.join(dll_dir, 'tk86t.dll'), '.'),
    ],
    datas=[
        (os.path.join(tcl_dir, 'tcl8.6'), 'tcl/tcl8.6'),
        (os.path.join(tcl_dir, 'tk8.6'), 'tcl/tk8.6'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.ttk',
    ],
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
    name='フォルダ内検索',
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
