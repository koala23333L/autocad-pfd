# -*- coding: utf-8 -*-
"""标定映射（px_x=188+3.676x, px_y=3382-3.675y）后裁剪关键区域自检。"""
import os
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
pil = Image.open(os.path.join(OUT, "pfd_demo_hi.png"))

def crop(x1, y1, x2, y2, name, scale=1.5):
    ax = 188 + x1 * 3.676
    ay = 3382 - y2 * 3.675
    bx = 188 + x2 * 3.676
    by = 3382 - y1 * 3.675
    c = pil.crop((int(ax), int(ay), int(bx), int(by)))
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    c.save(os.path.join(OUT, name))
    print(name, c.size)

crop(740, 660, 1010, 800, "k_e102.png")        # 冷凝器+位号+回流绕线
crop(620, 60, 1010, 330, "k_f101.png")         # 重沸炉+标题栏
crop(540, 720, 800, 830, "k_coltop.png")       # 塔顶双管+PIC
crop(640, 690, 1000, 750, "k_cws.png")         # 循环水去向符号
crop(56, 24, 350, 140, "k_table.png")          # 物料表
crop(820, 16, 1180, 145, "k_title.png")        # 标题栏全貌
crop(560, 240, 760, 660, "k_column.png")       # 塔全貌
