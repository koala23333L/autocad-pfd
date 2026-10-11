# -*- coding: utf-8 -*-
"""成图 QA 工具：加载 draw_pfd 导出的 PNG，自动检测图框完成 mm→像素标定，
按 spec 逐台设备裁剪特写 + 底部一览区 + 标题栏，供逐台目视复核。

用法：
    python inspect_png.py <png路径> <spec.py路径或spec json路径> [输出目录]
spec 需含 equipment[{tag,x,y,label_xy}]（json/py 均可，py 需有 SPEC 变量）。
输出： <输出目录>/qa_<位号>.png、qa_bottom.png、qa_title.png
"""
import importlib.util
import json
import os
import sys

from PIL import Image

OUTER = {"A0": (1214.0, 841.0), "A1": (859.0, 591.0), "A2": (614.0, 431.0)}


def load_spec(path):
    if path.lower().endswith(".json"):
        with io_open(path) as f:
            return json.load(f)
    spec_mod = importlib.util.spec_from_file_location("spec_mod", path)
    m = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(m)
    return m.SPEC


def io_open(p):
    import io
    return io.open(p, encoding="utf-8")


def detect_frame(img):
    """检测图框外矩形：统计暗像素最密的前/后边界长线。"""
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    thr = 128

    def col_dark(x):
        return sum(1 for y in range(0, h, 4) if px[x, y] < thr) * 4

    def row_dark(y):
        return sum(1 for x in range(0, w, 4) if px[x, y] < thr) * 4

    cols = [x for x in range(w) if col_dark(x) > h * 0.55]
    rows = [y for y in range(h) if row_dark(y) > w * 0.55]
    if len(cols) < 2 or len(rows) < 2:
        raise RuntimeError("未检测到图框线，请确认导出 PNG 包含图框")
    return min(cols), min(rows), max(cols), max(rows)


def main():
    png, spec_path = sys.argv[1], sys.argv[2]
    outdir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(os.path.abspath(png)), "qa")
    os.makedirs(outdir, exist_ok=True)
    spec = load_spec(spec_path)
    img = Image.open(png)
    l, t, r, b = detect_frame(img)
    frame = spec.get("frame", "A0")
    Wmm, Hmm = OUTER.get(frame, OUTER["A0"])
    S = (r - l) / Wmm
    print("图框标定: left=%d top=%d right=%d bottom=%d  %.3f px/mm (%s)"
          % (l, t, r, b, S, frame))

    def crop_mm(name, x1, y1, x2, y2, scale=2):
        px1 = int(l + x1 * S); px2 = int(l + x2 * S)
        py1 = int(b - y2 * S); py2 = int(b - y1 * S)
        c = img.crop((max(px1, 0), max(py1, 0), min(px2, img.width), min(py2, img.height)))
        c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
        p = os.path.join(outdir, name)
        c.save(p)
        print(" ", name, c.size)

    for e in spec.get("equipment", []):
        ex, ey = float(e["x"]), float(e["y"])
        lx, ly = (e.get("label_xy") or [ex, ey])
        half = max(70.0, 0.62 * float(e.get("size") or 0))
        crop_mm("qa_%s.png" % e.get("tag", e["kind"]),
                min(ex, lx) - half, min(ey, ly) - half,
                max(ex, lx) + half, max(ey, ly) + half, scale=3)
    et = spec.get("equipment_table")
    if et:
        crop_mm("qa_bottom.png", et["x"] - 30, et["y"] - 45,
                et["x"] + et.get("width", 740) + 30, et["y"] + 15, scale=1.5)
    crop_mm("qa_title.png", 800, 10, 1189, 150, scale=2)
    print("QA 裁剪完成 →", outdir)


if __name__ == "__main__":
    main()
