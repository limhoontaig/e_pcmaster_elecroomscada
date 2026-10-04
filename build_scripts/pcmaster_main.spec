# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/pcmaster_main.py'],  # 👈 [수정] 메인 프로그램 위치 (src 폴더 지정)
    pathex=[],
    binaries=[],
    # 👈 [수정] 원본 파일 위치(datas/, assets/)를 명시. 
    # 단, 파이썬 코드 수정을 피하기 위해 패키징 내부 도착지는 기존처럼 '.' (루트)로 유지합니다.
    datas=[
        ('datas/template_전기실_운영일지.xlsx', '.'), 
        ('assets/free-icon-folder-2015058.ico', '.'), 
        ('config.ini', '.')
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
    name='main', # 생성될 실행파일 이름 (필요시 'pcmaster' 등으로 변경 가능)
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
    icon='assets/free-icon-folder-2015058.ico'  # 👈 [수정] 실행파일(.exe)의 자체 아이콘 경로 지정
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