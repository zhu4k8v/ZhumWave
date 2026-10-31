# -*- coding: utf-8 -*-
"""
ZhumWave — музыкальный плеер (MP3 / MP4)
- DPI-aware: интерфейс не «мылится» на любом масштабе Windows
- все иконки и ползунки рисуются векторно с 6x сглаживанием
- перемотка ±10 сек: ← / → или A / D
- порядок треков как в папке, без нумерации
- поиск по плейлисту
- Mute, сохранение громкости и списка треков
- «Добавить трек» добавляет выбранные файлы в текущий плейлист
"""

import os
import re
import sys
import time
import json
import math
import queue
import socket
import threading
import subprocess
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4
except ImportError:
    MP3 = None
    MP4 = None

try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# Аудиомодули подключаются при первом воспроизведении: окно открывается
# заметно быстрее, а звук по-прежнему проверяется до запуска трека.
np = None
sd = None
imageio_ffmpeg = None
HAS_STREAM = True
_STREAM_IMPORT_TRIED = False


def ensure_stream_modules():
    global np, sd, imageio_ffmpeg, HAS_STREAM, _STREAM_IMPORT_TRIED
    if np is not None and sd is not None and imageio_ffmpeg is not None:
        return True
    if _STREAM_IMPORT_TRIED:
        return False
    _STREAM_IMPORT_TRIED = True
    try:
        import numpy as _np
        import sounddevice as _sd
        import imageio_ffmpeg as _ff
        np, sd, imageio_ffmpeg = _np, _sd, _ff
        HAS_STREAM = True
        return True
    except Exception:
        np = None
        sd = None
        imageio_ffmpeg = None
        HAS_STREAM = False
        return False

# ----------------------------- палитра -------------------------------------
# ZhumWave: светло-чёрный графит + серебристо-белый акцент
BG = "#17181c"
PANEL = "#1e1f24"
CARD = "#24252b"
CARD_EDGE = "#393b43"
ROW_ALT = "#292b31"
ROW_HOVER = "#32343b"
ROW_PRESS = "#3b3d45"
TEXT = "#f4f4f6"
MUTED = "#adafb5"
BTN = "#2c2e35"
BTN_HOVER = "#373941"
BTN_DOWN = "#24252b"
TRACK_LINE = "#474a52"
TRACK_LINE_HOVER = "#5e616a"
DEFAULT_ACCENT = "#d7d9dd"
SWATCH_RING = "#909298"        # серое кольцо выбранного цвета
SWATCH_RING_HOVER = "#5b5d62"
GREEN_GRADIENT_ACCENT = "#6ec99b"
GREEN_GRADIENT_TOP = "#3e8f6c"
GREEN_GRADIENT_BOTTOM = "#a9e4c1"
RED_GRADIENT_ACCENT = "#d4575f"
RED_GRADIENT_TOP = "#8f2f38"
RED_GRADIENT_BOTTOM = "#ff9aa1"
BLUE_GRADIENT_ACCENT = "#5f8fe0"
BLUE_GRADIENT_TOP = "#2b4c8c"
BLUE_GRADIENT_BOTTOM = "#9cc4ff"
PURPLE_GRADIENT_ACCENT = "#9270d6"
PURPLE_GRADIENT_TOP = "#54358a"
PURPLE_GRADIENT_BOTTOM = "#c9a6ff"
GRADIENT_ACCENTS = {
    GREEN_GRADIENT_ACCENT.lower(): (GREEN_GRADIENT_TOP, GREEN_GRADIENT_BOTTOM),
    RED_GRADIENT_ACCENT.lower(): (RED_GRADIENT_TOP, RED_GRADIENT_BOTTOM),
    BLUE_GRADIENT_ACCENT.lower(): (BLUE_GRADIENT_TOP, BLUE_GRADIENT_BOTTOM),
    PURPLE_GRADIENT_ACCENT.lower(): (PURPLE_GRADIENT_TOP,
                                     PURPLE_GRADIENT_BOTTOM),
}
ACCENT_PRESETS = (
    ("Красный градиент", RED_GRADIENT_ACCENT),
    ("Оранжевый", "#f08a24"),
    ("Жёлтый", "#e6c84f"),
    ("Зелёный", "#3fbf6f"),
    ("Бирюзовый", "#3fbfc4"),
    ("Синий градиент", BLUE_GRADIENT_ACCENT),
    ("Фиолетовый градиент", PURPLE_GRADIENT_ACCENT),
    ("Розовый", "#ff6b9a"),
    ("Пудровый", "#e8b4b8"),
    ("Персиковый", "#f6c7a1"),
    ("Карамельный", "#e8c7a8"),
    ("Лимонный", "#f2e2a0"),
    ("Мятный", "#b8e0c2"),
    ("Мятно-зелёный", "#cfe6d4"),
    ("Небесный", "#b9d4f2"),
    ("Лазурный", "#b7d9ea"),
    ("Лавандовый", "#d4c3ec"),
    ("Сиреневый", "#d6c6e8"),
    ("Розовый пастель", "#f2b8d0"),
    ("Пыльно-розовый", "#e3c3c9"),
    ("Серо-голубой", "#aebfcc"),
    ("Зелёный градиент", GREEN_GRADIENT_ACCENT),
)

# красный фон и белый текст для недоступных треков
MISSING_TINT = "#ff4d4f"
MISSING_BG = "#a33237"
MISSING_HOVER = "#bf454a"
MISSING_PRESS = "#8a272c"
MISSING_SEL = "#c94a4f"

DARK_THEME = {
    "BG": "#17181c", "PANEL": "#1e1f24", "CARD": "#24252b",
    "CARD_EDGE": "#393b43", "ROW_ALT": "#292b31", "ROW_HOVER": "#32343b",
    "ROW_PRESS": "#3b3d45", "TEXT": "#f4f4f6", "MUTED": "#adafb5",
    "BTN": "#2c2e35", "BTN_HOVER": "#373941", "BTN_DOWN": "#24252b",
    "TRACK_LINE": "#474a52", "TRACK_LINE_HOVER": "#5e616a",
}
LIGHT_THEME = {
    "BG": "#f3f4f6", "PANEL": "#ffffff", "CARD": "#fafbfc",
    "CARD_EDGE": "#d8dce1", "ROW_ALT": "#f2f4f6", "ROW_HOVER": "#e8ebef",
    "ROW_PRESS": "#dde1e7", "TEXT": "#1b1c1f", "MUTED": "#5f646c",
    "BTN": "#e9ecf0", "BTN_HOVER": "#dfe3e8", "BTN_DOWN": "#d3d8df",
    "TRACK_LINE": "#cdd2d8", "TRACK_LINE_HOVER": "#a8afb8",
}


def apply_theme_palette(light):
    """Переключает фоновую палитру на светлую или тёмную."""
    global SYSTEM_LIGHT
    SYSTEM_LIGHT = bool(light)
    for name, value in (LIGHT_THEME if light else DARK_THEME).items():
        globals()[name] = value

APP_NAME = "ZhumWave"
SEEK_STEP = 10  # секунд
PLACEHOLDER = "Поиск трека…"

# глобальные настройки (общие для всех окон)
ACCENT = DEFAULT_ACCENT
THEME_MODE = "manual"      # тема всегда тёмная
ACCENT_MODE = "manual"     # manual | system (следовать цвету Windows)
ACCENT_CHECK_TS = 0.0      # общий троттлинг опроса акцента Windows
SYSTEM_LIGHT = False
VOLUME = 0.2
MUTE_STATE = False
REPEAT = False
SAVED_TRACKS = []      # восстановление импортированных треков при запуске
SAVED_FOLDER_TRACKS = []   # верхняя группа: из папки
SAVED_ADDED_TRACKS = []    # нижняя группа: добавленные файлы
SAVED_FOLDER = None
VIEW_SEPARATOR = -1    # служебная строка-разделитель в списке
LAST_TRACK = None      # последний трек и позиция для продолжения
LAST_POSITION = 0.0
LAST_DURATION = 0.0
SINGLE_INSTANCE_PORT = 50573
MUTEX_HANDLE = None
APP_ROOT = None
APP_RUNNING = False
DURATION_CACHE = {}
BASE_MIXER_RATE = 44100
MIXER_RATE = BASE_MIXER_RATE
SPEED = 1.0
SPEED_MIN = 0.5
SPEED_MAX = 2.0

# масштаб интерфейса (пересчитывается под DPI при старте)
SCALE = 1.0
WINDOWS = []
APP_ICON = None
ICON_SS = 8      # сглаживание иконок кнопок
SHAPE_SS = 8     # сглаживание фигур/ползунков


def app_data_dir():
    """Постоянная пользовательская папка (не временная папка PyInstaller)."""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, APP_NAME)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def resource_path(name):
    """Путь к ресурсу и в исходниках, и внутри собранного EXE."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)


def legacy_settings_paths():
    """Прежние места player_settings.json — для миграции без потери данных."""
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                           else os.path.abspath(__file__))
    return [os.path.join(base, "player_settings.json")]


def settings_path():
    return os.path.join(app_data_dir(), "player_settings.json")



def _is_greenish(color):
    """Определяет старые зелёные/бирюзовые акценты — их нужно заменить."""
    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
    except Exception:
        return False
    return g > r + 20 and g >= b - 25


def _read_reg_dword(path, name):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _kind = winreg.QueryValueEx(key, name)
        return int(value)
    except Exception:
        return None


def system_accent_color():
    """Акцент Windows из реестра; None, если прочитать не удалось."""
    value = _read_reg_dword(
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent",
        "AccentColorMenu")
    if value is None:
        value = _read_reg_dword(r"Software\Microsoft\Windows\DWM",
                                "AccentColor")
    if value is not None:
        # AccentColorMenu хранится как 0xAABBGGRR
        r = value & 0xFF
        g = (value >> 8) & 0xFF
        b = (value >> 16) & 0xFF
        return "#%02x%02x%02x" % (r, g, b)
    value = _read_reg_dword(r"Software\Microsoft\Windows\DWM",
                            "ColorizationColor")
    if value is not None:
        # ColorizationColor хранится как 0xAARRGGBB
        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF
        return "#%02x%02x%02x" % (r, g, b)
    return None


def system_uses_light_theme():
    value = _read_reg_dword(
        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        "AppsUseLightTheme")
    return bool(value) if value is not None else False


def load_settings():
    """Читает сохранённые цвет, громкость, Mute, треки и позицию."""
    global ACCENT, THEME_MODE, ACCENT_MODE
    global VOLUME, MUTE_STATE, SAVED_TRACKS, SAVED_FOLDER
    global SAVED_FOLDER_TRACKS, SAVED_ADDED_TRACKS
    global LAST_TRACK, LAST_POSITION, LAST_DURATION, REPEAT
    data = None
    seen = set()
    for path in [settings_path()] + legacy_settings_paths():
        if path in seen:
            continue
        seen.add(path)
        try:
            if os.path.isfile(path):
                import json
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                break
        except Exception:
            continue
    # Тема всегда одна — тёмная. Акцент может быть ручным или системным.
    THEME_MODE = "manual"
    if not isinstance(data, dict):
        ACCENT_MODE = "manual"
        ACCENT = DEFAULT_ACCENT
        return

    if data.get("accent_mode") == "system":
        ACCENT_MODE = "system"
        ACCENT = system_accent_color() or DEFAULT_ACCENT
    else:
        ACCENT_MODE = "manual"
        saved_color = data.get("accent")
        if (isinstance(saved_color, str) and len(saved_color) == 7
                and saved_color.startswith("#")):
            ACCENT = saved_color
        else:
            ACCENT = DEFAULT_ACCENT
    try:
        vol = data.get("volume")
        if isinstance(vol, (int, float)):
            VOLUME = max(0.0, min(float(vol), 1.0))
        muted = data.get("muted")
        if isinstance(muted, bool):
            MUTE_STATE = muted
        folder_tracks = data.get("folder_tracks")
        added_tracks = data.get("added_tracks")
        if isinstance(folder_tracks, list) and isinstance(added_tracks, list):
            SAVED_FOLDER_TRACKS = [t for t in folder_tracks
                                   if isinstance(t, str)]
            SAVED_ADDED_TRACKS = [t for t in added_tracks
                                  if isinstance(t, str)]
            SAVED_TRACKS = SAVED_FOLDER_TRACKS + SAVED_ADDED_TRACKS
        else:
            # старый формат: все треки считаем импортированными из папки
            tracks = data.get("tracks")
            if isinstance(tracks, list):
                SAVED_TRACKS = [t for t in tracks if isinstance(t, str)]
            SAVED_FOLDER_TRACKS = list(SAVED_TRACKS)
            SAVED_ADDED_TRACKS = []
        folder = data.get("folder")
        if isinstance(folder, str) and folder:
            SAVED_FOLDER = folder
        last = data.get("last_track")
        if isinstance(last, str) and last:
            LAST_TRACK = last
        pos = data.get("last_position")
        if isinstance(pos, (int, float)):
            LAST_POSITION = max(0.0, float(pos))
        dur = data.get("last_duration")
        if isinstance(dur, (int, float)):
            LAST_DURATION = max(0.0, float(dur))
        repeat = data.get("repeat")
        if isinstance(repeat, bool):
            REPEAT = repeat
    except Exception:
        pass


def save_settings():
    """Сохраняет цвет, громкость, Mute, треки и позицию последнего трека."""
    global LAST_TRACK, LAST_POSITION, LAST_DURATION
    try:
        import json
        data = {"accent": ACCENT, "accent_mode": ACCENT_MODE,
                "theme": THEME_MODE,
                "volume": round(VOLUME, 3),
                "muted": bool(MUTE_STATE), "repeat": bool(REPEAT),
                "tracks": list(SAVED_TRACKS),
                "folder_tracks": list(SAVED_FOLDER_TRACKS),
                "added_tracks": list(SAVED_ADDED_TRACKS),
                "last_track": LAST_TRACK,
                "last_position": round(float(LAST_POSITION or 0.0), 3),
                "last_duration": round(float(LAST_DURATION or 0.0), 3)}
        if SAVED_FOLDER:
            data["folder"] = SAVED_FOLDER
        path = settings_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
    except Exception:
        pass


def apply_audio_volume():
    """Громкость читается аудиопотоком из глобальных VOLUME/MUTE_STATE."""
    return


def _colorref(color):
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return r | (g << 8) | (b << 16)


def apply_windows_titlebar(root):
    """Красит системный заголовок Windows в тон кнопкам (Win10/11)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        dark = ctypes.c_int(0 if SYSTEM_LIGHT else 1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        caption = ctypes.c_int(_colorref(BTN))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
        text = ctypes.c_int(_colorref(BTN))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
        border = ctypes.c_int(_colorref(CARD_EDGE))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 34, ctypes.byref(border), ctypes.sizeof(border))
    except Exception:
        pass


def ensure_ico():
    """Возвращает путь к ZhumWave.ico; при необходимости создаёт его из PNG."""
    ico = resource_path("ZhumWave.ico")
    if os.path.isfile(ico):
        return ico
    if not HAS_PIL:
        return None
    png = resource_path("ZhumWave.png")
    if not os.path.isfile(png):
        return None
    try:
        dst = os.path.join(app_data_dir(), "ZhumWave.ico")
        if not os.path.isfile(dst):
            img = Image.open(png).convert("RGBA")
            w, h = img.size
            side = max(w, h)
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
            canvas.save(dst, format="ICO",
                        sizes=[(16, 16), (32, 32), (48, 48),
                               (64, 64), (128, 128), (256, 256)])
        return dst
    except Exception:
        return None


def apply_app_icon(root):
    """Ставит ZhumWave.png (и .ico) в taskbar/Alt+Tab; шапку очищаем отдельно."""
    global APP_ICON
    try:
        png = resource_path("ZhumWave.png")
        if os.path.isfile(png):
            img = tk.PhotoImage(file=png)
            root.iconphoto(True, img)
            APP_ICON = img
    except Exception:
        pass
    try:
        ico = ensure_ico()
        if ico:
            root.iconbitmap(default=ico)
    except Exception:
        pass


def ensure_blank_icon():
    """Прозрачная маленькая иконка, чтобы в системной шапке не было логотипа."""
    if not HAS_PIL:
        return None
    try:
        path = os.path.join(app_data_dir(), "blank.ico")
        if not os.path.isfile(path):
            img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            img.save(path, format="ICO", sizes=[(16, 16), (32, 32)])
        return path
    except Exception:
        return None


def hide_titlebar_icon(root):
    """Прячет маленькую иконку в шапке; большая остаётся для taskbar/Alt+Tab."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        root.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x10
        user32.LoadImageW.restype = ctypes.c_void_p
        big_path = ensure_ico()
        small_path = ensure_blank_icon()
        big = 0
        small = 0
        if big_path:
            big = user32.LoadImageW(None, big_path, IMAGE_ICON, 32, 32,
                                    LR_LOADFROMFILE)
        if small_path:
            small = user32.LoadImageW(None, small_path, IMAGE_ICON, 16, 16,
                                      LR_LOADFROMFILE)

        # иконки класса TkTopLevel: большая для taskbar, прозрачная для шапки
        GCLP_HICON = -14
        GCLP_HICONSM = -34
        user32.SetClassLongPtrW.restype = ctypes.c_void_p
        user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                            ctypes.c_void_p]
        if big:
            user32.SetClassLongPtrW(hwnd, GCLP_HICON, ctypes.c_void_p(big))
        if small:
            user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, ctypes.c_void_p(small))
    except Exception:
        pass


def enable_file_drop(widget):
    """Принимает файлы, перетащенные из Проводника (WM_DROPFILES)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        widget.update_idletasks()
        hwnd = widget.winfo_id()
        WM_DROPFILES = 0x0233
        GWL_WNDPROC = -4
        LRESULT = ctypes.c_ssize_t
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            get_long = user32.GetWindowLongPtrW
            set_long = user32.SetWindowLongPtrW
        else:
            get_long = user32.GetWindowLongW
            set_long = user32.SetWindowLongW
        get_long.restype = LRESULT
        get_long.argtypes = [wintypes.HWND, ctypes.c_int]
        set_long.restype = LRESULT
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, LRESULT]
        call_proc = user32.CallWindowProcW
        call_proc.restype = LRESULT
        call_proc.argtypes = [LRESULT, wintypes.HWND, wintypes.UINT,
                              wintypes.WPARAM, wintypes.LPARAM]
        query = shell32.DragQueryFileW
        query.restype = wintypes.UINT
        query.argtypes = [wintypes.HANDLE, wintypes.UINT,
                          wintypes.LPWSTR, wintypes.UINT]
        shell32.DragFinish.argtypes = [wintypes.HANDLE]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]

        queue = getattr(widget, "_drop_queue", None)
        if queue is None:
            queue = []
            widget._drop_queue = queue
        old_proc = get_long(hwnd, GWL_WNDPROC)
        proc_type = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                       wintypes.WPARAM, wintypes.LPARAM)

        def wndproc(h, msg, wp, lp):
            if msg == WM_DROPFILES:
                files = []
                try:
                    count = query(wp, 0xFFFFFFFF, None, 0)
                    for i in range(count):
                        length = query(wp, i, None, 0)
                        buf = ctypes.create_unicode_buffer(length + 1)
                        query(wp, i, buf, length + 1)
                        if buf.value:
                            files.append(buf.value)
                except Exception:
                    files = []
                finally:
                    try:
                        shell32.DragFinish(wp)
                    except Exception:
                        pass
                if files:
                    # никаких вызовов Tk из WndProc — только очередь
                    queue.append(list(files))
                return 0
            return call_proc(old_proc, h, msg, wp, lp)

        proc = proc_type(wndproc)
        widget._drop_old_proc = old_proc
        widget._drop_proc = proc
        set_long(hwnd, GWL_WNDPROC,
                 ctypes.cast(proc, ctypes.c_void_p).value)
        shell32.DragAcceptFiles(hwnd, True)
        return True
    except Exception as exc:
        debug_log("file drop setup failed: %r" % (exc,))
        return False


def disable_file_drop(widget):
    """Снимает перехват WM_DROPFILES перед уничтожением окна."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        hwnd = widget.winfo_id()
        old = getattr(widget, "_drop_old_proc", None)
        if old:
            LRESULT = ctypes.c_ssize_t
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                set_long = user32.SetWindowLongPtrW
            else:
                set_long = user32.SetWindowLongW
            set_long.restype = LRESULT
            set_long.argtypes = [wintypes.HWND, ctypes.c_int, LRESULT]
            set_long(hwnd, -4, old)
        shell32.DragAcceptFiles(hwnd, False)
    except Exception:
        pass


def lock_window_size(root, width, height):
    """Фиксирует клиентскую область: без растягивания и максимизации."""
    try:
        root.resizable(False, False)
        root.minsize(width, height)
        root.maxsize(width, height)
    except Exception:
        pass


def display_name(path):
    """Имя файла без расширения — для плейлиста, шапки и поиска."""
    return os.path.splitext(os.path.basename(path))[0]


def display_title(path):
    """Название для шапки: без расширения и без порядкового номера в имени."""
    name = display_name(path)
    clean = re.sub(r"^\s*\d{1,4}\s*(?:[\.\)]|[-–—])\s*", "", name).strip()
    return clean or name


def log_exception(exc_type, exc_value, exc_tb):
    """Пишет любую необработанную ошибку в постоянный лог ZhumWave."""
    try:
        import traceback
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        with open(os.path.join(app_data_dir(), "zhumwave_error.log"),
                  "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


def debug_log(message):
    """Диагностика «Открыть с помощью» при ZHUMWAVE_DEBUG=1."""
    if os.environ.get("ZHUMWAVE_DEBUG") != "1":
        return
    try:
        with open(os.path.join(app_data_dir(), "debug.log"),
                  "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%H:%M:%S ") + str(message) + "\n")
    except Exception:
        pass


def forward_to_existing(payload):
    """Передаёт файл/фокус уже запущенному ZhumWave. True — экземпляр есть."""
    try:
        with socket.create_connection(("127.0.0.1", SINGLE_INSTANCE_PORT),
                                      timeout=0.45) as sock:
            sock.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            reply = sock.recv(16)
        return reply.startswith(b"ZHUMWAVE")
    except Exception:
        return False


def acquire_single_instance():
    """Именованный мьютекс Windows: True — мы первый экземпляр."""
    global MUTEX_HANDLE
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "Local\\ZhumWave.SingleInstance")
        if not handle:
            return True
        MUTEX_HANDLE = handle
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def start_instance_server(app):
    """Слушает локальный порт и складывает запросы в очередь главного окна."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        server.listen(8)
    except OSError:
        try:
            server.close()
        except Exception:
            pass
        return None

    def serve():
        while True:
            try:
                conn, _ = server.accept()
                with conn:
                    raw = conn.recv(262144)
                    conn.sendall(b"ZHUMWAVE")
                payload = json.loads(raw.decode("utf-8") or "{}")
                if isinstance(payload, dict):
                    app._inbox.put(payload)
            except Exception:
                pass

    threading.Thread(target=serve, daemon=True).start()
    return server


def _delete_reg_value(winreg, root, path, name):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass


def _reg_command_matches(winreg, root, path, expected):
    """Проверяет, что команда открытия уже указывает на этот EXE."""
    try:
        with winreg.OpenKey(root, path) as key:
            value, _kind = winreg.QueryValueEx(key, "")
        return os.path.normcase(str(value)) == os.path.normcase(expected)
    except OSError:
        return False


def register_file_associations():
    """Добавляет ZhumWave в «Открыть с помощью» только для .mp3 (HKCU)."""
    if sys.platform != "win32":
        return
    try:
        import winreg

        exts = (".mp3",)
        old_exts = (".mp4", ".m4a", ".wav", ".flac", ".ogg")
        progid = "ZhumWave.AudioFile"
        classes = r"Software\Classes"

        if getattr(sys, "frozen", False):
            exe = sys.executable
            command = '"%s" "%%1"' % exe
            icon = exe + ",0"
            app_exe = os.path.basename(exe)
        else:
            exe = sys.executable
            pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
            runner = pyw if os.path.isfile(pyw) else exe
            script = os.path.abspath(__file__)
            command = '"%s" "%s" "%%1"' % (runner, script)
            icon = (ensure_ico() or "") + ",0"
            app_exe = None

        # Быстрый запуск: если регистрация уже сделана для этого пути,
        # повторно ничего не пишем в реестр.
        marker = os.path.join(app_data_dir(), "assoc_state.json")
        try:
            stamp = os.path.getmtime(exe)
        except OSError:
            stamp = 0
        signature = "2|%s|%s" % (os.path.normcase(exe), stamp)
        try:
            with open(marker, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
            if (saved.get("signature") == signature
                    and _reg_command_matches(
                        winreg, winreg.HKEY_CURRENT_USER,
                        classes + "\\" + progid + r"\shell\open\command",
                        command)):
                return
        except Exception:
            pass

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              classes + "\\" + progid) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "ZhumWave audio")
            winreg.SetValueEx(key, "FriendlyTypeName", 0, winreg.REG_SZ,
                              "ZhumWave audio")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              classes + "\\" + progid + r"\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              classes + "\\" + progid + r"\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

        app_key = classes + r"\Applications\ZhumWave.exe"
        if app_exe and app_exe.lower() == "zhumwave.exe":
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key) as key:
                winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ,
                                  "ZhumWave")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  app_key + r"\shell\open\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              app_key + r"\SupportedTypes") as key:
            for ext in exts:
                winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, "")
            # раньше были зарегистрированы и другие расширения — убираем
            for ext in old_exts:
                _delete_reg_value(winreg, winreg.HKEY_CURRENT_USER,
                                  app_key + r"\SupportedTypes", ext)

        for ext in exts:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  classes + "\\" + ext + r"\OpenWithProgids") as key:
                winreg.SetValueEx(key, progid, 0, winreg.REG_SZ, "")
            if app_exe and app_exe.lower() == "zhumwave.exe":
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                      classes + "\\" + ext + r"\OpenWithList") as key:
                    winreg.SetValueEx(key, "ZhumWave.exe", 0, winreg.REG_SZ, "")

        # чистим старые регистрации для видео/других форматов
        for ext in old_exts:
            base = classes + "\\" + ext
            _delete_reg_value(winreg, winreg.HKEY_CURRENT_USER,
                              base + r"\OpenWithProgids", progid)
            _delete_reg_value(winreg, winreg.HKEY_CURRENT_USER,
                              base + r"\OpenWithList", "ZhumWave.exe")
        try:
            with open(marker, "w", encoding="utf-8") as fh:
                json.dump({"signature": signature}, fh)
        except Exception:
            pass
        # SHChangeNotify здесь не вызываем: запуск не должен обновлять рабочий стол
    except Exception:
        pass


def init_windows_app_id():
    """AppUserModelID + имя для панели задач (в шапке заголовок остаётся пустым)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import winreg
        key_path = r"Software\Classes\AppUserModelId\ZhumWave.Player"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            icon_path = (sys.executable if getattr(sys, "frozen", False)
                         else ensure_ico())
            if icon_path:
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon_path)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZhumWave.Player")
    except Exception:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZhumWave.Player")
        except Exception:
            pass



def S(value):
    """Пересчёт размера под масштаб экрана."""
    return int(round(value * SCALE))


def enable_dpi_awareness():
    """Заставляет Windows рисовать интерфейс в физических пикселях (без мыла)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        return True
    except Exception:
        return False


def mix(c1, c2, t):
    """Смешивает два цвета: t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def contrast_text(color):
    """Тёмный или светлый текст поверх акцентного фона."""
    try:
        r = int(color[1:3], 16) / 255.0
        g = int(color[3:5], 16) / 255.0
        b = int(color[5:7], 16) / 255.0
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "#0b0b0b" if lum > 0.55 else "#ffffff"
    except Exception:
        return "#0b0b0b"


def elide(text, font, max_px):
    """Обрезает текст по ширине с многоточием (для длинных имён файлов)."""
    if max_px <= 0:
        return ""
    try:
        if font.measure(text) <= max_px:
            return text
    except Exception:
        return text
    tail = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        if font.measure(text[:mid] + tail) <= max_px:
            lo = mid + 1
        else:
            hi = mid
    return text[:max(0, lo - 1)] + tail


def _search_normalize(text):
    """Нижний регистр, ё → е, без лишних пробелов."""
    return " ".join(str(text).lower().replace("ё", "е").split())


def _is_subsequence(needle, haystack):
    """Все буквы запроса встречаются по порядку, но не обязательно рядом."""
    pos = 0
    for ch in needle:
        pos = haystack.find(ch, pos)
        if pos < 0:
            return False
        pos += 1
    return True


def _edit_distance(a, b, limit):
    """Расстояние Левенштейна с ранним выходом за пределы limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for i, ch in enumerate(b, 1):
        cur = [i]
        best = i
        for j, ca in enumerate(a, 1):
            value = min(prev[j] + 1, cur[j - 1] + 1,
                        prev[j - 1] + (ca != ch))
            cur.append(value)
            if value < best:
                best = value
        if best > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _name_matches_terms(name, terms):
    """Приблизительное совпадение: подстрока, буквы по порядку или опечатка."""
    if not terms:
        return True
    words = None
    for term in terms:
        if term in name:
            continue
        if len(term) >= 2 and _is_subsequence(term, name):
            continue
        if len(term) < 3:
            return False
        if words is None:
            words = re.findall(r"[^\W_]+", name, re.UNICODE)
        limit = 1 if len(term) <= 5 else (2 if len(term) <= 8 else 3)
        matched = False
        for word in words:
            if abs(len(word) - len(term)) > limit:
                continue
            if _edit_distance(term, word, limit) <= limit:
                matched = True
                break
        if not matched:
            return False
    return True


_CORNER_TILES = {}


def rounded_corner_tiles(radius, color, bg, outline=None):
    """Четыре сглаженных уголка для скруглённой панели (быстро)."""
    if not HAS_PIL:
        return None
    r = max(1, int(round(radius)))
    key = (r, color, bg, outline)
    tiles = _CORNER_TILES.get(key)
    if tiles is not None:
        return tiles
    try:
        scale = max(4, SHAPE_SS)
        d = 2 * r * scale
        img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([0, 0, d - 1, d - 1], fill=color)
        if outline:
            draw.ellipse([0, 0, d - 1, d - 1], outline=outline,
                         width=max(1, scale))
        img = img.resize((2 * r, 2 * r), Image.LANCZOS)
        base = Image.new("RGB", (2 * r, 2 * r), bg)
        base.paste(img, (0, 0), img)
        boxes = ((0, 0, r, r), (r, 0, 2 * r, r),
                 (0, r, r, 2 * r), (r, r, 2 * r, 2 * r))
        tiles = tuple(ImageTk.PhotoImage(base.crop(b)) for b in boxes)
    except Exception:
        return None
    _CORNER_TILES[key] = tiles
    return tiles


def draw_rounded_panel(canvas, w, h, color, bg, radius, border=None):
    """Рисует скруглённую панель без полноразмерного сглаживания."""
    canvas.delete("all")
    r = max(1, int(round(radius)))
    if w <= 2 * r or h <= 2 * r:
        canvas.create_rectangle(0, 0, w, h, fill=color,
                                outline=border or "")
        return None
    canvas.create_rectangle(r, 0, w - r, h, fill=color, outline="")
    canvas.create_rectangle(0, r, w, h - r, fill=color, outline="")
    if border:
        line_w = max(1, int(round(1 * max(1.0, SCALE))))
        canvas.create_line(r, line_w / 2.0, w - r, line_w / 2.0,
                           fill=border, width=line_w)
        canvas.create_line(r, h - line_w / 2.0, w - r, h - line_w / 2.0,
                           fill=border, width=line_w)
        canvas.create_line(line_w / 2.0, r, line_w / 2.0, h - r,
                           fill=border, width=line_w)
        canvas.create_line(w - line_w / 2.0, r, w - line_w / 2.0, h - r,
                           fill=border, width=line_w)
    tiles = rounded_corner_tiles(r, color, bg, outline=border)
    if not tiles:
        canvas.create_rectangle(0, 0, w, h, fill=color,
                                outline=border or "")
        return None
    for img, x, y in zip(tiles, (0, w - r, 0, w - r),
                         (0, 0, h - r, h - r)):
        canvas.create_image(x, y, image=img, anchor="nw")
    return tiles


def smooth_image(w, h, color, bg, radius=None, scale=None):
    """Сглаженный круг/«пилюля» как PhotoImage."""
    if not HAS_PIL:
        return None
    scale = scale or SHAPE_SS
    w = max(1, int(round(w)))
    h = max(1, int(round(h)))
    W, H = w * scale, h * scale
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = (H // 2) if radius is None else int(radius * scale)
    r = max(0, min(r, W // 2, H // 2))
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=r, fill=color)
    img = img.resize((w, h), Image.LANCZOS)
    base = Image.new("RGB", (w, h), bg)
    base.paste(img, (0, 0), img)
    return ImageTk.PhotoImage(base)


# ----------------------------- иконки --------------------------------------
def _icon_parts(kind, size):
    """Геометрия значков; значки чуть меньше круга, по центру."""
    if kind == "play":
        parts = [("poly", [(0.39 * size, 0.26 * size),
                           (0.39 * size, 0.74 * size),
                           (0.74 * size, 0.50 * size)])]
    elif kind == "pause":
        w = 0.085 * size
        parts = [("rect", (0.355 * size, 0.27 * size,
                           0.355 * size + w, 0.73 * size)),
                 ("rect", (0.56 * size, 0.27 * size,
                           0.56 * size + w, 0.73 * size))]
    elif kind == "prev":
        w = 0.065 * size
        parts = [("rect", (0.275 * size, 0.28 * size,
                           0.275 * size + w, 0.72 * size)),
                 ("poly", [(0.735 * size, 0.28 * size),
                           (0.735 * size, 0.72 * size),
                           (0.405 * size, 0.50 * size)])]
    elif kind == "next":
        w = 0.065 * size
        parts = [("rect", (0.66 * size, 0.28 * size,
                           0.66 * size + w, 0.72 * size)),
                 ("poly", [(0.265 * size, 0.28 * size),
                           (0.265 * size, 0.72 * size),
                           (0.595 * size, 0.50 * size)])]
    else:
        return []

    # уменьшаем сам значок (~82%), не трогая размер круглой кнопки
    factor = 0.82
    offset = size * (1.0 - factor) / 2.0

    def shrink(data):
        if isinstance(data, list):
            return [(offset + x * factor, offset + y * factor)
                    for x, y in data]
        return tuple(offset + value * factor for value in data)

    return [(shape, shrink(data)) for shape, data in parts]


def _draw_icon_pil(draw, kind, size, color):
    for shape, data in _icon_parts(kind, size):
        if shape == "poly":
            draw.polygon([(int(x), int(y)) for x, y in data], fill=color)
        else:
            x1, y1, x2, y2 = data
            draw.rectangle([int(x1), int(y1), int(x2), int(y2)], fill=color)


def _draw_icon_canvas(cv, kind, size, color):
    for shape, data in _icon_parts(kind, size):
        if shape == "poly":
            cv.create_polygon(*[c for xy in data for c in xy], fill=color, outline="")
        else:
            cv.create_rectangle(*data, fill=color, outline="")

class RoundedButton(tk.Canvas):
    """Кнопка с умеренным скруглением углов (радиус ~6 px)."""

    def __init__(self, parent, text, command, font, bg=None, radius=None,
                 padx=None, pady=None, fixed_width=None, fixed_height=None):
        self.text = text
        self.command = command
        bg = bg or BG
        self.bgc = bg
        self.radius = radius if radius is not None else S(6)
        self.padx = padx if padx is not None else S(13)
        self.pady = pady if pady is not None else S(5)
        self.fixed_width = fixed_width
        width = (fixed_width if fixed_width is not None
                 else font.measure(text) + 2 * self.padx)
        height = (fixed_height if fixed_height is not None
                  else font.metrics("linespace") + 2 * self.pady)
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2",
                         takefocus=1)
        self.font = font
        self._state = "normal"
        self._focus = False
        self._inside = False
        self._img = None
        self.active = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)
        self._draw()

    def _price(self):
        if self.active:
            base = ACCENT
            hover = mix(ACCENT, "#ffffff", 0.14)
            down = mix(ACCENT, "#000000", 0.14)
            return {"normal": base, "hover": hover,
                    "pressed": down}.get(self._state, base)
        return {"normal": BTN, "hover": BTN_HOVER,
                "pressed": BTN_DOWN}.get(self._state, BTN)

    def _draw(self):
        self.delete("all")
        self._img = None
        w = int(self.cget("width"))
        h = int(self.cget("height"))
        fill = self._price()
        if HAS_PIL:
            img = smooth_image(w, h, fill, self.bgc, radius=self.radius)
            if img is not None:
                self._img = img
                self.create_image(0, 0, image=img, anchor="nw")
        if self._img is None:
            self.create_rectangle(0, 0, w - 1, h - 1, fill=fill, outline="")
        if self._focus:
            self.create_rectangle(S(2), S(2), w - S(2) - 1, h - S(2) - 1,
                                  outline=ACCENT, width=max(1, S(1)))
        if self.active:
            text_color = contrast_text(ACCENT)
        elif self._state in ("hover", "pressed"):
            text_color = TEXT
        else:
            text_color = MUTED
        self.create_text(w / 2.0, h / 2.0 - S(1), text=self.text,
                         fill=text_color, font=self.font,
                         anchor="center", justify="center")

    def set_active(self, active):
        self.active = bool(active)
        self._draw()

    def set_text(self, text):
        text = str(text)
        if text == self.text:
            return
        self.text = text
        width = (self.fixed_width if self.fixed_width is not None
                 else self.font.measure(text) + 2 * self.padx)
        self.config(width=width)
        self._draw()

    def refresh(self):
        self._draw()

    def _on_enter(self, _e):
        self._inside = True
        self._state = "hover"
        self._draw()

    def _on_leave(self, _e):
        self._inside = False
        self._state = "normal"
        self._draw()

    def _on_press(self, _e):
        self._state = "pressed"
        self._draw()

    def _on_release(self, e):
        inside = 0 <= e.x < int(self.cget("width")) and \
            0 <= e.y < int(self.cget("height"))
        self._state = "hover" if inside else "normal"
        self._draw()
        if inside and self.command:
            self.command()

    def _on_focus_in(self, _e):
        self._focus = True
        self._draw()

    def _on_focus_out(self, _e):
        self._focus = False
        self._draw()

    def _activate(self, _e=None):
        if self.command:
            self.command()
        return "break"


class IconButton(tk.Canvas):
    """Круглая кнопка: normal / hover / pressed / focus / disabled."""

    def __init__(self, parent, kind, command, size=None, filled=False,
                 accent=None, bg=None):
        size = size or S(62)
        accent = accent or ACCENT
        bg = bg or BG
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2",
                         takefocus=1)
        self.kind = kind
        self.command = command
        self.size = size
        self.filled = filled
        self.accent = accent
        self.bgc = bg
        self.enabled = True
        self._cache = {}
        self._photo = None
        self._state = "normal"
        self._inside = False
        self._focus = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)
        self._render("normal")

    def _colors(self, state):
        if not self.enabled:
            if self.filled:
                return mix(self.accent, BG, 0.65), MUTED
            return mix(BTN, BG, 0.45), MUTED
        if self.filled:
            base = self.accent
            hover = mix(self.accent, "#ffffff", 0.16)
            down = mix(self.accent, "#000000", 0.14)
            icon = contrast_text(self.accent)
        else:
            base, hover, down = BTN, BTN_HOVER, BTN_DOWN
            icon = TEXT
        fill = {"normal": base, "hover": hover, "pressed": down}.get(state, base)
        return fill, icon

    def _render(self, state):
        self._state = state
        fill, icon = self._colors(state)
        key = (state, fill, icon, self.kind, self.enabled)
        self.delete("all")

        img = self._cache.get(key)
        if img is None:
            img = self._make_image(fill, icon)
            if img is not None:
                self._cache[key] = img

        if img is not None:
            self._photo = img
            self.create_image(0, 0, image=img, anchor="nw")
        else:
            s = self.size
            self.create_oval(0, 0, s - 1, s - 1, fill=fill, outline="")
            _draw_icon_canvas(self, self.kind, s, icon)

        if self._focus:
            if not self.enabled:
                ring = "#4a4c52"
            elif self.filled:
                ring = "#ffffff"
            else:
                ring = self.accent
            r = S(3)
            self.create_oval(r, r, self.size - 1 - r, self.size - 1 - r,
                             outline=ring, width=max(1, S(2)))

    def _make_image(self, fill, icon):
        if not HAS_PIL:
            return None
        scale = ICON_SS
        big = self.size * scale
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([0, 0, big - 1, big - 1], fill=fill)
        _draw_icon_pil(d, self.kind, big, icon)
        img = img.resize((self.size, self.size), Image.LANCZOS)
        base = Image.new("RGB", (self.size, self.size), self.bgc)
        base.paste(img, (0, 0), img)
        return ImageTk.PhotoImage(base)

    def _on_enter(self, _e):
        self._inside = True
        if self.enabled:
            self._render("hover")

    def _on_leave(self, _e):
        self._inside = False
        self._render("normal")

    def _on_press(self, _e):
        if self.enabled:
            self._render("pressed")

    def _on_release(self, e):
        if not self.enabled:
            return
        inside = 0 <= e.x < self.size and 0 <= e.y < self.size
        self._render("hover" if inside else "normal")
        if inside and self.command:
            self.command()

    def _on_focus_in(self, _e):
        self._focus = True
        self._render(self._state)

    def _on_focus_out(self, _e):
        self._focus = False
        self._render(self._state)

    def _activate(self, _e=None):
        if self.enabled and self.command:
            self.command()
        return "break"

    def set_kind(self, kind):
        if kind == self.kind:
            return
        self.kind = kind
        self._cache.clear()
        self._render("hover" if self._inside else "normal")

    def set_accent(self, accent):
        self.accent = accent
        self._cache.clear()
        self._render(self._state)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        self.config(cursor="hand2" if enabled else "arrow")
        self._render(self._state)


class SearchIcon(tk.Canvas):
    """Векторная иконка лупы (увеличительное стекло)."""

    def __init__(self, parent, size=None, color=None, bg=None):
        size = size or S(18)
        color = color or MUTED
        bg = bg or BTN
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self.size = size
        self.color = color
        self.bgc = bg
        self._img = None
        self._draw()

    def _draw(self):
        self.delete("all")
        self._img = None
        s = self.size
        if HAS_PIL:
            big = s * ICON_SS
            img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            r = int(0.31 * big)
            lw = max(2, int(0.085 * big))
            cx = cy = int(0.07 * big) + r
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=self.color, width=lw)
            d.line([(cx + int(r * 0.70), cy + int(r * 0.70)),
                    (int(0.93 * big), int(0.93 * big))],
                   fill=self.color, width=lw)
            img = img.resize((s, s), Image.LANCZOS)
            base = Image.new("RGB", (s, s), self.bgc)
            base.paste(img, (0, 0), img)
            self._img = ImageTk.PhotoImage(base)
            self.create_image(0, 0, image=self._img, anchor="nw")
        else:
            lw = max(1, S(2))
            self.create_oval(s * 0.14, s * 0.14, s * 0.66, s * 0.66,
                             outline=self.color, width=lw)
            self.create_line(s * 0.60, s * 0.60, s * 0.92, s * 0.92,
                             fill=self.color, width=lw)


class ClearIcon(tk.Canvas):
    """Крестик очистки поиска; место под него зарезервировано всегда."""

    def __init__(self, parent, size=None, color=None, bg=None):
        size = size or S(16)
        color = color or MUTED
        bg = bg or BTN
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.size = size
        self.color = color
        self.bgc = bg
        self.visible = False
        self._hover = False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def _set_hover(self, hover):
        self._hover = bool(hover)
        self._draw()

    def set_visible(self, visible):
        visible = bool(visible)
        if visible != self.visible:
            self.visible = visible
            self._draw()

    def _draw(self):
        self.delete("all")
        if not self.visible:
            return
        s = self.size
        color = TEXT if self._hover else self.color
        lw = max(1, S(2))
        pad = 0.28 * s
        self.create_line(pad, pad, s - pad, s - pad,
                         fill=color, width=lw, capstyle="round")
        self.create_line(pad, s - pad, s - pad, pad,
                         fill=color, width=lw, capstyle="round")


class ScrollJumpIcon(tk.Canvas):
    """Компактная кнопка-стрелка «в начало / в конец» рядом с поиском."""

    def __init__(self, parent, size=None, color=None, bg=None,
                 button_width=None):
        size = size or S(24)
        width = button_width if button_width is not None else size
        color = color or MUTED
        bg = bg or BG
        super().__init__(parent, width=width, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.size = size
        self.width = width
        self.color = color
        self.bgc = bg
        self.accent = ACCENT
        self.direction = "down"
        self.active = False
        self._hover = False
        self._img = None
        self._draw()

    def set_direction(self, direction):
        direction = "up" if direction == "up" else "down"
        if direction != self.direction:
            self.direction = direction
            self._draw()

    def set_hover(self, hover):
        hover = bool(hover)
        if hover != self._hover:
            self._hover = hover
            self._draw()

    def _draw(self):
        self.delete("all")
        self._img = None
        w = self.width
        h = self.size
        color = TEXT if self._hover else self.color
        fill = BTN_HOVER if self._hover else BTN
        if HAS_PIL:
            bigw, bigh = w * ICON_SS, h * ICON_SS
            base = Image.new("RGB", (bigw, bigh), self.bgc)
            d = ImageDraw.Draw(base)
            d.rounded_rectangle([0, 0, bigw - 1, bigh - 1],
                                radius=int(0.22 * bigh), fill=fill)
            lw = max(2, int(0.075 * bigh))
            cx = bigw / 2.0
            off = 0.22 * bigh
            if self.direction == "up":
                d.line([(cx, 0.72 * bigh), (cx, 0.28 * bigh)],
                       fill=color, width=lw)
                d.line([(cx - off, 0.50 * bigh), (cx, 0.28 * bigh),
                        (cx + off, 0.50 * bigh)], fill=color, width=lw,
                       joint="curve")
            else:
                d.line([(cx, 0.28 * bigh), (cx, 0.72 * bigh)],
                       fill=color, width=lw)
                d.line([(cx - off, 0.50 * bigh), (cx, 0.72 * bigh),
                        (cx + off, 0.50 * bigh)], fill=color, width=lw,
                       joint="curve")
            base = base.resize((w, h), Image.LANCZOS)
            self._img = ImageTk.PhotoImage(base)
            self.create_image(0, 0, image=self._img, anchor="nw")
        else:
            lw = max(1, S(2))
            self.create_rectangle(0, 0, w - 1, h - 1, fill=fill, outline="")
            cx = w / 2.0
            off = h * 0.22
            if self.direction == "up":
                self.create_line(cx, h * 0.72, cx, h * 0.28,
                                 fill=color, width=lw)
                self.create_line(cx - off, h * 0.50, cx, h * 0.28,
                                 cx + off, h * 0.50, fill=color, width=lw)
            else:
                self.create_line(cx, h * 0.28, cx, h * 0.72,
                                 fill=color, width=lw)
                self.create_line(cx - off, h * 0.50, cx, h * 0.72,
                                 cx + off, h * 0.50, fill=color, width=lw)


class HistoryIcon(tk.Canvas):
    """Кнопка истории: компактные часы в том же стиле, что и стрелка."""

    def __init__(self, parent, size=None, color=None, bg=None,
                 button_width=None):
        size = size or S(24)
        width = button_width if button_width is not None else size
        color = color or MUTED
        bg = bg or BG
        super().__init__(parent, width=width, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.size = size
        self.width = width
        self.color = color
        self.bgc = bg
        self.accent = ACCENT
        self.active = False
        self._hover = False
        self._img = None
        self._draw()

    def set_hover(self, hover):
        hover = bool(hover)
        if hover != self._hover:
            self._hover = hover
            self._draw()

    def set_active(self, active):
        active = bool(active)
        if active != self.active:
            self.active = active
            self._draw()

    def _draw(self):
        self.delete("all")
        self._img = None
        w = self.width
        h = self.size
        color = (self.accent if self.active else
                 (TEXT if self._hover else self.color))
        fill = (mix(self.accent, BTN, 0.55) if self.active else
                (BTN_HOVER if self._hover else BTN))
        if HAS_PIL:
            bigw, bigh = w * ICON_SS, h * ICON_SS
            base = Image.new("RGB", (bigw, bigh), self.bgc)
            d = ImageDraw.Draw(base)
            d.rounded_rectangle([0, 0, bigw - 1, bigh - 1],
                                radius=int(0.22 * bigh), fill=fill)
            lw = max(2, int(0.075 * bigh))
            cx, cy = bigw / 2.0, bigh / 2.0
            rr = 0.28 * bigh
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      outline=color, width=lw)
            d.line([(cx, cy), (cx, cy - 0.19 * bigh)],
                   fill=color, width=lw)
            d.line([(cx, cy), (cx + 0.14 * bigh, cy + 0.06 * bigh)],
                   fill=color, width=lw)
            base = base.resize((w, h), Image.LANCZOS)
            self._img = ImageTk.PhotoImage(base)
            self.create_image(0, 0, image=self._img, anchor="nw")
        else:
            lw = max(1, S(2))
            self.create_rectangle(0, 0, w - 1, h - 1, fill=fill, outline="")
            cx, cy = w / 2.0, h / 2.0
            rr = h * 0.28
            self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                             outline=color, width=lw)
            self.create_line(cx, cy, cx, cy - h * 0.19,
                             fill=color, width=lw)
            self.create_line(cx, cy, cx + h * 0.14, cy + h * 0.06,
                             fill=color, width=lw)


class RepeatIcon(tk.Canvas):
    """Интерактивная иконка повтора (зацикленная стрелка)."""

    def __init__(self, parent, size=None, color=None, bg=None, active=False):
        size = size or S(18)
        color = color or MUTED
        bg = bg or BG
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.size = size
        self.color = color
        self.bgc = bg
        self.accent = ACCENT
        self.active = bool(active)
        self._hover = False
        self._img = None
        self._draw()

    def set_active(self, active):
        self.active = bool(active)
        self._draw()

    def set_hover(self, hover):
        self._hover = bool(hover)
        self._draw()

    def _draw(self):
        self.delete("all")
        self._img = None
        s = self.size
        if self.active:
            color = mix(self.accent, "#ffffff", 0.20 if self._hover else 0.0)
        elif self._hover:
            color = TEXT
        else:
            color = self.color
        if HAS_PIL:
            big = s * ICON_SS
            img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            lw = max(2, int(0.085 * big))
            d.arc([int(0.14 * big), int(0.20 * big),
                   int(0.86 * big), int(0.80 * big)],
                  start=200, end=340, fill=color, width=lw)
            d.arc([int(0.14 * big), int(0.20 * big),
                   int(0.86 * big), int(0.80 * big)],
                  start=20, end=160, fill=color, width=lw)
            # наконечники
            d.polygon([(int(0.82 * big), int(0.30 * big)),
                       (int(0.94 * big), int(0.38 * big)),
                       (int(0.80 * big), int(0.44 * big))], fill=color)
            d.polygon([(int(0.18 * big), int(0.70 * big)),
                       (int(0.06 * big), int(0.62 * big)),
                       (int(0.20 * big), int(0.56 * big))], fill=color)
            img = img.resize((s, s), Image.LANCZOS)
            base = Image.new("RGB", (s, s), self.bgc)
            base.paste(img, (0, 0), img)
            self._img = ImageTk.PhotoImage(base)
            self.create_image(0, 0, image=self._img, anchor="nw")
        else:
            lw = max(1, S(2))
            self.create_arc(0.14 * s, 0.20 * s, 0.86 * s, 0.80 * s,
                            start=200, extent=140, style="arc",
                            outline=color, width=lw)
            self.create_arc(0.14 * s, 0.20 * s, 0.86 * s, 0.80 * s,
                            start=20, extent=140, style="arc",
                            outline=color, width=lw)


class SpeakerIcon(tk.Canvas):
    """Интерактивная иконка динамика: волны / перечёркнутый при Mute."""

    def __init__(self, parent, size=None, color=None, bg=None, muted=False):
        size = size or S(18)
        color = color or MUTED
        bg = bg or BG
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.size = size
        self.color = color
        self.hover_color = TEXT
        self.bgc = bg
        self.muted = bool(muted)
        self._hover = False
        self._img = None
        self._draw()

    def set_muted(self, muted):
        muted = bool(muted)
        if muted != self.muted:
            self.muted = muted
            self._draw()

    def set_hover(self, hover):
        self._hover = bool(hover)
        self._draw()

    def _draw(self):
        self.delete("all")
        self._img = None
        s = self.size
        color = self.hover_color if self._hover else self.color
        if HAS_PIL:
            big = s * ICON_SS
            img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.polygon([(int(0.08 * big), int(0.40 * big)),
                       (int(0.28 * big), int(0.40 * big)),
                       (int(0.46 * big), int(0.22 * big)),
                       (int(0.46 * big), int(0.78 * big)),
                       (int(0.28 * big), int(0.60 * big)),
                       (int(0.08 * big), int(0.60 * big))], fill=color)
            lw = max(2, int(0.075 * big))
            if self.muted:
                # крест вместо звуковых волн
                x1, y1 = int(0.58 * big), int(0.34 * big)
                x2, y2 = int(0.94 * big), int(0.70 * big)
                d.line([(x1, y1), (x2, y2)], fill=color, width=lw)
                d.line([(x1, y2), (x2, y1)], fill=color, width=lw)
            else:
                d.arc([int(0.50 * big), int(0.32 * big),
                       int(0.76 * big), int(0.68 * big)],
                      start=-55, end=55, fill=color, width=lw)
                d.arc([int(0.56 * big), int(0.20 * big),
                       int(0.95 * big), int(0.80 * big)],
                      start=-55, end=55, fill=color, width=lw)
            img = img.resize((s, s), Image.LANCZOS)
            base = Image.new("RGB", (s, s), self.bgc)
            base.paste(img, (0, 0), img)
            self._img = ImageTk.PhotoImage(base)
            self.create_image(0, 0, image=self._img, anchor="nw")
        else:
            lw = max(1, S(2))
            self.create_polygon(0.08 * s, 0.40 * s, 0.28 * s, 0.40 * s,
                                0.46 * s, 0.22 * s, 0.46 * s, 0.78 * s,
                                0.28 * s, 0.60 * s, 0.08 * s, 0.60 * s,
                                fill=color, outline="")
            if self.muted:
                self.create_line(0.58 * s, 0.34 * s, 0.94 * s, 0.70 * s,
                                 fill=color, width=lw)
                self.create_line(0.58 * s, 0.70 * s, 0.94 * s, 0.34 * s,
                                 fill=color, width=lw)
            else:
                self.create_arc(0.50 * s, 0.32 * s, 0.76 * s, 0.68 * s,
                                start=-55, extent=110, style="arc",
                                outline=color, width=lw)
                self.create_arc(0.56 * s, 0.20 * s, 0.95 * s, 0.80 * s,
                                start=-55, extent=110, style="arc",
                                outline=color, width=lw)



class SlimScrollbar(tk.Canvas):
    """Тонкий скроллбар без стрелок и системного фона."""

    def __init__(self, parent, width=None, bg=None, thumb=None,
                 thumb_hover=None, thumb_drag=None, thumb_pad=None,
                 inset=None):
        width = width or S(8)
        bg = bg or CARD
        thumb = thumb or mix(TEXT, CARD, 0.42)
        thumb_hover = thumb_hover or mix(TEXT, CARD, 0.22)
        thumb_drag = thumb_drag or mix(TEXT, CARD, 0.10)
        self.thumb_pad = S(5) if thumb_pad is None else thumb_pad
        self.inset = 0 if inset is None else inset
        super().__init__(parent, width=width, bg=bg, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.w = width
        self.bgc = bg
        self.thumb_color = thumb
        self.thumb_hover = thumb_hover
        self.thumb_drag = thumb_drag
        self.first = 0.0
        self.last = 1.0
        self.dragging = False
        self._hover = False
        self._cmd = None
        self._img = None
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)

    def configure_commands(self, setter, mover):
        self._cmd = (setter, mover)

    def set(self, first, last):
        try:
            self.first = float(first)
            self.last = float(last)
        except (TypeError, ValueError):
            self.first, self.last = 0.0, 1.0
        self._redraw()

    def _thumb_box(self):
        h = max(1, self.winfo_height())
        span = max(0.0, self.last - self.first)
        if span >= 0.999:
            return None
        pad = min(float(self.thumb_pad), h / 2.0)
        track = max(1.0, h - 2.0 * pad)
        th = min(track, max(float(S(28)), track * span))
        y = pad + (track - th) * (self.first / max(1e-9, 1.0 - span))
        y = max(pad, min(y, h - pad - th))
        return y, y + th

    def _redraw(self):
        self.delete("all")
        self._img = None
        box = self._thumb_box()
        if not box:
            return
        y1, y2 = box
        if self.dragging:
            color = self.thumb_drag
        elif self._hover:
            color = self.thumb_hover
        else:
            color = self.thumb_color
        x1 = self.inset
        x2 = max(x1 + 1, self.w - self.inset)
        tw = x2 - x1
        if HAS_PIL:
            img = smooth_image(max(1, tw), y2 - y1, color, self.bgc,
                               radius=tw / 2.0)
            if img is not None:
                self._img = img
                self.create_image(x1, y1, image=img, anchor="nw")
                return
        r = tw / 2.0
        self.create_oval(x1, y1, x2, y1 + tw, fill=color, outline="")
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline="")
        self.create_oval(x1, y2 - tw, x2, y2, fill=color, outline="")

    def _enter(self, _e):
        self._hover = True
        self._redraw()

    def _leave(self, _e):
        self._hover = False
        if not self.dragging:
            self._redraw()

    def _target(self, y):
        h = max(1, self.winfo_height())
        pad = min(float(self.thumb_pad), h / 2.0)
        track = max(1.0, h - 2.0 * pad)
        box = self._thumb_box()
        th = (box[1] - box[0]) if box else track
        free = max(1.0, track - th)
        return max(0.0, min(1.0, (y - pad - th / 2.0) / free))

    def _press(self, e):
        self.dragging = True
        self._jump(e.y)

    def _drag(self, e):
        if self.dragging:
            self._jump(e.y)

    def _release(self, _e):
        self.dragging = False
        self._redraw()

    def _jump(self, y):
        if not self._cmd:
            return
        self._cmd[1](self._target(y))
        self._redraw()

class StreamPlayer:
    """Потоковый движок: ffmpeg (atempo) + PortAudio.

    Даёт реальное изменение скорости 0.5–2.0× с сохранением высоты тона,
    без загрузки часового файла в память.
    """

    RATE = 44100
    CHANNELS = 2

    def __init__(self):
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._proc = None
        self._stream = None
        self._reader = None
        self._eof = False
        self._done = False
        self._frames = 0
        self._start_pos = 0.0
        self._speed = 1.0
        self._path = None
        self._state = "stopped"      # playing | paused | stopped
        self._generation = 0
        self._local_frames = 0
        self._fade_frames = int(self.RATE * 0.045)
        self._pause_fade_total = 0
        self._pause_fade_remaining = 0
        self._pause_silent = False
        self.volume = VOLUME
        self.mute = MUTE_STATE
        self.error = None

    @property
    def available(self):
        return bool(HAS_STREAM)

    @property
    def playing(self):
        return self._state == "playing"

    @property
    def paused(self):
        return self._state == "paused"

    @property
    def done(self):
        return self._done and self._state == "playing"

    @property
    def path(self):
        return self._path

    def position(self):
        if self._state == "playing":
            return self._start_pos + (self._frames / float(self.RATE)) * self._speed
        return self._start_pos

    def load(self, path, position=0.0, speed=1.0):
        if self._state == "playing":
            self._begin_fade_out()
            time.sleep(0.02)
        self._stop_engine()
        if not ensure_stream_modules():
            self.error = "sounddevice/ffmpeg не установлены"
            return False
        self._path = os.path.abspath(path)
        self._start_pos = max(0.0, float(position))
        self._speed = max(SPEED_MIN, min(SPEED_MAX, float(speed)))
        self._frames = 0
        self._local_frames = 0
        self._pause_fade_total = 0
        self._pause_fade_remaining = 0
        self._pause_silent = False
        self._eof = False
        self._done = False
        self._generation += 1
        gen = self._generation
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                exe, "-hide_banner", "-loglevel", "error", "-nostdin",
                "-ss", "%.3f" % self._start_pos,
                "-i", self._path,
                "-af", "atempo=%.4f" % self._speed,
                "-f", "s16le", "-ac", str(self.CHANNELS),
                "-ar", str(self.RATE), "pipe:1",
            ]
            flags = 0x08000000 if sys.platform == "win32" else 0
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, creationflags=flags)
            self._reader = threading.Thread(
                target=self._read_loop, args=(self._proc, gen), daemon=True)
            self._reader.start()
            self._stream = sd.OutputStream(
                samplerate=self.RATE, channels=self.CHANNELS,
                dtype="int16", blocksize=0, callback=self._callback)
            self._stream.start()
            self._state = "playing"
            return True
        except Exception as exc:
            self.error = str(exc)
            debug_log("StreamPlayer.load error: %r" % (exc,))
            self._stop_engine()
            self._state = "stopped"
            return False

    def _read_loop(self, proc, gen):
        try:
            while gen == self._generation:
                data = proc.stdout.read(16384)
                if not data:
                    break
                with self._lock:
                    self._buf.extend(data)
                # не держим в памяти больше ~3 секунд аудио
                while (gen == self._generation
                       and len(self._buf) > self.RATE * 4 * 3):
                    time.sleep(0.02)
        except Exception:
            pass
        finally:
            if gen == self._generation:
                self._eof = True

    def _callback(self, outdata, frames, _time_info, _status):
        try:
            need = frames * self.CHANNELS * 2
            with self._lock:
                chunk = bytes(self._buf[:need])
                if chunk:
                    del self._buf[:len(chunk)]
            n = len(chunk) // (self.CHANNELS * 2)
            if n:
                arr = np.frombuffer(chunk, dtype=np.int16).reshape(-1, self.CHANNELS)
                gain = 0.0 if self.mute else float(self.volume)
                if self._fade_frames > 0:
                    gain *= min(1.0, self._local_frames / float(self._fade_frames))
                if self._state == "paused":
                    if self._pause_silent:
                        gain = 0.0
                    elif self._pause_fade_remaining > 0:
                        gain *= (self._pause_fade_remaining /
                                 float(max(1, self._pause_fade_total)))
                        self._pause_fade_remaining -= n
                        if self._pause_fade_remaining <= 0:
                            self._pause_silent = True
                if gain <= 0.0:
                    outdata[:n] = 0
                elif gain >= 0.999:
                    outdata[:n] = arr
                else:
                    outdata[:n] = (arr.astype(np.float32) * gain).astype(np.int16)
                self._frames += n
                self._local_frames += n
            if n < frames:
                outdata[n:] = 0
                if self._eof:
                    self._done = True
        except Exception:
            try:
                outdata.fill(0)
            except Exception:
                pass

    def _begin_fade_out(self):
        if self._state != "playing":
            return
        self._start_pos = self.position()
        self._state = "paused"
        self._pause_fade_total = max(1, int(self.RATE * 0.02))
        self._pause_fade_remaining = self._pause_fade_total
        self._pause_silent = False

    def pause(self):
        self._begin_fade_out()

    def finish_pause(self):
        """Закрывает поток после короткого fade-out, не блокируя интерфейс."""
        if self._state == "paused":
            self._stop_engine(wait=False)

    def resume(self):
        if not self._path:
            return False
        was = self._state
        pos = self.position() if was == "playing" else self._start_pos
        return self.load(self._path, pos, self._speed)

    def seek(self, position):
        position = max(0.0, float(position))
        was = self._state
        if was == "playing":
            self._begin_fade_out()
            # даём аудиопотоку 20 мс на затухание, чтобы не было щелчка
            time.sleep(0.025)
            return self.load(self._path, position, self._speed)
        self._stop_engine()
        self._start_pos = position
        self._state = was
        return True

    def set_position(self, position):
        if self._state == "playing":
            return self.seek(position)
        self._start_pos = max(0.0, float(position))
        return True

    def set_speed(self, speed):
        speed = max(SPEED_MIN, min(SPEED_MAX, float(speed)))
        was = self._state
        pos = self.position()
        self._stop_engine()
        self._speed = speed
        self._start_pos = pos
        if was == "playing":
            return self.load(self._path, pos, speed)
        self._state = was
        return True

    def stop(self):
        self._stop_engine()
        self._state = "stopped"
        self._start_pos = 0.0
        self._path = None

    def _stop_engine(self, wait=True):
        self._generation += 1
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
            if wait:
                try:
                    proc.wait(timeout=0.4)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        with self._lock:
            self._buf.clear()
        self._eof = False
        self._done = False
        self._frames = 0
        self._local_frames = 0
        self._pause_fade_total = 0
        self._pause_fade_remaining = 0
        self._pause_silent = False


class PlayerApp:
    def __init__(self, root, initial_files=None, external_files=None,
                 title=APP_NAME, is_main=None):
        self.root = root
        self.root.title(title or APP_NAME)
        self._win_w = S(1051)
        self._win_h = S(657)
        self.root.geometry("%dx%d" % (self._win_w, self._win_h))
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._is_main = (initial_files is None if is_main is None
                         else bool(is_main))
        self.accent = ACCENT
        self.volume = VOLUME
        self.mute = MUTE_STATE
        self._vol_ratio = self.volume
        self._inbox = queue.Queue()
        self._server = None
        self._ready = False
        self._engine_loaded = None
        self._suspended = False
        self._icon_hidden = False
        self._stream_player = StreamPlayer()
        self._stream_player.volume = self.volume
        self._stream_player.mute = self.mute
        debug_log("PlayerApp initial=%r external=%r" % (initial_files, external_files))

        # шрифты (единая типографика интерфейса)
        self._font_title = tkfont.Font(family="Segoe UI Semibold", size=13)
        self._font_sub = tkfont.Font(family="Segoe UI", size=10)
        self._font_time = tkfont.Font(family="Segoe UI", size=11)
        self._font_list = tkfont.Font(family="Segoe UI", size=11)
        self._font_ui = tkfont.Font(family="Segoe UI", size=10)
        self._font_button = tkfont.Font(family="Segoe UI", size=10,
                                        weight="bold")

        self.tracks = []
        self._folder_count = 0
        self.view = []
        self.index = -1
        self.current = None
        self.duration = 0.0
        self.position = 0.0
        self.start_time = 0.0
        self.state = "idle"          # idle | playing | paused
        self.repeat = REPEAT
        self.folder = None
        self.seeking = False
        self._seek_pos = 0.0
        self._seek_dragged = False
        self._missing = set()        # индексы недоступных файлов
        self.mode = "main"           # оставлено для совместимости
        self._main_loaded = False    # основной плейлист загружен
        self._note_job = None
        self._vinyl_angle = 0.0
        self._vinyl_glint = None
        self._vinyl_dot = None
        self._vinyl_base = None
        self._vinyl_item = None
        self._vinyl_photo = None
        self._vinyl_d = 0
        self._vinyl_active = False
        self._vinyl_last_time = 0.0
        self._vinyl_dir = 1.0
        self._vinyl_rate = 95.0
        self._vinyl_target_rate = 95.0
        self._vinyl_return_job = None
        self._vinyl_forced_until = 0.0
        self._last_time_text = ""
        self._closing = False
        self._closed = False
        self.history = []           # только текущий сеанс: path + count
        self._history_panel = None
        self._history_canvas = None
        self._history_scroll = None
        self._history_anim_job = None
        self._history_hover = -1
        self._history_card_normal = None
        self._history_card_hover = None
        self._history_row_h = S(44)
        self._history_open = False
        self._settings_panel = None
        self._settings_open = False
        self._settings_swatches = []
        self._settings_system_btn = None
        self._playlist_body = None
        self._mode_saves = {"external": {
            "tracks": [], "folder": None, "index": -1, "current": None,
            "duration": 0.0, "position": 0.0, "missing": set()}}

        self._title_full = "Выберите папку с музыкой"
        self._note_img = None
        self._toolbar_buttons = []
        self._settings_button = None
        self._img_cache = {}
        self._hover_row = -1
        self._pressed_row = -1
        self._active_row = -1
        self._selection_before_sep = []
        self._last_list_w = 0
        self._last_avail_check = 0.0
        self._last_theme_check = 0.0
        self._save_job = None
        self._elide_cache = {}
        self._elide_width = -1
        self._search_hits = []
        self._search_index = -1
        self._search_set = set()
        self._search_job = None
        self._scroll_job = None
        self._scroll_at_bottom = False
        self._bar_hover = False
        self._vol_hover = False
        self._ph_active = False
        self._bar_thumb_img = False
        self._vol_thumb_img = False
        self._bar_photo_key = None
        self._bar_thumb_d = S(16)
        self._vol_thumb_d = S(12)

        self._build_header()
        self._build_controls()
        self._build_progress()
        self._build_volume()
        self._build_playlist()
        self._bind_keys()

        WINDOWS.append(self)
        lock_window_size(self.root, self._win_w, self._win_h)
        apply_app_icon(self.root)
        hide_titlebar_icon(self.root)
        self.root.bind("<Map>", self._on_window_map, add="+")
        self.root.bind("<Unmap>", self._on_window_unmap, add="+")
        self.root.bind("<FocusIn>", self._on_window_focus, add="+")
        apply_windows_titlebar(self.root)

        self._update_transport()
        self._refresh_bar()
        self._tick()

        if initial_files:
            self.tracks = list(initial_files)
            self._folder_count = 0
            self.view = self._build_view()
            self._render_list()
            self._refresh_availability(force=True)
            self._set_title(display_title(self.tracks[0]))
            self._set_sub("Треков: %d" % len(self.tracks))
            self._update_transport()
            self.root.after(120, lambda: self._play_index(0))
        elif self._is_main:
            # главное окно восстанавливает ранее импортированный список
            self._restore_saved_tracks()
            self._restore_last_track()
        self._mode_saves["main"] = self._snapshot_mode()
        self._update_mode_button()
        self._setup_file_drop()
        self._ready = True

    # ===================== интерфейс ======================================
    def _thumb_image(self, d, color="#ffffff"):
        """Сглаженный кружок ползунка (кэшируется по диаметру и цвету)."""
        key = ("thumb", int(d), color)
        img = self._img_cache.get(key)
        if img is None:
            img = smooth_image(d, d, color, BG, radius=d / 2.0)
            if img is not None:
                self._img_cache[key] = img
        return img

    def _vinyl_base_image(self, d, rim, groove, label, glint):
        """Сглаженная пластинка в 4× разрешении для вращения без пикселей."""
        if not HAS_PIL:
            return None
        try:
            ss = max(4, SHAPE_SS)
            big = max(8, int(d) * ss)
            img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            c = big / 2.0
            r = max(4.0 * ss, c - S(2) * ss)
            draw.ellipse([ss, ss, big - ss, big - ss], fill="#0e0e10",
                         outline=rim, width=max(1, S(1)) * ss)
            for k in (0.82, 0.68, 0.54):
                rr = r * k
                draw.ellipse([c - rr, c - rr, c + rr, c + rr],
                             outline=groove, width=max(1, ss))
            lr = r * 0.30
            draw.ellipse([c - lr, c - lr, c + lr, c + lr], fill=label)
            hr = max(1.5 * ss, r * 0.055)
            draw.ellipse([c - hr, c - hr, c + hr, c + hr], fill=PANEL)
            gr = r * 0.88
            draw.arc([c - gr, c - gr, c + gr, c + gr], start=-48, end=0,
                     fill=glint, width=max(1, S(2)) * ss)
            dot_r = r * 0.13
            dr = 1.6 * ss
            draw.ellipse([c + dot_r - dr, c - dr,
                          c + dot_r + dr, c + dr], fill=glint)
            size = max(8, int(d) * 4)
            hi = img.resize((size, size), Image.LANCZOS)
            flat = Image.new("RGB", (size, size), PANEL)
            flat.paste(hi, (0, 0), hi)
            return flat
        except Exception:
            return None

    def _capsule_photo(self, width, height, pad, end, bg_color,
                       fill_color, show_fill=True):
        """Сглаженная капсула шкалы: без ступенек и пиксельных краёв."""
        if not HAS_PIL:
            return None
        width = int(width)
        height = int(height)
        if width <= 1 or height <= 1:
            return None
        try:
            ss = 4
            w = max(1, width)
            h = max(1, height)
            big = Image.new("RGB", (w * ss, h * ss), BG)
            draw = ImageDraw.Draw(big)
            radius = h * ss / 2.0

            def pill(x1, x2, color):
                left = int(round(x1 * ss - radius))
                right = int(round(x2 * ss + radius))
                if right - left < 2:
                    return
                rr = min(radius, (right - left) / 2.0)
                draw.rounded_rectangle(
                    [left, 0, right - 1, h * ss - 1],
                    radius=max(1, int(round(rr))), fill=color)

            pill(pad, w - pad, bg_color)
            if show_fill and end > pad + 0.5:
                pill(pad, end, fill_color)
            small = big.resize((w, h), Image.LANCZOS)
            return ImageTk.PhotoImage(small)
        except Exception:
            return None

    def _draw_note(self):
        """Рисует виниловую пластинку; вращается блик и метка."""
        d = S(44)
        c = d / 2.0
        r = max(4.0, c - S(2))
        self.note.delete("all")
        self._vinyl_glint = None
        self._vinyl_dot = None
        active = getattr(self, "state", "idle") in ("playing", "paused")
        self._vinyl_active = active
        rim = (mix(self.accent, "#3a3b3f", 0.58) if active
               else "#2a2b2e")
        groove = "#2c2d30" if active else "#242527"
        label = (mix(self.accent, PANEL, 0.45) if active
                 else mix(self.accent, PANEL, 0.80))
        glint = (mix(self.accent, "#ffffff", 0.28) if active
                 else TRACK_LINE)

        self._vinyl_d = d
        self._vinyl_item = None
        self._vinyl_photo = None
        self._vinyl_base = self._vinyl_base_image(d, rim, groove, label, glint)
        if self._vinyl_base is not None:
            self._draw_vinyl_dynamic()
            return

        # запасной вариант без Pillow: обычные векторные фигуры
        self.note.create_oval(1, 1, d - 1, d - 1, fill="#0e0e10",
                              outline=rim, width=max(1, S(1)))
        for k in (0.82, 0.68, 0.54):
            rr = r * k
            self.note.create_oval(c - rr, c - rr, c + rr, c + rr,
                                  outline=groove, width=1)
        lr = r * 0.30
        self.note.create_oval(c - lr, c - lr, c + lr, c + lr,
                              fill=label, outline="")
        hr = max(1.5, r * 0.055)
        self.note.create_oval(c - hr, c - hr, c + hr, c + hr,
                              fill=PANEL, outline="")
        self._vinyl_center = (c, r, r * 0.13)
        self._vinyl_glint_color = glint
        self._draw_vinyl_dynamic()

    def _draw_vinyl_dynamic(self):
        """Обновляет повёрнутую пластинку без оставшихся пикселей."""
        base = getattr(self, "_vinyl_base", None)
        if base is not None:
            angle = float(getattr(self, "_vinyl_angle", 0.0))
            try:
                img = base.rotate(-angle, resample=Image.BICUBIC,
                                  fillcolor=PANEL)
                d = max(8, int(getattr(self, "_vinyl_d", S(44))))
                img = img.resize((d, d), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                item = getattr(self, "_vinyl_item", None)
                if item is None:
                    self._vinyl_item = self.note.create_image(
                        0, 0, image=photo, anchor="nw")
                else:
                    self.note.itemconfig(item, image=photo)
                self._vinyl_photo = photo
            except Exception:
                pass
            return
        # запасной вариант без Pillow
        self.note.delete("vinyl_dyn")
        if not hasattr(self, "_vinyl_center"):
            return
        c, r, dot_r = self._vinyl_center
        angle = float(getattr(self, "_vinyl_angle", 0.0))
        gr = r * 0.88
        color = getattr(self, "_vinyl_glint_color", TRACK_LINE)
        self._vinyl_glint = self.note.create_arc(
            c - gr, c - gr, c + gr, c + gr, start=angle, extent=48,
            style="arc", outline=color, width=max(1, S(2)),
            tags=("vinyl_dyn",))
        rad = math.radians(angle)
        x = c + math.cos(rad) * dot_r
        y = c + math.sin(rad) * dot_r
        self._vinyl_dot = self.note.create_oval(
            x - 1.6, y - 1.6, x + 1.6, y + 1.6,
            fill=color, outline="", tags=("vinyl_dyn",))

    def _start_note_anim(self):
        """Вращение при воспроизведении или во время перемотки на паузе."""
        state = getattr(self, "state", None)
        forced = time.perf_counter() < getattr(self, "_vinyl_forced_until", 0.0)
        if state != "playing" and not (state == "paused" and forced):
            return
        if not hasattr(self, "note") or getattr(self, "_suspended", False):
            return
        if self._note_job is None:
            self._vinyl_last_time = time.perf_counter()
            self._note_job = self.root.after(33, self._note_tick)

    def _stop_note_anim(self):
        """Останавливает вращение, сохраняя текущий угол (пауза)."""
        if self._note_job is not None:
            try:
                self.root.after_cancel(self._note_job)
            except Exception:
                pass
            self._note_job = None
        self._vinyl_last_time = 0.0
        if self._vinyl_return_job is not None:
            try:
                self.root.after_cancel(self._vinyl_return_job)
            except Exception:
                pass
            self._vinyl_return_job = None
        self._vinyl_dir = 1.0
        self._vinyl_rate = 95.0
        self._vinyl_target_rate = 95.0
        self._vinyl_forced_until = 0.0

    def _vinyl_seek(self, delta, hold=0.45):
        """Задаёт направление/ускорение вращения при перемотке."""
        state = getattr(self, "state", None)
        if state not in ("playing", "paused"):
            return
        if abs(delta) < 0.05:
            return
        self._vinyl_dir = -1.0 if delta < 0 else 1.0
        self._vinyl_rate = max(self._vinyl_rate, 230.0)
        self._vinyl_target_rate = 230.0
        if state == "paused":
            self._vinyl_forced_until = max(
                self._vinyl_forced_until, time.perf_counter() + hold)
            self._start_note_anim()
            return
        if self._vinyl_return_job is not None:
            try:
                self.root.after_cancel(self._vinyl_return_job)
            except Exception:
                pass
        self._vinyl_return_job = self.root.after(
            int(hold * 1000), self._vinyl_return_normal)

    def _vinyl_return_normal(self):
        if self._vinyl_return_job is not None:
            try:
                self.root.after_cancel(self._vinyl_return_job)
            except Exception:
                pass
            self._vinyl_return_job = None
        self._vinyl_dir = 1.0
        self._vinyl_target_rate = 95.0

    def _note_tick(self):
        self._note_job = None
        now = time.perf_counter()
        state = getattr(self, "state", None)
        forced = now < getattr(self, "_vinyl_forced_until", 0.0)
        if state != "playing" and not forced:
            self._vinyl_dir = 1.0
            self._vinyl_rate = 95.0
            self._vinyl_target_rate = 95.0
            self._vinyl_last_time = 0.0
            return
        if getattr(self, "_suspended", False):
            return
        if not hasattr(self, "note"):
            return
        if (getattr(self, "_vinyl_base", None) is None
                and self._vinyl_glint is None):
            return
        last = self._vinyl_last_time or now
        dt = max(0.0, min(1.0, now - last))
        self._vinyl_last_time = now
        # угол зависит от реального времени, а не от частоты таймера
        self._vinyl_rate += ((self._vinyl_target_rate - self._vinyl_rate)
                             * min(1.0, dt * 6.0))
        self._vinyl_angle = (self._vinyl_angle
                             + self._vinyl_dir * self._vinyl_rate * dt) % 360.0
        try:
            self._draw_vinyl_dynamic()
        except Exception:
            return
        self._note_job = self.root.after(33, self._note_tick)

    def _build_header(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=S(18), pady=(S(16), 0))
        self._header_bg = tk.Canvas(head, bg=BG, highlightthickness=0, bd=0)
        self._header_bg.place(x=0, y=0, relwidth=1, relheight=1)
        self._header_bg.bind("<Configure>",
                             lambda e: self._draw_header_bg())

        inner = tk.Frame(head, bg=PANEL)
        inner.pack(fill="x", padx=S(16), pady=S(14))

        self.note = tk.Canvas(inner, width=S(44), height=S(44), bg=PANEL,
                              highlightthickness=0, bd=0)
        self.note.pack(side="left", padx=(0, S(14)))
        self._draw_note()

        time_box = tk.Frame(inner, bg=PANEL)
        time_box.pack(side="right")
        self.lbl_time = tk.Label(time_box, text="00:00 / 00:00", bg=PANEL,
                                 fg=MUTED, font=self._font_time)
        self.lbl_time.pack(anchor="e")

        self.title_box = tk.Frame(inner, bg=PANEL)
        self.title_box.pack(side="left", fill="both", expand=True)

        self.lbl_title = tk.Label(self.title_box, text=self._title_full, bg=PANEL,
                                  fg=TEXT, font=self._font_title, anchor="w",
                                  cursor="hand2")
        self.lbl_title.pack(fill="x")
        self.lbl_title.bind("<Button-1>", self._copy_current_title)

        self.lbl_sub = tk.Label(self.title_box, text="", bg=PANEL,
                                fg=MUTED, font=self._font_sub, anchor="w")
        self.lbl_sub.pack(fill="x", pady=(S(2), 0))

        self.title_box.bind("<Configure>", lambda e: self._refresh_title())
        self._draw_header_bg()

    def _refresh_title(self):
        maxw = self.title_box.winfo_width() - S(6)
        if maxw <= 1:
            maxw = S(520)
        self.lbl_title.config(text=elide(self._title_full, self._font_title, maxw))

    def _set_title(self, text):
        self._title_full = text
        self._refresh_title()
        self._update_taskbar_title()

    def _set_sub(self, text):
        self.lbl_sub.config(text=text)

    def _update_taskbar_title(self):
        """В панели задач и Alt+Tab видно, какой трек сейчас включён."""
        track = display_title(self.current) if self.current else ""
        title = "%s — %s" % (APP_NAME, track) if track else APP_NAME
        try:
            if self.root.title() != title:
                self.root.title(title)
        except Exception:
            pass

    def _copy_current_title(self, _event=None):
        """Клик по названию: копируем только имя трека, без расширения."""
        if not self.current:
            return "break"
        title = display_title(self.current)
        if not title:
            return "break"
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(title)
            self.root.update_idletasks()
        except Exception:
            return "break"
        self._notify("Название скопировано")
        return "break"

    def _notify(self, text, delay=1400):
        """Короткое уведомление в строке состояния."""
        try:
            old = self.lbl_sub.cget("text")
            self.lbl_sub.config(text=text)

            def restore():
                try:
                    if self.lbl_sub.cget("text") == text:
                        self.lbl_sub.config(text=old)
                except Exception:
                    pass

            self.root.after(delay, restore)
        except Exception:
            pass

    def _restore_saved_tracks(self):
        """Восстанавливает треки прошлого запуска — без диалогов и проводника."""
        folder_tracks = list(SAVED_FOLDER_TRACKS)
        added_tracks = list(SAVED_ADDED_TRACKS)
        if not folder_tracks and not added_tracks:
            folder_tracks = list(SAVED_TRACKS)
        files = folder_tracks + added_tracks
        if not files:
            return
        self._main_loaded = True
        self._folder_count = len(folder_tracks)
        self.tracks = files
        self.folder = SAVED_FOLDER
        self._missing = {i for i, path in enumerate(files)
                         if not os.path.isfile(path)}
        self._last_avail_check = time.time()
        self.view = self._build_view()
        self._render_list()
        base = self.folder or os.path.dirname(files[0])
        self._set_title(Path(base).name or "Плейлист")
        missing = len(self._missing)
        sub = "Треков: %d" % len(files)
        if missing:
            sub += " • недоступно: %d" % missing
        self._set_sub(sub)
        self._update_transport()

    def _remember_tracks(self):
        """Сохраняет основной список; временный список не записывается."""
        if not self._is_main or not self._main_loaded:
            return
        global SAVED_TRACKS, SAVED_FOLDER
        global SAVED_FOLDER_TRACKS, SAVED_ADDED_TRACKS
        count = max(0, min(self._folder_count, len(self.tracks)))
        SAVED_TRACKS = list(self.tracks)
        SAVED_FOLDER_TRACKS = list(self.tracks[:count])
        SAVED_ADDED_TRACKS = list(self.tracks[count:])
        SAVED_FOLDER = self.folder
        save_settings()

    def _remember_progress(self):
        """Запоминает трек и таймкод основного плейлиста."""
        if not self._is_main or not self._main_loaded:
            return
        global LAST_TRACK, LAST_POSITION, LAST_DURATION
        if self.current and os.path.isfile(self.current):
            pos = (self._live_position() if self.state == "playing"
                   else self.position)
            LAST_TRACK = self.current
            LAST_POSITION = max(0.0, float(pos))
            LAST_DURATION = max(0.0, float(self.duration))
        else:
            LAST_TRACK = None
            LAST_POSITION = 0.0
            LAST_DURATION = 0.0

    def _restore_last_track(self):
        """Восстанавливает трек и таймкод, но не запускает воспроизведение."""
        path = LAST_TRACK
        if not path:
            return
        if not os.path.isfile(path):
            self._set_sub("Прошлый трек недоступен")
            return
        if path not in self.tracks:
            self.tracks.append(path)
        self.view = self._build_view()
        self._reset_search()
        self._render_list()
        self._refresh_availability()
        self._main_loaded = True
        self.current = path
        self.index = self.tracks.index(path)
        self.duration = float(LAST_DURATION or 0.0)
        if self.duration <= 0:
            self.duration = DURATION_CACHE.get(os.path.abspath(path), 0.0)
        pos = max(0.0, float(LAST_POSITION or 0.0))
        if self.duration > 0:
            pos = min(pos, max(0.0, self.duration - 0.15))
        self.position = pos
        self.start_time = 0.0
        subtitle = ("Продолжить с %s" % self._fmt(pos)
                    if pos >= 1.0 else "Трек восстановлен")
        self._set_state("idle", subtitle)
        self._set_title(display_title(path))
        self._select_track(self.index, reveal=True)
        self._update_transport()
        self._refresh_bar()
        self._probe_duration(path)

    # ===================== основной / внешний плейлист ===================
    def _empty_mode_snapshot(self):
        return {"tracks": [], "folder": None, "index": -1, "current": None,
                "duration": 0.0, "position": 0.0, "missing": set()}

    def _snapshot_mode(self):
        pos = self.position
        if self.state == "playing":
            try:
                pos = self._live_position()
            except Exception:
                pos = self.position
        return {
            "tracks": self.tracks,
            "folder": self.folder,
            "index": self.index,
            "current": self.current,
            "duration": self.duration,
            "position": max(0.0, float(pos or 0.0)),
            "missing": set(self._missing),
        }

    def _mode_title(self):
        if self.folder:
            return Path(self.folder).name or "Плейлист"
        if self._main_loaded:
            return "Плейлист"
        if self.tracks:
            return "Добавленные треки"
        return "Добавьте треки"

    def _mode_sub(self):
        count = len(self.tracks)
        if not self._main_loaded and not self.folder:
            if not count:
                return "Добавить трек, перетаскивание или «Открыть с помощью»"
            return "Треков: %d • временный список" % count
        if not count:
            return "Выберите папку или добавьте трек"
        missing = sum(1 for p in self.tracks if not os.path.isfile(p))
        sub = "Треков: %d" % count
        if missing:
            sub += " • недоступно: %d" % missing
        return sub

    def _update_mode_header(self):
        if self.current and os.path.isfile(self.current):
            self._set_title(display_title(self.current))
            if self.state == "playing":
                self._set_sub("Играет")
            elif self.state == "paused":
                self._set_sub("Пауза")
            else:
                self._set_sub(self._mode_sub())
        else:
            self._set_title(self._mode_title())
            self._set_sub(self._mode_sub())

    def _update_mode_button(self):
        if not hasattr(self, "btn_mode"):
            return
        try:
            if self.mode == "external":
                self.btn_mode.set_text("Основной")
            else:
                count = len(self._mode_saves.get("external", {}).get("tracks") or [])
                self.btn_mode.set_text("Внешние" if count == 0
                                       else "Внешние · %d" % count)
        except Exception:
            pass

    def _toggle_mode(self):
        self._switch_mode("main" if self.mode == "external" else "external")

    def _switch_mode(self, mode, autoplay=None):
        """Переключает основной и временный внешний плейлисты."""
        if mode not in ("main", "external"):
            return
        if mode == self.mode:
            if autoplay is not None and 0 <= autoplay < len(self.tracks):
                self._play_index(autoplay)
            return
        if self.mode == "main":
            # состояние основного плейлиста всегда остаётся актуальным
            self._remember_progress()
        self._mode_saves[self.mode] = self._snapshot_mode()
        self._stop_mixer()
        self.mode = mode
        data = self._mode_saves.get(mode)
        if not isinstance(data, dict):
            data = self._empty_mode_snapshot()
            self._mode_saves[mode] = data
        self.tracks = data.get("tracks") or []
        data["tracks"] = self.tracks
        self.folder = data.get("folder")
        self.index = data.get("index", -1)
        self.current = data.get("current")
        self.duration = float(data.get("duration") or 0.0)
        self.position = float(data.get("position") or 0.0)
        self.start_time = 0.0
        self.seeking = False
        self._missing = set(data.get("missing") or ())
        self.view = list(range(len(self.tracks)))
        self._reset_search()
        self._render_list()
        self._refresh_availability()
        self._update_mode_button()
        self._update_transport()
        self._refresh_bar()
        if self.current and os.path.isfile(self.current):
            self._set_state("paused", "Пауза")
        else:
            if self.current and not os.path.isfile(self.current):
                self.current = None
                self.index = -1
                self.duration = 0.0
                self.position = 0.0
            self._set_state("idle")
        self._update_mode_header()
        if autoplay is not None and 0 <= autoplay < len(self.tracks):
            self._play_index(autoplay)

    def _setup_file_drop(self):
        if os.environ.get("ZHUMWAVE_NO_DROP") == "1":
            return
        try:
            enable_file_drop(self.root)
        except Exception:
            pass

    def _drain_drops(self):
        queue = getattr(self.root, "_drop_queue", None)
        while queue:
            try:
                files = queue.pop(0)
            except Exception:
                break
            if files:
                debug_log("drop files=%r" % (files,))
                self._add_external_files(files, play=True)

    def _on_files_dropped(self, files):
        debug_log("drop files=%r" % (files,))
        self._add_external_files(files, play=True)

    def _bring_to_front(self):
        if not getattr(self, "_ready", True):
            self.root.after(60, self._bring_to_front)
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def _open_external_files(self, files, play=True):
        """Единая точка добавления файлов из Проводника / «Открыть с помощью»."""
        self._add_external_files(files, play=play)

    def _add_external_files(self, files, play=True):
        """Добавляет файлы в текущий список; при загруженной папке — в основной."""
        debug_log("add files=%r play=%r" % (files, play))
        paths = [os.path.abspath(p) for p in files if os.path.isfile(p)]
        audio = [p for p in paths
                 if os.path.splitext(p)[1].lower() in (".mp3", ".mp4")]
        rejected = [p for p in paths if p not in audio]
        if rejected:
            names = "\n".join(os.path.basename(p) for p in rejected[:8])
            if len(rejected) > 8:
                names += "\n…"
            messagebox.showwarning(
                APP_NAME,
                "Поддерживаются аудиофайлы MP3 и MP4.\n\n"
                "Не добавлено:\n%s" % names)
        if not audio:
            self._bring_to_front()
            return

        first = -1
        for path in audio:
            if path in self.tracks:
                index = self.tracks.index(path)
            else:
                self.tracks.append(path)
                index = len(self.tracks) - 1
            if first < 0:
                first = index

        if self._query():
            self._filter_list()
        else:
            self._append_view_rows(self._build_view())
        self._update_transport()
        if play and first >= 0:
            self._play_index(first)
        else:
            self._update_mode_header()
        if self._main_loaded:
            self._remember_tracks()
        self._bring_to_front()

    def _drain_inbox(self):
        while True:
            try:
                payload = self._inbox.get_nowait()
            except queue.Empty:
                break
            if not isinstance(payload, dict):
                continue
            duration = payload.get("duration")
            if duration:
                try:
                    path, length = duration
                    self._apply_duration(path, length)
                except Exception:
                    pass
                continue
            files = payload.get("files") or []
            debug_log("inbox files=%r" % (files,))
            if files:
                self._open_external_files(files, play=True)
            else:
                self._bring_to_front()

    def _build_controls(self):
        row = tk.Frame(self.root, bg=BG)
        row.pack(pady=(S(16), 0))

        self.btn_prev = IconButton(row, "prev", self.prev_track, size=S(62),
                                   filled=False, accent=self.accent)
        self.btn_prev.pack(side="left", padx=S(10))

        self.btn_play = IconButton(row, "play", self.toggle, size=S(62),
                                   filled=True, accent=self.accent)
        self.btn_play.pack(side="left", padx=S(10))

        self.btn_next = IconButton(row, "next", self.next_track, size=S(62),
                                   filled=False, accent=self.accent)
        self.btn_next.pack(side="left", padx=S(10))

    def _build_progress(self):
        self._bar_h = S(26)
        self._bar_y1 = S(9)
        self._bar_y2 = S(17)
        self._bar_cy = self._bar_h // 2
        self._bar_pad = S(11)         # отступ под бегунок, чтобы он не обрезался

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="x", padx=S(44), pady=(S(18), 0))

        self.bar = tk.Canvas(wrap, height=self._bar_h, bg=BG,
                             highlightthickness=0, bd=0, cursor="hand2")
        self.bar.pack(fill="x")

        bar_line_w = self._bar_y2 - self._bar_y1
        # запасной вариант без Pillow
        self.bar_bg = self.bar.create_line(
            self._bar_pad, self._bar_cy, self._bar_pad + 1, self._bar_cy,
            width=bar_line_w, fill=TRACK_LINE, capstyle="round",
            joinstyle="round", state="hidden")
        self.bar_fill = self.bar.create_line(
            self._bar_pad, self._bar_cy, self._bar_pad, self._bar_cy,
            width=bar_line_w, fill=self.accent, capstyle="round",
            joinstyle="round", state="hidden")
        self._bar_photo = None
        self._bar_photo_item = None
        if HAS_PIL:
            self._bar_photo_item = self.bar.create_image(
                0, self._bar_cy - bar_line_w // 2, anchor="nw")

        thumb = self._thumb_image(S(16))
        if thumb is not None:
            self._bar_thumb_img = True
            self.bar_thumb = self.bar.create_image(self._bar_pad, self._bar_cy,
                                                   image=thumb, anchor="center",
                                                   state="hidden")
        else:
            self.bar_thumb = self.bar.create_oval(0, 0, 0, 0, fill="#ffffff",
                                                  outline="", state="hidden")

        self.bar.bind("<Button-1>", self._seek_press)
        self.bar.bind("<B1-Motion>", self._seek_drag)
        self.bar.bind("<ButtonRelease-1>", self._seek_release)
        self.bar.bind("<Configure>", lambda e: self._refresh_bar())
        self.bar.bind("<Enter>", self._bar_enter)
        self.bar.bind("<Leave>", self._bar_leave)

    def _bar_enter(self, _e=None):
        if self.duration <= 0:
            return
        self._bar_hover = True
        self._bar_thumb_d = S(20)
        pos = self._seek_pos if self.seeking else (
            self._live_position() if self.state == "playing" else self.position)
        self._paint(pos)

    def _bar_leave(self, _e=None):
        self._bar_hover = False
        if not self.seeking:
            self._bar_thumb_d = S(16)
            if self.duration > 0:
                pos = self._live_position() if self.state == "playing" else self.position
                self._paint(pos)

    def _build_volume(self):
        self._vol_h = S(24)
        self._vol_y1 = S(9)
        self._vol_y2 = S(15)
        self._vol_cy = self._vol_h // 2
        self._vol_pad = S(9)          # место под кружок громкости
        self._vol_w = S(190)

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(pady=(S(6), S(14)))

        self.repeat_icon = RepeatIcon(wrap, size=S(18), color=MUTED, bg=BG,
                                      active=self.repeat)
        self.repeat_icon.pack(side="left", padx=(0, S(10)))
        self.repeat_icon.bind("<Button-1>", self.toggle_repeat)
        self.repeat_icon.bind("<Enter>", lambda e: self.repeat_icon.set_hover(True))
        self.repeat_icon.bind("<Leave>", lambda e: self.repeat_icon.set_hover(False))

        self.vol_icon = SpeakerIcon(wrap, size=S(20), color=MUTED, bg=BG,
                                    muted=self.mute)
        self.vol_icon.pack(side="left", padx=(0, S(8)))
        self.vol_icon.bind("<Button-1>", self._toggle_mute)
        self.vol_icon.bind("<Enter>", lambda e: self.vol_icon.set_hover(True))
        self.vol_icon.bind("<Leave>", lambda e: self.vol_icon.set_hover(False))


        self.vol = tk.Canvas(wrap, width=self._vol_w, height=self._vol_h, bg=BG,
                             highlightthickness=0, bd=0, cursor="hand2")
        self.vol.pack(side="left")
        vol_line_w = self._vol_y2 - self._vol_y1
        self.vol_bg = self.vol.create_line(
            self._vol_pad, self._vol_cy, self._vol_w - self._vol_pad,
            self._vol_cy, width=vol_line_w, fill=TRACK_LINE,
            capstyle="round", joinstyle="round", state="hidden")
        self.vol_fill = self.vol.create_line(
            self._vol_pad, self._vol_cy, self._vol_pad, self._vol_cy,
            width=vol_line_w, fill=self.accent, capstyle="round",
            joinstyle="round", state="hidden")
        self._vol_photo = None
        self._vol_photo_item = None
        if HAS_PIL:
            self._vol_photo_item = self.vol.create_image(
                0, self._vol_cy - vol_line_w // 2, anchor="nw")

        thumb = self._thumb_image(self._vol_thumb_d)
        if thumb is not None:
            self._vol_thumb_img = True
            self.vol_thumb = self.vol.create_image(self._vol_pad, self._vol_cy,
                                                   image=thumb, anchor="center")
        else:
            self.vol_thumb = self.vol.create_oval(0, 0, 0, 0, fill="#ffffff",
                                                  outline="")

        self.vol.bind("<Button-1>", self._set_volume)
        self.vol.bind("<B1-Motion>", self._set_volume)
        self.vol.bind("<ButtonRelease-1>", self._save_volume)
        self.vol.bind("<Configure>", lambda e: self._paint_volume(self._vol_ratio))
        self.vol.bind("<Enter>", self._vol_enter)
        self.vol.bind("<Leave>", self._vol_leave)

        self.lbl_vol = tk.Label(wrap, text="50%", bg=BG, fg=MUTED,
                                font=self._font_sub, width=4, anchor="w")
        self.lbl_vol.pack(side="left", padx=(S(8), 0))
        for widget in (self.vol, self.vol_icon, self.lbl_vol):
            widget.bind("<MouseWheel>", self._vol_wheel)

        self._paint_volume(self._vol_ratio)
        self._sync_mute()

    def _vol_enter(self, _e=None):
        self._vol_hover = True
        self._vol_thumb_d = S(16)
        self._paint_volume(self._vol_ratio)

    def _vol_leave(self, _e=None):
        self._vol_hover = False
        self._vol_thumb_d = S(12)
        self._paint_volume(self._vol_ratio)

    def _paint_volume(self, ratio):
        ratio = max(0.0, min(float(ratio), 1.0))
        self._vol_ratio = ratio
        self.volume = ratio
        self._stream_player.volume = ratio
        self._stream_player.mute = self.mute
        w = self.vol.winfo_width()
        if w <= 1:
            w = self._vol_w
        pad = self._vol_pad
        span = max(1, w - 2 * pad)
        x = pad + ratio * span

        line_h = self._vol_y2 - self._vol_y1
        bg_color = TRACK_LINE_HOVER if self._vol_hover else TRACK_LINE
        photo = None
        if self._vol_photo_item is not None:
            photo = self._capsule_photo(
                w, line_h, pad, x, bg_color, self.accent,
                show_fill=ratio > 0.0005)
        if photo is not None:
            self._vol_photo = photo
            self.vol.itemconfig(self._vol_photo_item, image=photo,
                                state="normal")
            self.vol.coords(self._vol_photo_item, 0,
                            self._vol_cy - line_h // 2)
            self.vol.itemconfig(self.vol_bg, state="hidden")
            self.vol.itemconfig(self.vol_fill, state="hidden")
        else:
            if self._vol_photo_item is not None:
                self.vol.itemconfig(self._vol_photo_item, state="hidden")
            self.vol.coords(self.vol_bg, pad, self._vol_cy,
                            w - pad, self._vol_cy)
            self.vol.coords(self.vol_fill, pad, self._vol_cy, x, self._vol_cy)
            self.vol.itemconfig(self.vol_bg, fill=bg_color, state="normal")
            self.vol.itemconfig(
                self.vol_fill, fill=self.accent,
                state=("normal" if ratio > 0.0005 else "hidden"))

        if self._vol_thumb_img:
            img = self._thumb_image(self._vol_thumb_d)
            if img is not None:
                self.vol.itemconfig(self.vol_thumb, image=img)
            self.vol.coords(self.vol_thumb, x, self._vol_cy)
        else:
            self.vol.itemconfig(self.vol_thumb, fill="#ffffff")
            d = self._vol_thumb_d / 2.0
            self.vol.coords(self.vol_thumb, x - d, self._vol_cy - d,
                            x + d, self._vol_cy + d)

        self.lbl_vol.config(text="%d%%" % round(ratio * 100))

    def _sync_mute(self):
        """Обновляет иконку и громкость движка по логическому состоянию Mute."""
        if hasattr(self, "vol_icon"):
            self.vol_icon.set_muted(self.mute)
        self._stream_player.mute = self.mute
        self._stream_player.volume = self.volume
        apply_audio_volume()

    def _toggle_mute(self, _event=None):
        global MUTE_STATE
        self.mute = not self.mute
        if self._is_main:
            MUTE_STATE = self.mute
        self._sync_mute()
        if self._is_main:
            save_settings()
        return "break"

    def _on_window_focus(self, _event=None):
        """При возврате к окну проверяет только текущий трек, без обхода списка."""
        if self.index < 0 or self.current is None:
            return
        exists = os.path.isfile(self.current)
        if not exists and self.index not in self._missing:
            self._missing.add(self.index)
            self._paint_rows()
        elif exists and self.index in self._missing:
            self._missing.discard(self.index)
            self._paint_rows()

    def _on_window_map(self, _event=None):
        """Восстановление из панели задач: лёгкая перерисовка без мерцания."""
        self._suspended = False
        if not self._icon_hidden:
            hide_titlebar_icon(self.root)
            apply_windows_titlebar(self.root)
            self._icon_hidden = True
        self.root.after_idle(self._repaint_visible)
        if self.state == "playing":
            self._start_note_anim()

    def _on_window_unmap(self, _event=None):
        self._suspended = True
        self._stop_note_anim()

    def _repaint_visible(self):
        """Обновляет только видимые элементы после восстановления окна."""
        try:
            self._refresh_bar()
        except Exception:
            pass

    def _toolbar_button(self, parent, text, command,
                        width=None, height=None):
        b = RoundedButton(parent, text, command, self._font_button,
                          bg=parent.cget("bg"), fixed_width=width,
                          fixed_height=height)
        self._toolbar_buttons.append(b)
        return b

    # ===================== плейлист =======================================
    def _selection_bg(self):
        return mix(self.accent, CARD, 0.72)

    def _draw_header_bg(self):
        """Скруглённый фон верхней панели, как у кнопок."""
        if not hasattr(self, "_header_bg"):
            return
        w = self._header_bg.winfo_width()
        h = self._header_bg.winfo_height()
        if w <= 1 or h <= 1:
            return
        self._header_bg_tiles = draw_rounded_panel(
            self._header_bg, w, h, PANEL, BG, S(6))

    def _draw_playlist_bg(self):
        """Скруглённый фон области плейлиста, как у кнопок."""
        if not hasattr(self, "_playlist_bg"):
            return
        w = self._playlist_bg.winfo_width()
        h = self._playlist_bg.winfo_height()
        if w <= 1 or h <= 1:
            return
        self._playlist_bg_tiles = draw_rounded_panel(
            self._playlist_bg, w, h, CARD, BG, S(6))

    def _build_playlist(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=S(18))

        tk.Label(head, text="ПЛЕЙЛИСТ", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(side="left")

        # поле поиска: иконка + entry в скруглённой общей рамке
        self.search_field = tk.Canvas(head, bg=BG, highlightthickness=0, bd=0)
        self.search_field.pack(side="left", padx=(S(14), 0))
        self.search_field.bind("<Button-1>", self._focus_search)
        field_inner = tk.Frame(self.search_field, bg=BTN)

        self.search_icon = SearchIcon(field_inner, size=S(20), color=MUTED, bg=BTN)
        self.search_icon.pack(side="left", padx=(S(4), 0))
        self.search_icon.config(cursor="xterm")

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(field_inner, textvariable=self.search_var,
                                     bg=BTN, fg=MUTED, insertbackground=TEXT,
                                     relief="flat", bd=0, highlightthickness=0,
                                     font=self._font_ui, width=18)
        self.search_entry.pack(side="left", padx=(S(6), S(4)), pady=S(5))
        self.search_entry.bind("<KeyRelease>", self._schedule_filter)
        self.search_entry.bind("<Escape>", self._clear_search)
        self.search_entry.bind("<FocusIn>", self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)
        for sequence in ("<<Paste>>", "<Control-v>", "<Control-V>",
                         "<Shift-Insert>"):
            self.search_entry.bind(sequence, self._paste_search)
        self.search_entry.bind("<KeyPress>", self._search_keypress, add="+")
        for widget in (self.search_entry, field_inner, self.search_field):
            widget.bind("<Button-3>", self._show_search_menu)
        self.search_icon.bind("<Button-1>", self._search_icon_click)

        self.search_clear = ClearIcon(field_inner, size=S(16),
                                      color=MUTED, bg=BTN)
        self.search_clear.pack(side="left", padx=(0, S(6)))
        self.search_clear.bind("<Button-1>", self._search_clear_click)

        field_inner.update_idletasks()
        radius = S(6)
        field_w = field_inner.winfo_reqwidth() + 2 * radius
        field_h = field_inner.winfo_reqheight() + 2
        self.search_field.config(width=field_w, height=field_h)
        self.search_field.create_window(radius, 1, window=field_inner,
                                        anchor="nw")
        self._draw_search_bg(False)
        self._show_placeholder()
        self._search_field_h = field_h
        tool_size = max(S(24), field_h)
        labels = ("Выбрать папку", "Добавить трек", "Настройки", "Очистить")
        btn_w = max(self._font_button.measure(text)
                    for text in labels) + 2 * S(9)
        btn_h = field_h

        # кнопки «в конец / в начало» и история: тот же размер, что у панели
        self.scroll_btn = ScrollJumpIcon(head, size=tool_size,
                                         color=MUTED, bg=BG)
        self.scroll_btn.pack(side="left", padx=(S(6), 0))
        self.scroll_btn.bind("<Button-1>", self._toggle_playlist_edge)
        self.scroll_btn.bind("<Enter>", lambda e: self.scroll_btn.set_hover(True))
        self.scroll_btn.bind("<Leave>", lambda e: self.scroll_btn.set_hover(False))

        self.history_icon = HistoryIcon(head, size=tool_size,
                                        color=MUTED, bg=BG)
        self.history_icon.pack(side="left", padx=(S(6), 0))
        self.history_icon.bind("<Button-1>", self._toggle_history_panel)
        self.history_icon.bind("<Enter>",
                               lambda e: self.history_icon.set_hover(True))
        self.history_icon.bind("<Leave>",
                               lambda e: self.history_icon.set_hover(False))

        btns = tk.Frame(head, bg=BG)
        btns.pack(side="right")
        for text, command in (
                ("Выбрать папку", self._choose_folder),
                ("Добавить трек", self._add_files),
                ("Настройки", self._open_settings),
                ("Очистить", self._clear_list)):
            btn = self._toolbar_button(btns, text, command,
                                       width=btn_w, height=btn_h)
            btn.pack(side="left", padx=S(3))
            if text == "Настройки":
                self._settings_button = btn

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=S(18), pady=(S(10), S(18)))
        self._playlist_body = body
        self._playlist_bg = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
        self._playlist_bg.place(x=0, y=0, relwidth=1, relheight=1)
        self._playlist_bg.bind("<Configure>",
                               lambda e: self._draw_playlist_bg())

        gutter = tk.Frame(body, bg=CARD)
        gutter.pack(side="right", fill="y", padx=(S(0), S(2)), pady=S(8))
        self.scroll = SlimScrollbar(
            gutter, width=S(12), bg=CARD, thumb_pad=0, inset=S(2),
            thumb=self.accent,
            thumb_hover=mix(self.accent, "#ffffff", 0.25),
            thumb_drag=mix(self.accent, "#000000", 0.25))
        self.scroll.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            body, bg=CARD, fg=TEXT, selectbackground=self._selection_bg(),
            selectforeground=TEXT, relief="flat", bd=0, borderwidth=0,
            highlightthickness=0, font=self._font_list, activestyle="none",
            exportselection=False, yscrollcommand=self.scroll.set,
        )
        self.listbox.pack(side="left", fill="both", expand=True,
                          padx=(0, S(2)), pady=S(6))
        self.scroll.configure_commands(self.listbox.yview,
                                       self.listbox.yview_moveto)

        self.listbox.bind("<Double-Button-1>", self._play_selected_jump)
        self.listbox.bind("<Return>", self._play_selected)
        self.listbox.bind("<MouseWheel>", self._wheel)
        self.scroll.bind("<MouseWheel>", self._wheel)
        self.listbox.bind("<Configure>", self._on_list_configure)
        self.listbox.bind("<Motion>", self._on_row_motion)
        self.listbox.bind("<Leave>", self._on_row_leave)
        self.listbox.bind("<ButtonPress-1>", self._on_row_press)
        self.listbox.bind("<ButtonRelease-1>", self._on_row_release)
        self._draw_playlist_bg()

    # ---------- поиск / placeholder ----------
    def _draw_search_bg(self, focused=False):
        """Скруглённый фон/рамка поля поиска, как у кнопок."""
        try:
            w = int(self.search_field.cget("width"))
            h = int(self.search_field.cget("height"))
        except Exception:
            return
        border = self.accent if focused else CARD_EDGE
        self.search_field.delete("bg")
        self._search_bg_img = None
        if HAS_PIL:
            try:
                scale = SHAPE_SS
                big = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
                d = ImageDraw.Draw(big)
                d.rounded_rectangle(
                    [0, 0, w * scale - 1, h * scale - 1],
                    radius=S(6) * scale, fill=BTN, outline=border,
                    width=scale)
                big = big.resize((w, h), Image.LANCZOS)
                base = Image.new("RGB", (w, h), BG)
                base.paste(big, (0, 0), big)
                self._search_bg_img = ImageTk.PhotoImage(base)
                self.search_field.create_image(
                    0, 0, image=self._search_bg_img, anchor="nw", tags="bg")
                self.search_field.tag_lower("bg")
                return
            except Exception:
                pass
        self.search_field.create_rectangle(0, 0, w - 1, h - 1,
                                           fill=BTN, outline=border,
                                           tags="bg")
        self.search_field.tag_lower("bg")

    def _show_placeholder(self):
        self._ph_active = True
        self.search_var.set(PLACEHOLDER)
        self.search_entry.config(fg=MUTED)
        self._update_search_clear()

    def _search_focus_in(self, _e=None):
        self._draw_search_bg(True)
        if self._ph_active:
            self._ph_active = False
            self.search_var.set("")
        self.search_entry.config(fg=TEXT)
        self._update_search_clear()

    def _search_focus_out(self, _e=None):
        self._draw_search_bg(False)
        if not self.search_var.get().strip():
            self._show_placeholder()
        self._update_search_clear()

    def _search_keypress(self, event):
        """Ctrl+V / Shift+Insert для любой раскладки (в т.ч. русской)."""
        if event.state & 0x4:
            # на русской раскладке Tk присылает keysym "??", но keycode/char
            # физической клавиши V остаются прежними
            if (event.keysym.lower() in ("v", "м")
                    or event.keycode == 86
                    or event.char == "\x16"):
                return self._paste_search()
        if (event.state & 0x1) and (
                event.keysym == "Insert" or event.keycode == 45):
            return self._paste_search()
        return None

    def _clipboard_text(self):
        """Текст из буфера обмена; пустая строка, если текста нет."""
        try:
            text = self.root.clipboard_get()
            if text:
                return str(text)
        except Exception:
            pass
        for kind in ("STRING", "UTF8_STRING"):
            try:
                text = self.root.clipboard_get(type=kind)
                if text:
                    return str(text)
            except Exception:
                continue
        return ""

    def _paste_search(self, _event=None):
        """Вставка из буфера обмена в поиск с немедленной фильтрацией."""
        text = self._clipboard_text()
        if not text:
            # даём шанс штатной вставке Tk и обновляем фильтр после неё
            try:
                self.root.after(80, self._flush_search)
            except Exception:
                pass
            return None
        text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
        if not text:
            return "break"
        text = text[:200]
        self._ph_active = False
        if self.search_entry.get() == PLACEHOLDER:
            self.search_var.set("")
        try:
            first = self.search_entry.index("sel.first")
            last = self.search_entry.index("sel.last")
            self.search_entry.delete(first, last)
        except tk.TclError:
            pass
        self.search_entry.insert("insert", text)
        self.search_entry.config(fg=TEXT)
        self._update_search_clear()
        self._flush_search()
        try:
            self.search_entry.focus_set()
        except Exception:
            pass
        return "break"

    def _copy_search_selection(self):
        try:
            text = self.search_entry.selection_get()
        except tk.TclError:
            return
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
        except Exception:
            pass

    def _select_all_search(self):
        try:
            self.search_entry.selection_range(0, tk.END)
            self.search_entry.icursor(tk.END)
            self.search_entry.focus_set()
        except Exception:
            pass

    def _show_search_menu(self, event):
        """ПКМ по полю поиска: вставка, копирование, выделение, очистка."""
        try:
            self.search_entry.focus_set()
        except Exception:
            pass
        menu = tk.Menu(self.root, tearoff=0,
                       bg=PANEL, fg=TEXT,
                       activebackground=BTN_HOVER, activeforeground=TEXT,
                       bd=0, relief="flat", activeborderwidth=0)
        has_text = bool(self._clipboard_text())
        menu.add_command(label="Вставить", command=self._paste_search,
                         state=("normal" if has_text else "disabled"))
        menu.add_command(label="Копировать",
                         command=self._copy_search_selection)
        menu.add_command(label="Выделить всё", command=self._select_all_search)
        menu.add_separator()
        menu.add_command(label="Очистить", command=self._clear_search)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _query(self):
        if getattr(self, "_ph_active", False):
            return ""
        return self.search_var.get().strip().lower()

    def _reset_search(self):
        self._ph_active = False
        if getattr(self, "_search_job", None) is not None:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None
        self._cancel_scroll_anim()
        self._reset_scroll_button()
        old = getattr(self, "_search_set", set())
        self._search_hits = []
        self._search_index = -1
        self._search_set = set()
        self._search_name_cache = {}
        if hasattr(self, "listbox"):
            self._paint_search_diff(old, self._search_set)
        self.search_var.set("")
        self._update_search_clear()
        if self.search_entry.focus_get() == self.search_entry:
            self.search_entry.config(fg=TEXT)
        else:
            self._show_placeholder()

    def _clear_search(self, _event=None):
        self._ph_active = False
        if self._search_job is not None:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None
        self._cancel_scroll_anim()
        self._reset_scroll_button()
        self._search_hits = []
        self._search_index = -1
        self._search_set = set()
        self.search_var.set("")
        self._update_search_clear()
        self.view = self._build_view()
        self._render_list()
        if self.index in self.view:
            self._select_track(self.index, reveal=False)
        if self.search_entry.focus_get() != self.search_entry:
            self._show_placeholder()
        return "break"

    def _exit_search(self, _event=None):
        """Выход из поиска кликом: только сброс фильтра, без запуска трека."""
        self._clear_search()
        self.search_entry.selection_clear()
        return "break"

    def _search_icon_click(self, _event=None):
        self.search_entry.focus_set()
        return "break"

    def _search_clear_click(self, _event=None):
        if getattr(self, "search_clear", None) is not None and \
                self.search_clear.visible:
            return self._clear_search()
        self.search_entry.focus_set()
        return "break"

    def _update_search_clear(self):
        if hasattr(self, "search_clear"):
            self.search_clear.set_visible(bool(self._query()))

    def _focus_search(self, _event=None):
        """Явный клик по самому полю — только тогда ставим фокус в поиск."""
        self.search_entry.focus_set()
        return "break"

    # ---------- кнопка «в конец / в начало» ----------
    def _cancel_scroll_anim(self):
        if self._scroll_job is not None:
            try:
                self.root.after_cancel(self._scroll_job)
            except Exception:
                pass
            self._scroll_job = None

    def _reset_scroll_button(self):
        self._scroll_at_bottom = False
        if hasattr(self, "scroll_btn"):
            self.scroll_btn.set_direction("down")

    def _toggle_playlist_edge(self, _event=None):
        """Прокручивает список к концу, затем к началу; трек и поиск не трогает."""
        if self.listbox.size() == 0:
            return "break"
        target = 0.0 if self._scroll_at_bottom else 1.0
        self._scroll_at_bottom = not self._scroll_at_bottom
        if hasattr(self, "scroll_btn"):
            self.scroll_btn.set_direction(
                "up" if self._scroll_at_bottom else "down")
        self._scroll_list_to(target)
        return "break"

    def _scroll_list_to(self, target):
        """Плавная прокрутка без перестройки плейлиста."""
        self._cancel_scroll_anim()
        try:
            start = float(self.listbox.yview()[0])
        except Exception:
            return
        target = max(0.0, min(1.0, float(target)))
        if abs(target - start) < 0.001:
            try:
                self.listbox.yview_moveto(target)
            except Exception:
                pass
            return
        steps = 16

        def step(index=[0]):
            self._scroll_job = None
            index[0] += 1
            t = min(1.0, index[0] / float(steps))
            eased = 1.0 - (1.0 - t) ** 3       # плавное затухание
            try:
                self.listbox.yview_moveto(start + (target - start) * eased)
            except Exception:
                return
            if t < 1.0:
                self._scroll_job = self.root.after(16, step)

        step()

    # ---------- история текущего сеанса ----------
    def _record_history(self, path):
        """Считает запуски за сеанс; повторный трек поднимается наверх."""
        if not path:
            return
        key = os.path.abspath(path)
        for entry in self.history:
            if os.path.abspath(entry.get("path", "")) == key:
                entry["count"] = int(entry.get("count", 0)) + 1
                break
        else:
            self.history.insert(0, {"path": path, "count": 1})
        if self._history_open:
            self._refresh_history_panel()

    def _toggle_history_panel(self, _event=None):
        if self._history_open:
            return self._hide_history_panel()
        return self._show_history_panel()

    def _show_history_panel(self, _event=None):
        if self._playlist_body is None:
            return "break"
        if self._settings_open:
            self._hide_settings_panel()
        if self._history_panel is not None:
            try:
                self._history_panel.lift()
            except Exception:
                pass
            self._history_open = True
            if hasattr(self, "history_icon"):
                self.history_icon.set_active(True)
            self._refresh_history_panel()
            return "break"
        panel = tk.Frame(self._playlist_body, bg=PANEL,
                         highlightthickness=S(1),
                         highlightbackground=CARD_EDGE)
        panel.place(x=S(8), y=-S(18), width=S(440), relheight=0.86)
        self._history_panel = panel
        self._history_card_normal = None
        self._history_card_hover = None
        self._history_hover = -1

        head = tk.Frame(panel, bg=PANEL)
        head.pack(fill="x", padx=S(14), pady=(S(12), S(6)))
        tk.Label(head, text="История", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 12)).pack(side="left")

        list_wrap = tk.Frame(panel, bg=PANEL)
        list_wrap.pack(fill="both", expand=True,
                       padx=(S(10), S(8)), pady=(0, S(10)))
        self._history_scroll = SlimScrollbar(list_wrap, width=S(8), bg=PANEL)
        self._history_scroll.pack(side="right", fill="y", padx=(S(4), 0))
        self._history_canvas = tk.Canvas(
            list_wrap, bg=PANEL, highlightthickness=0, bd=0)
        self._history_canvas.pack(side="left", fill="both", expand=True)
        self._history_canvas.configure(
            yscrollcommand=self._history_on_scroll)
        self._history_scroll.configure_commands(
            self._history_canvas.yview, self._history_canvas.yview_moveto)
        self._history_canvas.bind("<Configure>", self._history_on_configure)
        self._history_canvas.bind("<MouseWheel>", self._history_wheel)
        self._history_canvas.bind("<Motion>", self._history_motion)
        self._history_canvas.bind("<Leave>", self._history_leave)
        self._history_canvas.bind("<Double-Button-1>", self._history_double)
        self._history_scroll.bind("<MouseWheel>", self._history_wheel)

        self._history_open = True
        if hasattr(self, "history_icon"):
            self.history_icon.set_active(True)
        self._refresh_history_panel()
        self._animate_history_in(panel)
        return "break"

    def _cancel_history_anim(self):
        if self._history_anim_job is not None:
            try:
                self.root.after_cancel(self._history_anim_job)
            except Exception:
                pass
            self._history_anim_job = None

    def _animate_history_in(self, panel):
        self._cancel_history_anim()
        start = -S(18)
        end = S(6)
        steps = 9

        def step(index=[0]):
            self._history_anim_job = None
            if not self._history_open or self._history_panel is not panel:
                return
            try:
                if not panel.winfo_exists():
                    return
            except Exception:
                return
            index[0] += 1
            t = min(1.0, index[0] / float(steps))
            eased = 1.0 - (1.0 - t) ** 3
            try:
                panel.place_configure(y=int(start + (end - start) * eased))
            except Exception:
                return
            if t < 1.0:
                self._history_anim_job = self.root.after(14, step)

        self._history_anim_job = self.root.after(14, step)

    def _hide_history_panel(self, _event=None):
        self._cancel_history_anim()
        if self._history_panel is not None:
            try:
                self._history_panel.destroy()
            except Exception:
                pass
        self._history_panel = None
        self._history_canvas = None
        self._history_scroll = None
        self._history_card_normal = None
        self._history_card_hover = None
        self._history_hover = -1
        self._history_open = False
        if hasattr(self, "history_icon"):
            self.history_icon.set_active(False)
        return "break"

    def _history_wheel(self, event):
        if self._history_canvas is None:
            return "break"
        step = -3 if event.delta > 0 else 3
        self._history_canvas.yview_scroll(step, "units")
        return "break"

    def _history_step(self):
        return self._history_row_h + S(4)

    def _history_content_height(self):
        return S(2) + max(1, len(self.history)) * self._history_step()

    def _history_on_configure(self, _event=None):
        self._history_card_normal = None
        self._history_card_hover = None
        self._update_history_scrollregion()
        self._draw_history_visible()

    def _history_on_scroll(self, first, last):
        if self._history_scroll is not None:
            self._history_scroll.set(first, last)
        self._draw_history_visible()

    def _update_history_scrollregion(self):
        if self._history_canvas is None:
            return
        try:
            w = max(1, self._history_canvas.winfo_width())
            h = max(self._history_content_height(),
                    self._history_canvas.winfo_height())
            self._history_canvas.configure(scrollregion=(0, 0, w, h))
        except Exception:
            pass

    def _history_card_image(self, hover):
        if self._history_canvas is None:
            return None
        self._history_card_normal = getattr(self, "_history_card_normal", None)
        if hover:
            if self._history_card_hover is not None:
                return self._history_card_hover
        elif self._history_card_normal is not None:
            return self._history_card_normal
        w = max(S(80), self._history_canvas.winfo_width() - S(4))
        h = self._history_row_h
        fill = ROW_HOVER if hover else CARD
        img = smooth_image(w, h, fill, PANEL, radius=S(8))
        if hover:
            self._history_card_hover = img
        else:
            self._history_card_normal = img
        return img

    def _history_index_at(self, y):
        if self._history_canvas is None or not self.history:
            return -1
        cy = self._history_canvas.canvasy(y) - S(2)
        if cy < 0:
            return -1
        step = self._history_step()
        index = int(cy // step)
        if index < 0 or index >= len(self.history):
            return -1
        if cy - index * step > self._history_row_h:
            return -1
        return index

    def _draw_history_row(self, index, width):
        canvas = self._history_canvas
        if canvas is None or not (0 <= index < len(self.history)):
            return
        tag = "hrow_%d" % index
        canvas.delete(tag)
        entry = self.history[index]
        y = S(2) + index * self._history_step()
        img = self._history_card_image(index == self._history_hover)
        if img is not None:
            canvas.create_image(S(2), y, image=img, anchor="nw",
                                tags=("histrow", tag))
        else:
            canvas.create_rectangle(S(2), y, width - S(2), y + self._history_row_h,
                                    fill=(ROW_HOVER if index == self._history_hover
                                          else CARD), outline="",
                                    tags=("histrow", tag))
        title = display_title(entry.get("path", ""))
        pad = S(14)
        maxw = max(S(40), width - 2 * pad)
        canvas.create_text(pad, y + self._history_row_h / 2.0,
                           text=elide(title, self._font_list, maxw),
                           anchor="w", fill=TEXT, font=self._font_list,
                           tags=("histrow", tag))

    def _draw_history_visible(self):
        canvas = self._history_canvas
        if canvas is None:
            return
        canvas.delete("histrow")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            return
        if not self.history:
            canvas.create_text(width / 2.0, min(height / 2.0, S(60)),
                               text="Пока нет прослушиваний", fill=MUTED,
                               font=self._font_list, tags="histrow")
            return
        top = canvas.canvasy(0)
        first = max(0, int((top - S(2)) // self._history_step()))
        last = min(len(self.history) - 1,
                   int((top + height - S(2)) // self._history_step()) + 1)
        for index in range(first, last + 1):
            self._draw_history_row(index, width)

    def _history_motion(self, event):
        index = self._history_index_at(event.y)
        if index == self._history_hover:
            return
        old = self._history_hover
        self._history_hover = index
        width = self._history_canvas.winfo_width() if self._history_canvas else 0
        if 0 <= old < len(self.history):
            self._draw_history_row(old, width)
        if index >= 0:
            self._draw_history_row(index, width)

    def _history_leave(self, _event=None):
        if self._history_hover == -1:
            return
        old = self._history_hover
        self._history_hover = -1
        if self._history_canvas is not None and 0 <= old < len(self.history):
            self._draw_history_row(old, self._history_canvas.winfo_width())

    def _history_double(self, event):
        index = self._history_index_at(event.y)
        if index >= 0:
            self._history_play(index)

    def _history_play(self, index):
        if not (0 <= index < len(self.history)):
            return
        path = self.history[index].get("path", "")
        try:
            target = os.path.normcase(os.path.abspath(path))
        except Exception:
            return
        track_index = -1
        for i, item in enumerate(self.tracks):
            try:
                if os.path.normcase(os.path.abspath(item)) == target:
                    track_index = i
                    break
            except Exception:
                pass
        if track_index < 0:
            self._notify("Трек не найден в плейлисте")
            return
        self._play_index(track_index, reveal=False)
        if self._history_canvas is not None:
            self._draw_history_visible()

    def _refresh_history_panel(self):
        if self._history_canvas is None:
            return
        self._update_history_scrollregion()
        self._draw_history_visible()

    # ---------- строки плейлиста ----------
    def _is_separator_pos(self, pos):
        return 0 <= pos < len(self.view) and self.view[pos] == VIEW_SEPARATOR

    def _is_missing_pos(self, pos):
        return (0 <= pos < len(self.view)
                and self.view[pos] != VIEW_SEPARATOR
                and self.view[pos] in self._missing)

    def _row_foreground(self, pos):
        if self._is_separator_pos(pos):
            return TRACK_LINE_HOVER
        if self._is_missing_pos(pos):
            return "#ffffff"
        if pos == self._active_row:
            return self.accent
        if pos in self._search_set:
            return mix(self.accent, "#ffffff", 0.35)
        return TEXT

    def _row_bg(self, pos):
        if self._is_separator_pos(pos):
            return CARD
        if self._is_missing_pos(pos):
            return MISSING_BG
        return ROW_ALT if pos % 2 else CARD

    def _row_state_bg(self, pos, state):
        if self._is_separator_pos(pos):
            return CARD
        if self._is_missing_pos(pos):
            return MISSING_PRESS if state == "press" else MISSING_HOVER
        return ROW_PRESS if state == "press" else ROW_HOVER

    def _refresh_availability(self, force=False):
        """Перепроверяет файлы; полный обход — не чаще раза в 2 секунды."""
        now = time.time()
        if not force and now - self._last_avail_check < 2.0:
            return
        self._last_avail_check = now
        missing = {i for i, path in enumerate(self.tracks)
                   if not os.path.isfile(path)}
        if missing != self._missing:
            self._missing = missing
            self._paint_rows()

    def _row_index_at(self, y):
        if self.listbox.size() == 0:
            return -1
        idx = self.listbox.nearest(y)
        if idx < 0:
            return -1
        bbox = self.listbox.bbox(idx)
        if not bbox:
            return -1
        top, height = bbox[1], bbox[3]
        if top <= y < top + height:
            return idx
        return -1

    def _set_row_color(self, pos):
        if pos is None or pos < 0 or pos >= self.listbox.size():
            return
        if pos == self._pressed_row:
            bg = self._row_state_bg(pos, "press")
        elif pos == self._hover_row:
            bg = self._row_state_bg(pos, "hover")
        else:
            bg = self._row_bg(pos)
        self.listbox.itemconfig(pos, background=bg)

    def _on_row_motion(self, event):
        idx = self._row_index_at(event.y)
        if idx != self._hover_row:
            old = self._hover_row
            self._hover_row = idx
            self._set_row_color(old)
            self._set_row_color(idx)

    def _on_row_leave(self, _event=None):
        if self._hover_row != -1 or self._pressed_row != -1:
            old_hover = self._hover_row
            old_press = self._pressed_row
            self._hover_row = -1
            self._pressed_row = -1
            self._set_row_color(old_hover)
            self._set_row_color(old_press)

    def _on_row_press(self, event):
        self._cancel_scroll_anim()
        pos = self._row_index_at(event.y)
        old = self._pressed_row
        if pos < 0 or self._is_separator_pos(pos):
            self._pressed_row = -1
            try:
                self._selection_before_sep = list(self.listbox.curselection())
            except Exception:
                self._selection_before_sep = []
            self._set_row_color(old)
            self.root.after_idle(self._drop_separator_selection)
            return
        self._selection_before_sep = []
        # выделяем строку сами, чтобы разделитель нельзя было выбрать
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(pos)
        try:
            self.listbox.activate(pos)
        except Exception:
            pass
        self._pressed_row = pos
        self._set_row_color(old)
        self._set_row_color(self._pressed_row)

    def _on_row_release(self, _event=None):
        old = self._pressed_row
        self._pressed_row = -1
        self._set_row_color(old)
        self.root.after_idle(self._drop_separator_selection)

    def _drop_separator_selection(self):
        """Разделитель — не трек: убираем его из выделения."""
        try:
            selected = list(self.listbox.curselection())
        except Exception:
            return
        seps = [pos for pos in selected if self._is_separator_pos(pos)]
        if not seps:
            return
        keep = [pos for pos in selected if not self._is_separator_pos(pos)]
        self.listbox.selection_clear(0, tk.END)
        for pos in keep:
            self.listbox.selection_set(pos)
        if keep:
            self._selection_before_sep = []
            return
        saved = [pos for pos in self._selection_before_sep
                 if 0 <= pos < self.listbox.size()
                 and not self._is_separator_pos(pos)]
        self._selection_before_sep = []
        if saved:
            for pos in saved:
                self.listbox.selection_set(pos)
            return
        target = seps[0] - 1
        while target >= 0 and self._is_separator_pos(target):
            target -= 1
        if target < 0:
            target = seps[0] + 1
            size = self.listbox.size()
            while target < size and self._is_separator_pos(target):
                target += 1
            if target >= size:
                return
        self.listbox.selection_set(target)
        try:
            self.listbox.activate(target)
            self.listbox.see(target)
        except Exception:
            pass

    def _paint_rows(self):
        active = self.view.index(self.index) if self.index in self.view else -1
        self._active_row = active
        for pos in range(self.listbox.size()):
            if self._is_separator_pos(pos):
                self.listbox.itemconfig(
                    pos, background=CARD, foreground=TRACK_LINE_HOVER,
                    selectbackground=CARD, selectforeground=TRACK_LINE_HOVER)
                continue
            missing = self._is_missing_pos(pos)
            if pos == self._pressed_row:
                bg = self._row_state_bg(pos, "press")
            elif pos == self._hover_row:
                bg = self._row_state_bg(pos, "hover")
            else:
                bg = self._row_bg(pos)
            sel_bg = MISSING_SEL if missing else self._selection_bg()
            self.listbox.itemconfig(
                pos,
                background=bg,
                foreground=self._row_foreground(pos),
                selectbackground=sel_bg,
                selectforeground=("#ffffff" if missing
                                  else contrast_text(sel_bg)),
            )

    def _on_list_configure(self, event):
        if abs(event.width - self._last_list_w) > 2:
            self._last_list_w = event.width
            self._render_list(keep_scroll=True)

    def _wheel(self, event):
        self._cancel_scroll_anim()
        self.listbox.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    # ===================== клавиатура =====================================
    def _bind_keys(self):
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<Button-1>", self._on_global_click, add="+")
        # перехватываем клавиши на самом списке раньше стандартной обработки,
        # иначе стрелки двигают выделение и прокручивают плейлист
        self.listbox.bind("<Key>", self._on_key)

    def _on_global_click(self, event):
        """Клик вне истории/настроек закрывает их; вне поиска — убирает фокус."""
        try:
            widget = str(event.widget)
        except Exception:
            widget = ""
        if self._history_open:
            try:
                inside = (self._history_panel is not None
                          and widget.startswith(str(self._history_panel)))
                on_icon = (hasattr(self, "history_icon")
                           and (event.widget is self.history_icon
                                or widget.startswith(str(self.history_icon))))
            except Exception:
                inside = False
                on_icon = False
            if not inside and not on_icon:
                self._hide_history_panel()
        if self._settings_open:
            try:
                inside = (self._settings_panel is not None
                          and widget.startswith(str(self._settings_panel)))
                on_btn = (getattr(self, "_settings_button", None) is not None
                          and (event.widget is self._settings_button
                               or widget.startswith(
                                   str(self._settings_button))))
            except Exception:
                inside = False
                on_btn = False
            if not inside and not on_btn:
                self._hide_settings_panel()
        try:
            if str(event.widget).startswith(str(self.search_field)):
                return
        except Exception:
            pass
        try:
            if self.root.focus_get() is self.search_entry:
                # иначе буквы продолжают попадать в поиск после клика по кнопке
                self.root.focus_set()
        except Exception:
            pass

    def _on_key(self, event):
        focus = self.root.focus_get()
        if focus is self.search_entry:
            if event.keysym == "Return":
                self._flush_search()
                return self._play_first_visible()
            return None
        if isinstance(focus, (tk.Entry, tk.Text)):
            return None
        symbol = event.keysym
        char = (event.char or "").lower()
        if symbol == "Escape" and self._settings_open:
            self._hide_settings_panel()
            return "break"
        if symbol == "space" or char == " ":
            self.toggle()
            return "break"
        if symbol == "Up" or char in ("w", "ц"):
            self._move_selection(-1)
            return "break"
        if symbol == "Down" or char in ("s", "ы"):
            self._move_selection(1)
            return "break"
        if symbol == "Left" or char in ("a", "ф"):
            return self._seek_by(-SEEK_STEP)
        if symbol == "Right" or char in ("d", "в"):
            return self._seek_by(SEEK_STEP)
        # список не должен «уезжать» от стрелок и PageUp/PageDown
        if focus is self.listbox and symbol in (
                "Up", "Down", "Prior", "Next", "Home", "End"):
            return "break"
        return None

    def _seek_by(self, delta):
        if self.current is None or self.duration <= 0:
            return None
        target = max(0.0, min(self._live_position() + delta,
                              max(0.0, self.duration - 0.15)))
        self._apply_seek(target)
        return "break"

    # ===================== список / поиск =================================
    def _natural_key(self, text):
        """Сортировка как в проводнике: 1, 2, 10, а не 1, 10, 2."""
        parts = []
        digits = ""
        for ch in text.lower():
            if ch.isdigit():
                digits += ch
            else:
                if digits:
                    parts.append((1, int(digits), ""))
                    digits = ""
                parts.append((0, 0, ch))
        if digits:
            parts.append((1, int(digits), ""))
        return parts

    def _build_view(self, indices=None):
        """Порядок строк: папка сверху, добавленные снизу, разделитель между."""
        if indices is None:
            indices = range(len(self.tracks))
        folder = []
        added = []
        for index in indices:
            if not (0 <= index < len(self.tracks)):
                continue
            if index < self._folder_count:
                folder.append(index)
            else:
                added.append(index)
        if folder and added:
            return folder + [VIEW_SEPARATOR] + added
        return folder + added

    def _list_maxw(self):
        width = self.listbox.winfo_width()
        if width <= 1:
            width = S(700)
        maxw = max(S(60), width - S(18))
        if maxw != self._elide_width:
            self._elide_cache = {}
            self._elide_width = maxw
        return maxw

    def _row_text(self, index, maxw):
        if index == VIEW_SEPARATOR:
            return "─" * 300
        path = self.tracks[index]
        from_folder = index < self._folder_count
        base = display_name(path) if from_folder else display_title(path)
        prefix = "   "
        cache_key = (path, from_folder)
        shown = self._elide_cache.get(cache_key)
        if shown is None:
            shown = elide(base, self._font_list,
                          maxw - self._font_list.measure(prefix))
            self._elide_cache[cache_key] = shown
        return prefix + shown

    def _append_view_rows(self, new_view):
        """Добавляет только новые строки, не перестраивая список целиком."""
        old_len = len(self.view)
        if (old_len > len(new_view)
                or new_view[:old_len] != self.view
                or self.listbox.size() != old_len):
            self.view = new_view
            self._render_list(keep_scroll=True)
            return
        if old_len == len(new_view):
            self.view = new_view
            return
        maxw = self._list_maxw()
        for index in new_view[old_len:]:
            self.listbox.insert(tk.END, self._row_text(index, maxw))
        self.view = new_view
        self._paint_rows()
        try:
            self.scroll.set(*self.listbox.yview())
        except Exception:
            pass

    def _render_list(self, keep_scroll=False):
        keep = 0.0
        selected = ()
        if keep_scroll:
            try:
                keep = float(self.listbox.yview()[0])
                selected = self.listbox.curselection()
            except Exception:
                keep = 0.0
                selected = ()
        self.listbox.delete(0, tk.END)
        self._hover_row = -1
        self._pressed_row = -1
        maxw = self._list_maxw()
        for i in self.view:
            self.listbox.insert(tk.END, self._row_text(i, maxw))
        # после перерисовки (например, при изменении ширины) возвращаем выделение
        if keep_scroll and selected:
            for pos in selected:
                if 0 <= pos < self.listbox.size():
                    self.listbox.selection_set(pos)
        elif self.index in self.view:
            self.listbox.selection_set(self.view.index(self.index))
        self._paint_rows()
        if keep_scroll and self.listbox.size() > 0:
            try:
                self.listbox.yview_moveto(keep)
            except Exception:
                pass
        try:
            self.scroll.set(*self.listbox.yview())
        except Exception:
            pass

    def _schedule_filter(self, _event=None):
        """Фильтрует поиск с короткой задержкой, не перестраивая список на каждый символ."""
        if self._search_job is not None:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.root.after(100, self._run_scheduled_filter)

    def _run_scheduled_filter(self):
        self._search_job = None
        self._filter_list()

    def _flush_search(self):
        if self._search_job is not None:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None
        self._filter_list()

    def _filter_list(self, _event=None):
        """Показывает в основном списке треки, похожие по ключевым словам."""
        self._cancel_scroll_anim()
        self._reset_scroll_button()
        query = self._query()
        self._update_search_clear()
        if query:
            terms = _search_normalize(query).split()
            cache = getattr(self, "_search_name_cache", None)
            if cache is None:
                cache = {}
                self._search_name_cache = cache
            hits = []
            for i, path in enumerate(self.tracks):
                name = cache.get(path)
                if name is None:
                    name = _search_normalize(display_name(path))
                    cache[path] = name
                if _name_matches_terms(name, terms):
                    hits.append(i)
            self._search_hits = hits
            self.view = self._build_view(self._search_hits)
        else:
            self._search_hits = []
            self.view = self._build_view()
        self._search_index = (self._search_hits[0]
                              if self._search_hits else -1)
        self._search_set = set()
        self._render_list()
        if query and self.listbox.size() > 0:
            # показываем начало результатов; играет только двойной клик
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self.listbox.see(0)

    def _paint_search_diff(self, old, new):
        for pos in old.symmetric_difference(new):
            if 0 <= pos < self.listbox.size():
                self.listbox.itemconfig(pos,
                                        foreground=self._row_foreground(pos))

    def _search_select(self, index):
        """Выделяет найденный трек и прокручивает к нему основной список."""
        if index not in self.view:
            return
        pos = self.view.index(index)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(pos)
        self.listbox.see(pos)

    def _play_first_visible(self):
        if self._query():
            if self._search_index >= 0:
                self._play_index(self._search_index)
            return "break"
        if self.view:
            self._play_index(self.view[0])
        return "break"

    def _select_track(self, index, reveal=True):
        if self._query():
            # поиск активен: не перестраиваем список и не сбиваем найденный трек
            if index in self.view:
                self._update_active_row(self.view.index(index))
            else:
                self._update_active_row(-1)
            return
        if index not in self.view:
            return
        pos = self.view.index(index)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(pos)
        if reveal:
            self.listbox.see(pos)
        self._update_active_row(pos)

    def _update_active_row(self, pos):
        """Меняет цвет только старой и новой активной строки (быстро)."""
        old = self._active_row
        if old == pos:
            return
        self._active_row = pos
        for row in (old, pos):
            if 0 <= row < self.listbox.size():
                self.listbox.itemconfig(
                    row, foreground=self._row_foreground(row))

    # ===================== данные =========================================
    def _duration_of(self, path):
        key = os.path.abspath(path)
        if key in DURATION_CACHE:
            return DURATION_CACHE[key]
        length = 0.0
        try:
            ext = Path(path).suffix.lower()
            if ext == ".mp3" and MP3:
                length = float(MP3(path).info.length)
            elif ext == ".mp4" and MP4:
                info = MP4(path).info
                if info.length:
                    length = float(info.length)
        except Exception:
            length = 0.0
        if length > 0:
            DURATION_CACHE[key] = length
        return length

    def _probe_duration(self, path):
        """Длительность в фоне: часовые VBR-треки не блокируют интерфейс."""
        def worker():
            try:
                length = self._duration_of(path)
            except Exception:
                length = 0.0
            if length > 0:
                self._inbox.put({"duration": [path, length]})
        threading.Thread(target=worker, daemon=True).start()

    def _apply_duration(self, path, length):
        if self.current != path:
            return
        self.duration = max(0.0, float(length))
        if self.duration > 0 and self.position > self.duration:
            self.position = max(0.0, self.duration - 0.15)
        self._refresh_bar()

    @staticmethod
    def _fmt(seconds):
        seconds = max(0, int(seconds))
        return "%02d:%02d" % (seconds // 60, seconds % 60)

    # ===================== папка / файлы ==================================
    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку с музыкой")
        if not folder:
            return
        if self.tracks:
            # в окне уже есть список — открываем папку отдельным окном
            open_new_window(folder=folder)
        else:
            # пустое окно — импортируем папку сюда же
            self._load_folder(folder)

    def _load_folder(self, folder):
        self.folder = folder
        self._main_loaded = True
        self._reset_player()
        names = []
        try:
            for name in os.listdir(folder):
                if Path(name).suffix.lower() in (".mp3", ".mp4"):
                    names.append(name)
        except Exception as exc:
            messagebox.showerror("Ошибка", "Не удалось прочитать папку:\n%s" % exc)
            return

        names.sort(key=self._natural_key)   # порядок как в проводнике, без нумерации
        self.tracks = [os.path.join(folder, n) for n in names]
        self._folder_count = len(self.tracks)
        self.view = self._build_view()
        self._reset_search()
        self._render_list()
        self._refresh_availability(force=True)

        if self.tracks:
            self._set_title(Path(folder).name or "Плейлист")
            self._set_sub("Треков: %d" % len(self.tracks))
        else:
            self._set_title("Треки не найдены")
            self._set_sub("В папке нет MP3 или MP4")
        self._update_transport()
        self._remember_tracks()

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Добавить треки",
            filetypes=[("Аудио файлы", "*.mp3 *.mp4"),
                       ("MP3", "*.mp3"),
                       ("MP4", "*.mp4"),
                       ("Все файлы", "*.*")],
        )
        if not files:
            return
        self._add_external_files(list(files), play=True)

    def _clear_list(self):
        was_main = self._main_loaded
        self._reset_player()
        self.tracks = []
        self._folder_count = 0
        self.view = []
        self._missing = set()
        self.folder = None
        self._reset_search()
        self.listbox.delete(0, tk.END)
        self.scroll.set(0.0, 1.0)
        self._set_title("Плейлист очищен")
        self._set_sub("Выберите папку или добавьте трек" if was_main
                      else "Добавьте треки кнопкой «Добавить трек» или перетащите файлы")
        self.lbl_time.config(text="00:00 / 00:00")
        self._update_transport()
        self._refresh_bar()
        if was_main:
            global LAST_TRACK, LAST_POSITION, LAST_DURATION
            LAST_TRACK = None
            LAST_POSITION = 0.0
            LAST_DURATION = 0.0
            self._main_loaded = True
            self._remember_tracks()
        self._main_loaded = False

    # ===================== воспроизведение ================================
    def _set_state(self, state, subtitle=None):
        """Единая точка синхронизации состояния и иконки Play/Pause."""
        previous = getattr(self, "state", None)
        self.state = state
        if state == "playing" and previous != "playing":
            self._vinyl_forced_until = 0.0
            self._vinyl_dir = 1.0
            self._vinyl_target_rate = 95.0
        if hasattr(self, "note"):
            active = state in ("playing", "paused")
            if active != getattr(self, "_vinyl_active", None):
                self._draw_note()
        if state == "playing":
            self.btn_play.set_kind("pause")
            self._set_sub(subtitle or "Сейчас играет")
            self._start_note_anim()
        elif state == "paused":
            self.btn_play.set_kind("play")
            self._set_sub(subtitle or "Пауза")
            self._stop_note_anim()
        else:
            self.btn_play.set_kind("play")
            self._set_sub(subtitle or "Остановлено")
            self._stop_note_anim()
        self._update_taskbar_title()

    def _update_transport(self):
        has_tracks = bool(self.tracks)
        self.btn_prev.set_enabled(has_tracks)
        self.btn_next.set_enabled(has_tracks)

    def _stop_mixer(self):
        self._stream_player.stop()

    def _silence_others(self):
        """Окна плеера независимы: не останавливаем воспроизведение в других."""
        return

    def _be_silent(self):
        """Останавливает звук другого окна, сохраняя его трек и позицию."""
        if self.state == "playing":
            self.position = self._live_position()
            self._stop_mixer()
            self._set_state("paused", "Пауза")
            self._refresh_bar()
        elif self.state == "paused":
            self._stop_mixer()
            self._refresh_bar()

    def _reset_player(self):
        self._stop_mixer()
        self.index = -1
        self.current = None
        self.duration = 0.0
        self.position = 0.0
        self.start_time = 0.0
        self.seeking = False
        self._set_state("idle")
        self._refresh_bar()

    def _play_selected(self, _event=None):
        """Enter по выделенному треку: играем, не сбрасывая поиск."""
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self.view):
            index = self.view[sel[0]]
            if index != VIEW_SEPARATOR:
                self._play_index(index)

    def _play_selected_jump(self, _event=None):
        """Двойной клик: найденный трек показываем на его месте в общем списке."""
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self.view):
            index = self.view[sel[0]]
            if index == VIEW_SEPARATOR:
                return
            if self._query():
                self._jump_to_track(index)
            else:
                self._play_index(index)

    def _jump_to_track(self, index):
        """Двойной клик по результату: полный список, прокрутка и запуск."""
        self._clear_search()
        if 0 <= index < len(self.tracks):
            self._play_index(index)

    def _play_index(self, index, reveal=True):
        if not ensure_stream_modules():
            messagebox.showerror(
                APP_NAME,
                "Не найден аудиодвижок.\n"
                "Установите: py -m pip install sounddevice numpy imageio-ffmpeg")
            return
        if not self.tracks:
            return
        index %= len(self.tracks)
        path = self.tracks[index]
        if not os.path.isfile(path):
            messagebox.showwarning(
                APP_NAME, "Файл недоступен:\n%s\n\n"
                "Трек остаётся в плейлисте. Если файл вернётся на место, "
                "его можно будет воспроизвести снова." % path)
            return
        if index in self._missing:
            self._missing.discard(index)
            self._paint_rows()
        self._silence_others()
        self.current = path
        self.index = index
        if not self._stream_player.load(path, 0.0, SPEED):
            self.current = None
            self.index = -1
            self.duration = 0.0
            self.position = 0.0
            self._set_state("idle", "Не удалось воспроизвести")
            self._refresh_bar()
            messagebox.showerror(
                APP_NAME, "Не удалось воспроизвести файл:\n%s"
                % (self._stream_player.error or "неизвестная ошибка"))
            return

        self.duration = DURATION_CACHE.get(os.path.abspath(self.current), 0.0)
        self.position = 0.0
        self.start_time = time.time()
        self.seeking = False
        self._set_state("playing")
        self._set_title(display_title(self.current))
        self._record_history(self.current)
        if reveal:
            self._select_track(index)
        elif index in self.view:
            self._update_active_row(self.view.index(index))
        else:
            self._update_active_row(-1)
        self._refresh_bar()
        self._probe_duration(self.current)

    def toggle(self):
        if not self.tracks:
            self._set_sub("Сначала выберите папку или добавьте трек")
            return
        if self.index < 0:
            self._play_index(0)
            return

        if self.state == "playing":
            self.position = self._stream_player.position()
            self._stream_player.pause()
            self.root.after(80, self._stream_player.finish_pause)
            self._set_state("paused")
            self._refresh_bar()
            return

        self._silence_others()
        ok = False
        if (self.state == "paused"
                and self._stream_player.paused
                and self._stream_player.path == os.path.abspath(self.current)):
            ok = self._stream_player.resume()
        else:
            ok = self._stream_player.load(self.current, self.position, SPEED)
        if not ok:
            messagebox.showerror(
                APP_NAME, "Не удалось продолжить воспроизведение:\n%s"
                % (self._stream_player.error or "неизвестная ошибка"))
            return
        self._set_state("playing")
        self._refresh_bar()

    def next_track(self):
        if not self.tracks:
            return
        self._play_index((self.index + 1) % len(self.tracks))

    def prev_track(self):
        if not self.tracks:
            return
        start = self.index if self.index >= 0 else 0
        self._play_index((start - 1) % len(self.tracks))

    def toggle_repeat(self, _event=None):
        global REPEAT
        self.repeat = not self.repeat
        if self._is_main:
            REPEAT = self.repeat
        if hasattr(self, "repeat_icon"):
            self.repeat_icon.set_active(self.repeat)
        if self._is_main:
            save_settings()

    def _step_track(self, delta):
        """Клавиатурное переключение без выхода за границы плейлиста."""
        if not self.tracks:
            return
        if self.index < 0:
            target = 0
        else:
            target = max(0, min(len(self.tracks) - 1, self.index + delta))
        if target != self.index:
            self._play_index(target)
        else:
            self._select_track(target, reveal=True)

    def _move_selection(self, delta):
        """Стрелки/W/S двигают выделение, не меняя воспроизводимый трек."""
        size = self.listbox.size()
        if size <= 0:
            return
        sel = self.listbox.curselection()
        if sel:
            pos = sel[0]
        elif self.index in self.view:
            pos = self.view.index(self.index)
        else:
            pos = 0
        step = 1 if delta > 0 else -1
        target = pos
        for _ in range(abs(delta)):
            nxt = target + step
            while 0 <= nxt < size and self._is_separator_pos(nxt):
                nxt += step
            if not (0 <= nxt < size):
                break
            target = nxt
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(target)
        self.listbox.see(target)

    def _live_position(self):
        if self.state == "playing":
            pos = self._stream_player.position()
            if self.duration > 0:
                pos = min(pos, self.duration)
            return max(0.0, pos)
        return max(0.0, self.position)

    # ===================== перемотка ======================================
    def _ratio_from_x(self, x):
        w = self.bar.winfo_width()
        if w <= 1:
            return 0.0
        pad = self._bar_pad
        span = max(1, w - 2 * pad)
        return max(0.0, min((x - pad) / span, 1.0))

    def _seek_press(self, event):
        if self.duration <= 0 or self.current is None:
            return
        self.seeking = True
        self._seek_dragged = False
        self._bar_thumb_d = S(20)
        self._seek_pos = self._ratio_from_x(event.x) * self.duration
        if self.state in ("playing", "paused"):
            self._vinyl_seek(self._seek_pos - self._live_position())
        self._paint(self._seek_pos)

    def _seek_drag(self, event):
        if not self.seeking:
            return
        self._seek_dragged = True
        self._seek_pos = self._ratio_from_x(event.x) * self.duration
        if self.state in ("playing", "paused"):
            self._vinyl_seek(self._seek_pos - self._live_position())
        self._paint(self._seek_pos)

    def _seek_release(self, event):
        if not self.seeking:
            return
        self.seeking = False
        self._seek_pos = self._ratio_from_x(event.x) * self.duration
        self._apply_seek(self._seek_pos)
        if self._seek_dragged:
            # отпустили именно ползунок — плавно возвращаем обычное вращение
            if self.state == "playing":
                self._vinyl_return_normal()
            elif self.state == "paused":
                self._vinyl_forced_until = 0.0
                self._stop_note_anim()
        if not self._bar_hover:
            self._bar_thumb_d = S(16)
            self._paint(self.position)

    def _apply_seek(self, position):
        if self.current is None or not HAS_STREAM:
            return
        was_playing = (self.state == "playing")
        position = max(0.0, float(position))
        if self.duration > 0:
            position = min(position, self.duration)
        play_pos = position
        if self.duration > 0:
            play_pos = min(position, max(0.0, self.duration - 0.15))

        if not was_playing:
            # на паузе/остановке звук не запускаем
            if self.state == "paused":
                self._vinyl_seek(position - self.position)
            self.position = play_pos
            self._stream_player.set_position(play_pos)
            if self.state == "idle":
                self._set_sub("Продолжить с %s" % self._fmt(play_pos))
            self._paint(play_pos)
            return

        self._vinyl_seek(position - self._live_position())
        if not self._stream_player.seek(play_pos):
            return
        self.position = play_pos
        self._set_state("playing")
        self._paint(play_pos)

    def _paint(self, position):
        w = self.bar.winfo_width()
        if w <= 1:
            return
        pad = self._bar_pad
        span = max(1, w - 2 * pad)
        ratio = 0.0
        if self.duration > 0:
            ratio = max(0.0, min(position / self.duration, 1.0))
        x = pad + ratio * span

        line_h = self._bar_y2 - self._bar_y1
        bg_color = TRACK_LINE_HOVER if self._bar_hover else TRACK_LINE
        show_fill = self.duration > 0 and ratio > 0.0005
        photo = None
        if self._bar_photo_item is not None:
            key = (w, int(round(x)), bg_color, self.accent, bool(show_fill))
            if (key == getattr(self, "_bar_photo_key", None)
                    and self._bar_photo is not None):
                photo = self._bar_photo
            else:
                photo = self._capsule_photo(
                    w, line_h, pad, x, bg_color, self.accent,
                    show_fill=show_fill)
                if photo is not None:
                    self._bar_photo_key = key
        if photo is not None:
            self._bar_photo = photo
            self.bar.itemconfig(self._bar_photo_item, image=photo,
                                state="normal")
            self.bar.coords(self._bar_photo_item, 0,
                            self._bar_cy - line_h // 2)
            self.bar.itemconfig(self.bar_bg, state="hidden")
            self.bar.itemconfig(self.bar_fill, state="hidden")
        else:
            if self._bar_photo_item is not None:
                self.bar.itemconfig(self._bar_photo_item, state="hidden")
            self.bar.coords(self.bar_bg, pad, self._bar_cy,
                            w - pad, self._bar_cy)
            self.bar.coords(self.bar_fill, pad, self._bar_cy, x, self._bar_cy)
            self.bar.itemconfig(self.bar_bg, fill=bg_color, state="normal")
            self.bar.itemconfig(self.bar_fill, fill=self.accent,
                                state=("normal" if show_fill else "hidden"))

        if self.duration > 0:
            if self._bar_thumb_img:
                img = self._thumb_image(self._bar_thumb_d)
                if img is not None:
                    self.bar.itemconfig(self.bar_thumb, image=img)
                self.bar.coords(self.bar_thumb, x, self._bar_cy)
            else:
                d = self._bar_thumb_d / 2.0
                self.bar.coords(self.bar_thumb, x - d, self._bar_cy - d,
                                x + d, self._bar_cy + d)
            self.bar.itemconfig(self.bar_thumb, state="normal")
            self._set_time_text("%s / %s" % (self._fmt(position),
                                             self._fmt(self.duration)))
        else:
            self.bar.itemconfig(self.bar_thumb, state="hidden")
            self._set_time_text("00:00 / 00:00")

    def _set_time_text(self, text):
        if text != self._last_time_text:
            self._last_time_text = text
            self.lbl_time.config(text=text)

    def _refresh_bar(self):
        w = self.bar.winfo_width()
        if w <= 1:
            return
        if self.duration <= 0:
            self._paint(0.0)
            return
        if self.seeking:
            self._paint(self._seek_pos)
            return
        if self.state == "playing":
            self.position = self._live_position()
        self._paint(self.position)

    # ===================== таймер =========================================
    def _tick(self):
        if self._closed:
            return
        if self._suspended:
            # свёрнутое окно всё равно принимает внешние файлы из Проводника
            try:
                self._drain_drops()
                self._drain_inbox()
            except Exception:
                pass
            self.root.after(250, self._tick)
            return
        try:
            self._drain_drops()
            self._drain_inbox()
            self._poll_system_accent()
            if self.state == "playing" and not self.seeking:
                if self._stream_player.done:
                    if self.repeat and self.index >= 0:
                        self._play_index(self.index)
                    else:
                        self.next_track()
                else:
                    self.position = self._live_position()
                    self._refresh_bar()
            elif not self.seeking:
                self._refresh_bar()
        except Exception:
            pass
        # 30 кадров/с — плавная аудиодорожка без лишней нагрузки
        delay = 33 if (self.state == "playing" and not self._suspended) else 250
        self.root.after(delay, self._tick)

    # ===================== громкость ======================================
    def _set_volume(self, event):
        w = self.vol.winfo_width()
        if w <= 1:
            w = self._vol_w
        pad = self._vol_pad
        span = max(1, w - 2 * pad)
        ratio = max(0.0, min((event.x - pad) / span, 1.0))

        global VOLUME
        self.volume = ratio
        if self._is_main:
            VOLUME = ratio
        self._paint_volume(ratio)
        # громкость меняется сразу, но при Mute движок остаётся на нуле
        apply_audio_volume()

    def _save_volume(self, _event=None):
        self._save_now()

    def _schedule_save(self, delay=250):
        if not self._is_main:
            return
        try:
            if self._save_job is not None:
                self.root.after_cancel(self._save_job)
        except Exception:
            pass
        self._save_job = self.root.after(delay, self._save_now)

    def _save_now(self):
        self._save_job = None
        if self._is_main:
            save_settings()

    def _vol_wheel(self, event):
        """Колесо мыши над громкостью: ±2%, сохранение для главного окна."""
        global VOLUME
        if not getattr(event, "delta", 0):
            return "break"
        step = 0.02 if event.delta > 0 else -0.02
        self.volume = max(0.0, min(1.0, self.volume + step))
        if self._is_main:
            VOLUME = self.volume
        self._paint_volume(self.volume)
        apply_audio_volume()
        self._schedule_save()
        return "break"

    # ===================== настройки / цвет ===============================
    def _open_settings(self, _event=None):
        if self._settings_open:
            return self._hide_settings_panel()
        return self._show_settings_panel()

    def _show_settings_panel(self, _event=None):
        if self._settings_panel is not None:
            try:
                self._settings_panel.lift()
            except Exception:
                pass
            return "break"
        if self._playlist_body is None:
            return "break"
        if self._history_open:
            self._hide_history_panel()

        body = self._playlist_body
        body.update_idletasks()
        body_w = max(S(360), body.winfo_width())
        body_h = max(S(260), body.winfo_height())
        panel_w = min(S(430), body_w - S(24))
        panel_h = min(S(300), body_h - S(8))
        x = max(S(8), body_w - panel_w - S(18))
        y = S(4)

        panel = tk.Frame(body, bg=CARD)
        panel.place(x=x, y=y, width=panel_w, height=panel_h)
        self._settings_panel = panel
        self._settings_open = True

        bgc = tk.Canvas(panel, bg=CARD, highlightthickness=0, bd=0)
        bgc.place(x=0, y=0, relwidth=1, relheight=1)

        def draw_bg(_e=None):
            ww = bgc.winfo_width()
            hh = bgc.winfo_height()
            if ww > 1 and hh > 1:
                self._settings_bg_tiles = draw_rounded_panel(
                    bgc, ww, hh, PANEL, CARD, S(8), border=CARD_EDGE)
        bgc.bind("<Configure>", draw_bg)
        try:
            panel.update_idletasks()
        except Exception:
            pass
        draw_bg()

        content = tk.Frame(panel, bg=PANEL)
        content.pack(fill="both", expand=True, padx=S(14), pady=S(14))

        head = tk.Frame(content, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text="Настройки", bg=PANEL, fg=TEXT,
                 font=self._font_title).pack(side="left")

        tk.Label(content, text="ЦВЕТ АКЦЕНТА", bg=PANEL, fg=MUTED,
                 font=self._font_button, anchor="w").pack(
            fill="x", pady=(S(10), S(6)))

        inner_w = max(S(200), panel_w - 2 * S(14))
        self._settings_system_btn = RoundedButton(
            content, "Цвет как в системе Windows",
            self._use_system_accent, self._font_button, bg=PANEL,
            fixed_width=inner_w, fixed_height=S(30))
        self._settings_system_btn.pack(fill="x")
        self._settings_system_btn.set_active(ACCENT_MODE == "system")

        grid = tk.Frame(content, bg=PANEL)
        grid.pack(fill="x", pady=(S(10), 0))
        cell = S(44)
        self._settings_swatches = []
        columns = 9
        for idx, (_name, value) in enumerate(ACCENT_PRESETS):
            cv = tk.Canvas(grid, width=cell, height=cell, bg=PANEL,
                           highlightthickness=0, bd=0, cursor="hand2")
            cv.grid(row=idx // columns, column=idx % columns,
                    padx=0, pady=0)
            cv._swatch_color = value
            cv._swatch_cell = cell
            cv._swatch_img = None
            self._settings_swatches.append((value, cv))
            cv.bind("<Button-1>", lambda e, c=value: self._pick_accent(c))
            cv.bind("<Enter>", lambda e, w=cv: self._hover_swatch(w, True))
            cv.bind("<Leave>", lambda e, w=cv: self._hover_swatch(w, False))

        foot = tk.Frame(content, bg=PANEL)
        foot.pack(fill="x", side="bottom")
        reset = RoundedButton(foot, "Сбросить цвет", self._reset_color,
                              self._font_button, bg=PANEL,
                              fixed_width=S(170), fixed_height=S(30))
        reset.pack(side="left")

        self._refresh_settings_panel()
        return "break"

    def _hide_settings_panel(self, _event=None):
        if self._settings_panel is not None:
            try:
                self._settings_panel.destroy()
            except Exception:
                pass
        self._settings_panel = None
        self._settings_open = False
        self._settings_swatches = []
        self._settings_system_btn = None
        return "break"

    def _swatch_image(self, cell, color, ring):
        """Сглаженный кружок цвета и серое кольцо — без пиксельных краёв."""
        if not HAS_PIL:
            return None
        cell = max(1, int(cell))
        key = ("swatch", cell, color, ring)
        img = self._img_cache.get(key)
        if img is not None:
            return img
        try:
            ss = max(4, SHAPE_SS)
            big = cell * ss
            base = Image.new("RGB", (big, big), PANEL)
            draw = ImageDraw.Draw(base)
            c = big / 2.0
            if ring:
                rr = (cell - 2 * S(5)) / 2.0 * ss
                draw.ellipse([c - rr, c - rr, c + rr, c + rr],
                             outline=ring, width=max(1, ss))
            cr = S(28) / 2.0 * ss
            gradient = GRADIENT_ACCENTS.get(color.lower())
            if gradient:
                # спокойные градиенты в палитре; в UI идёт средний тон
                top = tuple(int(gradient[0][i:i + 2], 16)
                            for i in (1, 3, 5))
                bottom = tuple(int(gradient[1][i:i + 2], 16)
                               for i in (1, 3, 5))
                grad = Image.new("RGB", (big, big))
                gd = ImageDraw.Draw(grad)
                for yy in range(big):
                    t = yy / float(max(1, big - 1))
                    col = tuple(int(top[k] + (bottom[k] - top[k]) * t)
                                for k in range(3))
                    gd.line([(0, yy), (big, yy)], fill=col)
                mask = Image.new("L", (big, big), 0)
                ImageDraw.Draw(mask).ellipse(
                    [c - cr, c - cr, c + cr, c + cr], fill=255)
                base.paste(grad, (0, 0), mask)
            else:
                draw.ellipse([c - cr, c - cr, c + cr, c + cr], fill=color)
            base = base.resize((cell, cell), Image.LANCZOS)
            img = ImageTk.PhotoImage(base)
        except Exception:
            return None
        self._img_cache[key] = img
        return img

    def _paint_swatch(self, cv, color, hover=False):
        cell = int(cv._swatch_cell)
        active = (ACCENT_MODE == "manual"
                  and color.lower() == self.accent.lower())
        ring = SWATCH_RING if active else (
            SWATCH_RING_HOVER if hover else None)
        cv.delete("all")
        cv._swatch_img = None
        img = self._swatch_image(cell, color, ring)
        if img is not None:
            cv._swatch_img = img
            cv.create_image(0, 0, image=img, anchor="nw")
            return
        d = S(28)
        if ring:
            rr = (cell - 2 * S(5)) / 2.0
            cv.create_oval(cell / 2.0 - rr, cell / 2.0 - rr,
                           cell / 2.0 + rr, cell / 2.0 + rr,
                           outline=ring, width=max(1, S(1)))
        cv.create_oval((cell - d) / 2.0, (cell - d) / 2.0,
                       (cell + d) / 2.0, (cell + d) / 2.0,
                       fill=color, outline="")

    def _hover_swatch(self, cv, hover):
        self._paint_swatch(cv, cv._swatch_color, hover=hover)

    def _pick_accent(self, color):
        self._apply_accent(color, mode="manual")

    def _refresh_settings_panel(self):
        if not self._settings_open:
            return
        for color, cv in list(self._settings_swatches):
            try:
                self._paint_swatch(cv, color)
            except Exception:
                pass
        if self._settings_system_btn is not None:
            try:
                self._settings_system_btn.set_active(ACCENT_MODE == "system")
            except Exception:
                pass

    def _use_system_accent(self):
        color = system_accent_color() or DEFAULT_ACCENT
        self._apply_accent(color, mode="system")

    def _reset_color(self, _event=None):
        """Сброс акцента к серебристому; фон всегда остаётся тёмным."""
        self._apply_accent(DEFAULT_ACCENT, mode="manual")

    def _apply_accent(self, color, broadcast=True, mode="manual", persist=True):
        global ACCENT, THEME_MODE, ACCENT_MODE
        ACCENT_MODE = "system" if mode == "system" else "manual"
        ACCENT = color
        THEME_MODE = "manual"
        self.accent = color
        if hasattr(self, "note"):
            self._draw_note()
        if hasattr(self, "btn_play"):
            for btn in (self.btn_play, self.btn_prev, self.btn_next):
                btn.set_accent(color)
        if hasattr(self, "bar"):
            self._refresh_bar()
        if hasattr(self, "vol"):
            self._paint_volume(self._vol_ratio)
        if hasattr(self, "listbox"):
            self.listbox.config(selectbackground=self._selection_bg())
        if self._history_open:
            self._refresh_history_panel()
        if hasattr(self, "scroll"):
            self.scroll.thumb_color = color
            self.scroll.thumb_hover = mix(color, "#ffffff", 0.25)
            self.scroll.thumb_drag = mix(color, "#000000", 0.25)
            self.scroll._redraw()
        if hasattr(self, "listbox"):
            self._paint_rows()
        if hasattr(self, "repeat_icon"):
            self.repeat_icon.accent = color
            self.repeat_icon.set_active(self.repeat)
        if hasattr(self, "history_icon"):
            self.history_icon.accent = color
            self.history_icon.set_active(self._history_open)
        for b in getattr(self, "_toolbar_buttons", []):
            try:
                b.config(highlightcolor=color)
            except Exception:
                pass
        if hasattr(self, "search_entry"):
            if self.search_entry.focus_get() == self.search_entry:
                self._draw_search_bg(True)
        if broadcast:
            for win in list(WINDOWS):
                if win is not self:
                    try:
                        win._apply_accent(color, broadcast=False, mode=mode,
                                          persist=False)
                    except Exception:
                        pass
        if self._settings_open:
            self._refresh_settings_panel()
        if persist:
            save_settings()

    def _poll_system_accent(self):
        """Следит только за акцентом Windows; тема всегда остаётся тёмной."""
        global ACCENT_CHECK_TS
        if ACCENT_MODE != "system":
            return
        now = time.time()
        if now - ACCENT_CHECK_TS < 2.5:
            return
        ACCENT_CHECK_TS = now
        color = system_accent_color()
        if color and color.lower() != (self.accent or "").lower():
            self._apply_accent(color, mode="system")

    def _apply_system_palette(self, light, force=False):
        """Светлая/тёмная палитра по системной теме Windows."""
        light = bool(light)
        if not force and light == SYSTEM_LIGHT:
            return
        apply_theme_palette(light)
        for win in list(WINDOWS):
            try:
                win._rebuild_theme()
            except Exception:
                pass

    def _rebuild_theme(self):
        """Пересобирает интерфейс под новую фоновую палитру."""
        try:
            query = "" if self._ph_active else self.search_var.get()
        except Exception:
            query = ""
        try:
            focus_search = self.root.focus_get() is self.search_entry
        except Exception:
            focus_search = False
        try:
            scroll_pos = float(self.listbox.yview()[0])
        except Exception:
            scroll_pos = 0.0
        selected_track = None
        try:
            sel = self.listbox.curselection()
            if sel:
                selected_track = self.view[sel[0]]
        except Exception:
            selected_track = None
        title = self._title_full
        sub = self.lbl_sub.cget("text")
        state = self.state
        history_open = self._history_open
        if self._search_job is not None:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None
        self._cancel_history_anim()
        self._history_panel = None
        self._history_canvas = None
        self._history_scroll = None
        self._history_card_normal = None
        self._history_card_hover = None
        self._history_hover = -1
        self._history_open = False
        self._stop_note_anim()
        self._cancel_scroll_anim()
        for child in list(self.root.winfo_children()):
            if isinstance(child, tk.Toplevel):
                continue
            try:
                child.destroy()
            except Exception:
                pass
        self.root.configure(bg=BG)
        self._toolbar_buttons = []
        self._img_cache = {}
        self._elide_cache = {}
        self._elide_width = -1
        self._last_list_w = 0
        self._hover_row = -1
        self._pressed_row = -1
        self._active_row = -1
        self._selection_before_sep = []
        self._vinyl_glint = None
        self._vinyl_dot = None
        self._last_time_text = ""
        self._build_header()
        self._build_controls()
        self._build_progress()
        self._build_volume()
        self._build_playlist()
        self.root.unbind("<Button-1>")
        self._bind_keys()
        apply_app_icon(self.root)
        hide_titlebar_icon(self.root)
        lock_window_size(self.root, self._win_w, self._win_h)
        apply_windows_titlebar(self.root)
        self._set_title(title)
        self._set_sub(sub)
        if query:
            self._ph_active = False
            self.search_var.set(query)
            self._filter_list()
        else:
            self.view = self._build_view()
            self._render_list()
        self._update_transport()
        self._refresh_bar()
        self._set_state(state, sub)
        self._set_title(title)
        self._set_sub(sub)
        if (selected_track is not None and selected_track != VIEW_SEPARATOR
                and selected_track in self.view):
            try:
                pos = self.view.index(selected_track)
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(pos)
            except Exception:
                pass
        try:
            self.listbox.yview_moveto(scroll_pos)
        except Exception:
            pass
        if focus_search:
            try:
                self.search_entry.focus_set()
                self._draw_search_bg(True)
            except Exception:
                pass
        if history_open:
            self._show_history_panel()

    def _poll_system_theme(self):
        """Следит за акцентом и светлой/тёмной темой Windows."""
        now = time.time()
        if now - self._last_theme_check < 1.5:
            return
        self._last_theme_check = now
        light = system_uses_light_theme()
        if light != SYSTEM_LIGHT:
            self._apply_system_palette(light)
        if THEME_MODE == "system":
            accent = system_accent_color()
            if accent and accent.lower() != ACCENT.lower():
                self._apply_accent(accent, mode="system")

    # ===================== выход ==========================================
    def _close(self):
        global APP_ROOT
        if self._closing:
            return
        self._closing = True
        debug_log("close start main=%r windows=%d" % (self._is_main,
                                                       len(WINDOWS)))
        if self._is_main:
            self._remember_progress()
        debug_log("close step progress")
        self._stop_mixer()
        debug_log("close step mixer")
        if self._is_main:
            self._remember_tracks()
            save_settings()
        debug_log("close step save")
        self._stop_note_anim()
        self._cancel_history_anim()
        if self._search_job is not None:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None
        debug_log("close step anim")
        if self in WINDOWS:
            WINDOWS.remove(self)
        debug_log("close step removed")
        # не оставляем сервер привязанным к закрытому окну
        server = getattr(self, "_server", None)
        self._server = None
        if server is not None:
            try:
                server.close()
            except Exception:
                pass
            debug_log("close step server")
            if WINDOWS:
                try:
                    WINDOWS[0]._server = start_instance_server(WINDOWS[0])
                except Exception:
                    pass
        # не уничтожаем Toplevel из WM_DELETE: скрываем его, а корень
        # завершаем после выхода из главного цикла (иначе Tk может зависнуть)
        self._closed = True
        # Никаких Tk/Win32-вызовов внутри WM_DELETE: только планируем действие.
        if not WINDOWS:
            if APP_RUNNING:
                try:
                    self.root.after(1, self._exit_process)
                except Exception:
                    os._exit(0)
            else:
                try:
                    self.root.after(1, self.root.quit)
                except Exception:
                    pass
        else:
            try:
                self.root.after(1, self.root.withdraw)
            except Exception:
                pass
        debug_log("close done")

    @staticmethod
    def _exit_process():
        os._exit(0)


def show_window(top):
    """Показывает окно уже полностью отрисованным — без мигания."""
    try:
        top.attributes("-alpha", 0.0)
    except Exception:
        pass
    top.deiconify()
    try:
        top.update_idletasks()
        top.update()
    except Exception:
        pass
    try:
        top.attributes("-alpha", 1.0)
    except Exception:
        pass
    top.lift()


def open_new_window(files=None, title=None, folder=None):
    """Открывает независимое окно: папку или отдельные треки."""
    top = tk.Toplevel()
    top.withdraw()
    app = PlayerApp(top, initial_files=files or None,
                    title=title or APP_NAME, is_main=False)
    if folder:
        app._load_folder(folder)
    show_window(top)
    top.focus_force()
    return top


def main():
    enable_dpi_awareness()
    init_windows_app_id()
    load_settings()          # цвет, громкость, Mute, треки и позиция
    apply_theme_palette(False)   # единственная тема — тёмная

    # файлы из Проводника / «Открыть с помощью»
    files = [os.path.abspath(a) for a in sys.argv[1:]
             if a and not a.startswith("-")]
    autostart = any(a.lower() in ("--autostart", "/autostart")
                    for a in sys.argv[1:])
    debug_log("main argv=%r files=%r autostart=%r"
              % (sys.argv, files, autostart))

    first_instance = acquire_single_instance()
    if not first_instance:
        # первый экземпляр мог ещё не успеть открыть локальный порт
        for _ in range(12):
            if forward_to_existing({"files": files, "focus": True}):
                return
            time.sleep(0.25)
        return

    if forward_to_existing({"files": files, "focus": True}):
        return

    register_file_associations()

    if not HAS_STREAM:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_NAME,
            "Не найден аудиодвижок.\n"
            "Установите зависимости: py -m pip install sounddevice numpy imageio-ffmpeg")
        root.destroy()
        return

    root = tk.Tk()
    root.withdraw()
    root.title(APP_NAME)
    root.report_callback_exception = log_exception
    sys.excepthook = log_exception

    global SCALE, APP_ROOT, APP_RUNNING
    APP_ROOT = root
    APP_RUNNING = True
    try:
        dpi = root.winfo_fpixels("1i")
        SCALE = max(1.0, dpi / 96.0)
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        SCALE = 1.0

    # главное окно тоже Toplevel: закрытие любого окна не убивает остальные
    top = tk.Toplevel(root)
    top.withdraw()
    try:
        app = PlayerApp(top, is_main=True)
    except Exception:
        import traceback
        log = os.path.join(app_data_dir(), "zhumwave_error.log")
        try:
            with open(log, "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        except Exception:
            pass
        messagebox.showerror(APP_NAME, traceback.format_exc())
        root.destroy()
        return
    app._server = start_instance_server(app)
    show_window(top)
    if files:
        # «Открыть с помощью»: отдельное окно, основной плейлист не трогаем
        top.after(150, lambda items=list(files):
                  app._open_external_files(items, play=True))
    if autostart:
        # автозапуск после входа в Windows: плейлист загружается, окно
        # сворачивается в панель задач и не мешает работе
        top.after(300, top.iconify)
    root.mainloop()
    debug_log("main loop exited")
    # Tk иногда зависает при destroy скрытого корня — процесс уже всё сохранил
    os._exit(0)


if __name__ == "__main__":
    main()







