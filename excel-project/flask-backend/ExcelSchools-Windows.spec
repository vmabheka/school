# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

project_root = Path(SPECPATH)

datas = [
    (str(project_root / 'templates'), 'templates'),
    (str(project_root / 'static'), 'static'),
    # MobiSchola icon + branding shown in the browser tab and bundled assets.
    (str(project_root / 'static' / 'images' / 'mobischola-icon.svg'), 'static/images'),
]
binaries = []
hiddenimports = collect_submodules('flask') + collect_submodules('flask_sqlalchemy')
# Waitress is the Windows-compatible production WSGI server. Include all of
# its modules and package metadata, then verify it from the frozen EXE.
datas += copy_metadata('waitress')
hiddenimports += collect_submodules('waitress')
for package in ('reportlab', 'openpyxl', 'waitress'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ['windows_launcher.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['gunicorn', 'psycopg', 'pymysql'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MobiSchola',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    # The MobiSchola icon is embedded into the EXE itself (falls back to
    # PyInstaller's default if the .ico is missing).
    icon=str(project_root / 'static' / 'images' / 'mobischola.ico'),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
