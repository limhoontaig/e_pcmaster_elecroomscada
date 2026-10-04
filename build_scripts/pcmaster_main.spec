# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['../src/pcmaster_main.py'],  # 👈 [수정] 상위 폴더(../)로 나가서 src 폴더를 찾도록 변경
    pathex=[],
    binaries=[],
    datas=[
        ('../datas/template_전기실_운영일지.xlsx', '.'), # 👈 [수정] 이하 동일하게 ../ 적용
        ('../assets/free-icon-folder-2015058.ico', '.'), 
        ('../config.ini', '.')
    ],
    hiddenimports=[
        'src.event_manager',
        'src.pcmaster_worker',
        'src.excel_report',
        'src.tr_controller',
        'src.ui.ui_report_temp',
        'src.ui.ui_report_fan_operation',
        'src.ui.ui_report_fault_status',
        'src.ui.ui_graph_manager',
        'src.ui.ui_dialogs',
        'src.ui.ui_ac_settings',
        'src.ui.ui_hmi_dashboard',
        'src.ui.ui_ventilation',
        'shared.db_manager',
        'openpyxl',
        'pymysql',
        'sqlalchemy',
    ],
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