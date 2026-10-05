# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['../src/pcmaster_main.py'], 
    pathex=['..'],
    binaries=[],
    datas=[
        ('../datas/template_전기실_운영일지.xlsx', '.'), 
        ('../assets/free-icon-folder-2015058.ico', '.'), 
        ('../config.ini', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main', 
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../assets/free-icon-folder-2015058.ico'  # 👈 [수정] 아이콘 경로도 ../ 적용
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)