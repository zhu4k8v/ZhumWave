# -*- coding: utf-8 -*-
"""
Генерирует ZhumWave.ico из ZhumWave.png (несколько размеров).
Запускается перед сборкой EXE (см. build_exe.bat).
"""
import os
import sys

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "ZhumWave.png")
DST = os.path.join(BASE, "ZhumWave.ico")

# Windows: 16, 32, 48, 64, 128, 256
SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    if not os.path.isfile(SRC):
        print("Ошибка: не найден %s" % SRC)
        return 1

    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    side = max(w, h)

    # квадратный прозрачный холст, чтобы сохранить пропорции
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)

    # каждый размер ICO уменьшается из исходного 512×512 (а не из 256×256)
    canvas.save(DST, format="ICO", sizes=SIZES)
    print("OK -> %s" % DST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
