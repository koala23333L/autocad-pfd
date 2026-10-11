# -*- coding: utf-8 -*-
"""图纸级元素：图框(表4 X型含装订边)、标题栏、物料表(表13页示例)、管道/设备标注、物流箭头。"""
import math

import cad
import standards as std

# ================================================================ 图框 + 标题栏
def _tw(txt, h):
    """估算文本宽度：CJK≈1.0h，西文≈0.6h。"""
    w = 0.0
    for ch in txt:
        w += h if ord(ch) > 0x2E80 else h * 0.62
    return w


def draw_frame(doc, size="A0", fields=None):
    """绘制横向 X 型图框（左装订边 a，其余周边 c，外框线距纸边 e）与标题栏。
    标题栏结构对照标准图例第13/16页范例：
    行1 单位名称 | 工程名称；行2 签名表(设计/校核/审核/批准×姓名/日期) | 图名(两行大字) |
    设计阶段/图号；行3 日期 | 比例 | 张次。
    返回 {frame_rect, inner, title_block}。"""
    W, H, e, c, a = std.PAPER_SIZES[size]
    fields = fields or {}
    # 外框（纸边）
    cad.add_polyline(doc, [(0, 0), (W, 0), (W, H), (0, H), (0, 0)], "PFD-FRAME", 25)
    # 图框线
    x1, y1, x2, y2 = a, e, W - e, H - e
    cad.add_polyline(doc, [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)], "PFD-FRAME", 50)
    # ---------------- 标题栏 ----------------
    tb_w = min(340.0, (x2 - x1) * 0.45)
    tb_h = tb_w * 120.0 / 340.0
    bx, by = x2 - tb_w, y1
    F = "PFD-FRAME"
    cad.add_polyline(doc, [(bx, by), (bx + tb_w, by), (bx + tb_w, by + tb_h), (bx, by + tb_h), (bx, by)], F, 50)
    # 行线
    y_r1 = by + tb_h * (1 - 22 / 120.0)   # 行1/行2
    y_r2 = by + tb_h * (22 / 120.0)       # 行2/行3
    cad.add_line(doc, (bx, y_r1), (bx + tb_w, y_r1), F, 25)
    cad.add_line(doc, (bx, y_r2), (bx + tb_w, y_r2), F, 25)
    # 列线
    x_c1 = bx + tb_w * (140.0 / 340.0)    # 签名表右界
    x_c2 = bx + tb_w * (240.0 / 340.0)    # 右列左界
    cad.add_line(doc, (x_c2, y_r2), (x_c2, y_r1), F, 25)
    cad.add_line(doc, (x_c2, by), (x_c2, by + tb_h), F, 25)
    cad.add_line(doc, (x_c1, y_r2), (x_c1, y_r1), F, 25)
    cad.add_line(doc, (x_c1, by), (x_c1, y_r2), F, 25)
    # 签名表：4 行 × 3 列（职能/姓名/日期）
    roles = [("设计", fields.get("designer", "")), ("校核", fields.get("proofreader", "")),
             ("审核", fields.get("checker", "")), ("批准", fields.get("approver", ""))]
    rh = (y_r1 - y_r2) / 4.0
    xs = [bx, bx + tb_w * (45.0 / 340.0), bx + tb_w * (92.0 / 340.0), x_c1]
    for i in range(1, 4):
        cad.add_line(doc, (bx, y_r2 + i * rh), (x_c1, y_r2 + i * rh), F, 25)
    for xx in xs[1:3]:
        cad.add_line(doc, (xx, y_r2), (xx, y_r1), F, 25)

    def cell(tx, ty, txt, h=4.0, align="middle"):
        if txt:
            cad.add_text(doc, (tx, ty), h, str(txt), "PFD-TEXT", align=align)

    dates = fields.get("dates") or [""] * 4
    for i, (k, v) in enumerate(roles):
        cy = y_r1 - (i + 0.5) * rh
        cell((xs[0] + xs[1]) / 2, cy, k, 3.5)
        cell((xs[1] + xs[2]) / 2, cy, v, 4.0)
        cell((xs[2] + xs[3]) / 2, cy, dates[i] if i < len(dates) else "", 3.5)
    # 行1：单位名 | 工程名称
    cell((bx + x_c2) / 2, (y_r1 + by + tb_h) / 2, fields.get("unit_name", ""), 5.0)
    cell((x_c2 + bx + tb_w) / 2, (y_r1 + by + tb_h) / 2, fields.get("project_name", ""), 4.0)
    # 行2 中列：图名（可两行，大字）
    dn = str(fields.get("drawing_name", "工艺物料流程图（PFD）"))
    lines = dn.split("\n")
    if len(lines) == 1:
        lines = [dn, ""]
    cy = (y_r1 + y_r2) / 2
    cell((x_c1 + x_c2) / 2, cy + 4.5, lines[0], 5.0)
    cell((x_c1 + x_c2) / 2, cy - 5.5, lines[1], 5.0)
    # 行2 右列：设计阶段 / 图号
    sh = (y_r1 - y_r2) / 2.0
    cad.add_line(doc, (x_c2, y_r2 + sh), (bx + tb_w, y_r2 + sh), F, 25)
    cell((x_c2 + bx + tb_w) / 2, y_r2 + sh * 1.5, "阶段：" + str(fields.get("phase", "初步设计")), 4.0)
    cell((x_c2 + bx + tb_w) / 2, y_r2 + sh * 0.5, "图号 " + str(fields.get("drawing_no", "")), 5.0)
    # 行3：日期 | 比例 | 张次
    cell((bx + x_c1) / 2, by + tb_h * (11 / 120.0), str(fields.get("date", "")), 3.5)
    cell((x_c1 + x_c2) / 2, by + tb_h * (11 / 120.0), "比例 " + str(fields.get("scale", "")), 3.5)
    cell((x_c2 + bx + tb_w) / 2, by + tb_h * (11 / 120.0),
         "第 %s 张 共 %s 张" % (fields.get("sheet", "1"), fields.get("total_sheets", "1")), 3.5)
    return {"frame": (W, H), "inner": (x1 + 8, y1 + 8, x2 - 8, y2 - 8),
            "title_block": (bx, by, tb_w, tb_h)}


# ================================================================ 设备位号标注
def add_equipment_tag(doc, tag, name, x, y, above=True, h=5.0):
    """位号在上、粗实线、名称在下（标准图例：位号和名称用粗实线分开）。x,y 为粗实线中点。"""
    w = max(_tw(tag, h), _tw(name, h)) + h * 0.5
    if above:
        cad.add_text(doc, (x, y + h * 1.2), h, tag, "PFD-TEXT", align="middle")
        cad.add_line(doc, (x - w / 2, y), (x + w / 2, y), "PFD-TEXT", 50)
        cad.add_text(doc, (x, y - h * 1.2), h, name, "PFD-TEXT", align="middle")
    else:
        cad.add_text(doc, (x, y - h * 1.2), h, tag, "PFD-TEXT", align="middle")
        cad.add_line(doc, (x - w / 2, y), (x + w / 2, y), "PFD-TEXT", 50)
        cad.add_text(doc, (x, y + h * 1.2), h, name, "PFD-TEXT", align="middle")
    return (x, y)


# ================================================================ 管道标注 / 物流号
def pipe_tag_text(label):
    """由 dict 生成管道标注：{material, section, seq, dn, grade, insulation}
    形如 'PG 08 01-50 B2A H'；material 缺省时原样返回 label 字符串。"""
    if isinstance(label, str):
        return label
    m = label.get("material", "PG")
    sec = str(label.get("section", ""))
    seq = str(label.get("seq", "")).zfill(2) if label.get("seq") is not None else ""
    dn = str(label.get("dn", ""))
    grade = label.get("grade", "")
    ins = label.get("insulation", "")
    s = f"{m} {sec} {seq}-{dn}"
    if grade:
        s += f" {grade}"
    if ins:
        s += f" {ins}"
    return s


def add_pipe_label(doc, text, x, y, vertical=False, h=3.5):
    if vertical:
        # 竖管：标注在管线左侧，留出流股号圆圈(半径3)的位置
        cad.add_text(doc, (x - h * 3.0, y), h, text, "PFD-TEXT", rotation=90.0, align="middle")
    else:
        cad.add_text(doc, (x, y + h * 1.4), h, text, "PFD-TEXT", align="center")
    return (x, y)


def add_stream_number(doc, number, x, y, r=3.5):
    """流股编号：细实线小圆圈内写数字（PFD 惯例）。圆圈骑在线上，
    管线由调用方在圆圈两侧断开留缺口——不用白色遮罩（ACI 255 填充在
    AutoCAD 深色背景下会把 ACI 7 数字盖成一片实心白点，数字不可读）。"""
    cad.add_circle(doc, (x, y), r, "PFD-TEXT", 25)
    cad.add_text(doc, (x, y), r * 1.1, str(number), "PFD-TEXT", align="middle")
    return (x, y)


def add_arrow(doc, tip, direction_deg, length=6.0, half_width=2.2, layer="PFD-PIPE-MAIN"):
    """物流方向实心箭头：tip 为箭尖，direction 为流向角（度）。"""
    a = math.radians(direction_deg)
    dx, dy = math.cos(a), math.sin(a)
    px, py = -dy, dx
    base = (tip[0] - dx * length, tip[1] - dy * length)
    pts = [((base[0] + px * half_width), (base[1] + py * half_width)),
           ((base[0] - px * half_width), (base[1] - py * half_width)),
           tip]
    cad.add_solid_tri(doc, pts, layer, 25)
    return tip


def add_stream_connector(doc, text, x, y, flow_dir=1, label="", L=20.0, h=5.0, pipe_len=12.0):
    """管道进/出图纸符号（标准图例第9页）：平头端在 (x,y)，尖头端朝流向(flow_dir=±1)，
    框内写管线号(如 0210-3)，尖头后接短线；label(来自T-201/至E-206)写在短线上方。
    返回短线末端坐标（可与管道端点重合）。"""
    d = 1 if flow_dir >= 0 else -1
    if d > 0:
        pts = [(x, y - h / 2), (x + L - h, y - h / 2), (x + L, y),
               (x + L - h, y + h / 2), (x, y + h / 2), (x, y - h / 2)]
        tip = (x + L + pipe_len, y)
        cad.add_line(doc, (x + L, y), tip, "PFD-PIPE-AUX", 25)
    else:
        pts = [(x, y - h / 2), (x - L + h, y - h / 2), (x - L, y),
               (x - L + h, y + h / 2), (x, y + h / 2), (x, y - h / 2)]
        tip = (x - L - pipe_len, y)
        cad.add_line(doc, (x - L, y), tip, "PFD-PIPE-AUX", 25)
    cad.add_polyline(doc, pts, "PFD-PIPE-AUX", 25)
    cad.add_text(doc, (x + d * L / 2, y), h * 0.72, str(text), "PFD-TEXT", align="middle")
    if label:
        cad.add_text(doc, ((x + tip[0]) / 2, y + h * 1.3), 3.5, str(label), "PFD-TEXT", align="middle")
    return tip


# ================================================================ 物料表（PFD 图下方表格）
TABLE_ROWS = [
    ("温度 ℃", lambda s: _fmt(s.get("T"))),
    ("压力 MPa", lambda s: _fmt(s.get("P"))),
    ("汽相分率", lambda s: _fmt(s.get("vap"))),
    ("摩尔流率 kmol/h", lambda s: _fmt(s.get("mol"))),
    ("总质量流率 kg/h", lambda s: _fmt(s.get("mass"))),
]


def _fmt(v, nd=2):
    if v is None:
        return ""
    return f"{float(v):.{nd}f}"


def draw_material_table(doc, x, y, streams, components=None,
                        col_w=26.0, row_h=8.0, th=3.5, label_w=48.0):
    """x,y 为表格左下角。streams: [{no,T,P,vap,mol,mass,comp:{名称:kg/h}}...]
    rows: 物流代号/温度℃/压力MPa/汽相分率/摩尔流率kmol/h/总质量流率kg/h/各组分质量流量。"""
    if components is None:
        seen = []
        for s in streams:
            for k in (s.get("comp") or {}):
                if k not in seen:
                    seen.append(k)
        components = seen
    n_cols = len(streams) + 1
    rows = [("物流代号", [str(s.get("no", i + 1)) for i, s in enumerate(streams)])]
    for label, fn in TABLE_ROWS:
        rows.append((label, [fn(s) for s in streams]))
    for comp in components:
        rows.append((f"{comp} kg/h", [_fmt((s.get("comp") or {}).get(comp)) for s in streams]))
    n_rows = len(rows)
    W, H = label_w + (n_cols - 1) * col_w, n_rows * row_h
    xs = [x, x + label_w] + [x + label_w + j * col_w for j in range(1, n_cols)]
    # 网格
    for i in range(n_rows + 1):
        yy = y + i * row_h
        lw = 50 if i == n_rows else 25
        cad.add_line(doc, (x, yy), (x + W, yy), "PFD-TABLE", lw)
    for xx in xs:
        cad.add_line(doc, (xx, y), (xx, y + H), "PFD-TABLE", 25)
    # 文字
    for i, (label, vals) in enumerate(rows):
        yy = y + H - (i + 0.5) * row_h
        cad.add_text(doc, (x + 2.0, yy), th, label, "PFD-TABLE", align="left")
        for j, v in enumerate(vals):
            cad.add_text(doc, (xs[j + 2] - 2.0, yy), th, v, "PFD-TABLE", align="right")
    return {"x": x, "y": y, "width": W, "height": H}


def draw_equipment_table(doc, x, y, entries, width=740.0, h=5.0, row_pitch=15.0,
                         per_row=None, gap=16.0):
    """设备位号-名称一览（图例式，无框线，与图中设备标注同款式）：
    每项 = 位号(上) + 短横线 + 名称(下)，自左向右排，超过 width 自动换行；
    per_row 指定每项数时按行均分——项与项之间留空格、布满整行宽。
    x,y 为首行位号基线左端。返回占据矩形。"""
    entries = [e for e in entries if e[0]]
    if not entries:
        return None
    xr = x + width
    placed = []
    if per_row:
        slot = width / float(per_row)
        for k, (tag, name) in enumerate(entries):
            w = max(_tw(str(tag), h), _tw(str(name), h)) + gap
            r, c = k // per_row, k % per_row
            placed.append((r, x + c * slot + slot / 2.0, tag, name, w))
        nrows = max(1, (len(entries) + per_row - 1) // per_row)
    else:
        nrows = 1
        cx = x
        for tag, name in entries:
            w = max(_tw(str(tag), h), _tw(str(name), h)) + gap
            if cx + w > xr and placed:
                nrows += 1
                cx = x
            placed.append((nrows - 1, cx + w / 2.0, tag, name, w))
            cx += w
    for r, cxx, tag, name, w in placed:
        yr = y - r * row_pitch
        cad.add_text(doc, (cxx, yr), h, str(tag), "PFD-TABLE", align="middle")
        cad.add_line(doc, (cxx - w / 2.0, yr - 1.8), (cxx + w / 2.0, yr - 1.8),
                     "PFD-TABLE", 25)
        cad.add_text(doc, (cxx, yr - 7.0), h, str(name), "PFD-TABLE", align="middle")
    return (x, y - nrows * row_pitch - h, xr, y + h)
