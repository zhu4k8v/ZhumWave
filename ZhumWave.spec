# -*- mode: python ; coding: utf-8 -*-
# Сборка ZhumWave.exe (PyInstaller, one-file, windowed)
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

has_ico = os.path.exists("ZhumWave.ico")
icon = "ZhumWave.ico" if has_ico else None

datas = [("ZhumWave.png", ".")]
binaries = []
if has_ico:
    datas.append(("ZhumWave.ico", "."))

# PortAudio для sounddevice
datas += collect_data_files("sounddevice")
binaries += collect_dynamic_libs("sounddevice")

# ffmpeg для реальной скорости/atempo
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if ffmpeg_exe and os.path.isfile(ffmpeg_exe):
        datas.append((ffmpeg_exe, "imageio_ffmpeg/binaries"))
except Exception:
    pass

a = Analysis(
    ["audio_player.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=["sounddevice", "numpy", "imageio_ffmpeg", "cffi",
                   "_cffi_backend"],
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
    name="ZhumWave",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version="version_info.txt",
)
