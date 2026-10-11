# -*- coding: utf-8 -*-
import os
import pypdfium2 as pdfium

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
pdf = pdfium.PdfDocument(os.path.join(OUT, "pfd_demo.pdf"))
page = pdf[0]
w_pt, h_pt = page.get_width(), page.get_height()
print("pdf pts:", w_pt, h_pt)
scale = 6.0
bmp = page.render(scale=scale)
pil = bmp.to_pil()
W, H = pil.size
print("png px:", W, H)
pil.save(os.path.join(OUT, "pfd_demo_hi.png"))

def mm2px(x_mm, y_mm):
    # PDF 页面为 A0 landscape 1189x841mm，绘图满幅居中（CenterPlot+Fit），假设留白对称
    margin_x = (W - 1189 * (W / 1289)) / 2  # 粗略
    return None

# 直接裁剪：塔区域（模型 x 480..780, y 240..660）
# 比例：模型 1189mm -> W px（近似满幅）
sx, sy = W / 1289.0, H / 941.0  # 打印范围含边距
def crop(x1, y1, x2, y2, name):
    # 近似：图框 1189x841 占满打印范围
    px1 = int(x1 / 1189.0 * W); px2 = int(x2 / 1189.0 * W)
    py1 = int((841 - y2) / 841.0 * H); py2 = int((841 - y1) / 841.0 * H)
    box = (max(px1, 0), max(py1, 0), min(px2, W), min(py2, H))
    pil.crop(box).save(os.path.join(OUT, name))
    print(name, box)

crop(440, 220, 800, 700, "crop_column.png")
crop(880, 420, 1189, 841, "crop_reflux.png")
crop(60, 20, 560, 220, "crop_table.png")
crop(880, 0, 1189, 140, "crop_title.png")
