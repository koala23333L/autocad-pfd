# -*- coding: utf-8 -*-
"""autocad-pfd MCP 服务器：通过 COM 驱动本机 AutoCAD 绘制 HG/T 20519 规范的化工 PFD 图。

工具分三层：
1) 文档级：autocad_status / new_drawing / draw_frame / save_drawing / export_drawing
2) 图元级：add_equipment / add_pipe / add_valve / add_instrument / add_text /
   add_equipment_tag / add_stream_number / add_heat_load / draw_material_table
3) 一次成图：draw_pfd（JSON 规格：设备+管道+阀门+仪表+物料表+标题栏）
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cad  # noqa: E402
import layout_check  # noqa: E402
import sheets  # noqa: E402
import standards as std  # noqa: E402
import symbols  # noqa: E402

from mcp.server.mcpserver import MCPServer  # noqa: E402

mcp = MCPServer(
    "autocad-pfd",
    instructions=(
        "绘制化工 PFD 的推荐流程：写好 spec 后先 check_pfd_layout(spec) 预检（errors 必须清零），"
        "再 draw_pfd(spec) 一次成图（成图前会自动再跑同一套预检，带硬伤会拒绝并返回违规清单）。"
        "也可逐步：new_drawing(frame='A0') → draw_frame(...) → add_equipment(...) 记录返回的 ports → "
        "add_pipe(points=[端口坐标...], kind='main'/'aux', label=..., stream_no=...) → add_valve / add_instrument → "
        "add_equipment_tag → draw_material_table → save_drawing + export_drawing(png/pdf) 供用户查看。"
        "单位 mm，模型空间 1:1。设备符号、标注、底部设备一览等全部规范见插件 SKILL.md 的红线清单。"
    ),
)

# 会话内状态：文档名 -> {"equipment": {tag: {...}}, "pipes": [points]}
_STATE = {}


def _doc(create=False):
    app = cad.get_app(create=create)
    doc = cad.active_doc(app)
    if doc is None:
        doc = cad.new_document(app)
    cad.ensure_layers(doc)
    return app, doc, doc.Name


def _st(doc_name):
    return _STATE.setdefault(doc_name, {"equipment": {}, "pipes": []})


# ================================================================ 文档级
@mcp.tool()
def autocad_status() -> dict:
    """查询本机 AutoCAD 是否在运行、版本与当前文档。不启动 AutoCAD。"""
    with cad.lock():
        try:
            app = cad.get_app(create=False)
        except Exception as e:
            return {"running": False, "detail": str(e)}
        try:
            ver = app.Version
        except Exception:
            ver = "?"
        doc = cad.active_doc(app)
        return {"running": True, "version": ver,
                "document": (doc.Name if doc else None),
                "model_space_count": (doc.ModelSpace.Count if doc else 0)}


@mcp.tool()
def new_drawing(frame: str = "A0") -> dict:
    """新建（或复用运行中的）AutoCAD 并创建公制文档、标准图层与工程字样式。
    AutoCAD 未运行时会启动它，可能需要 1-2 分钟。frame 仅用于返回绘图范围建议。
    返回 {document, inner_area: 图框内可用区(x1,y1,x2,y2)}。"""
    with cad.lock():
        app = cad.get_app(create=True)
        doc = cad.new_document(app)
        cad.ensure_layers(doc)
        W, H, e, c, a = std.PAPER_SIZES.get(frame, std.PAPER_SIZES["A0"])
        return {"document": doc.Name, "frame": frame,
                "sheet_mm": [W, H],
                "inner_area": [a + 8, e + 8, W - e - 8, H - e - 8],
                "tip": std.EQUIP_TAG_HELP}


@mcp.tool()
def draw_frame(size: str = "A0", fields: dict | None = None) -> dict:
    """绘制 X 型图框（含装订边，表4 尺寸）与简化标题栏。
    fields: {project_name 工程名称, drawing_name 图名(默认 工艺物料流程图(PFD)),
    drawing_no 图号, unit_name 设计院/单位, designer 设计, checker 审核,
    approver 批准, date 日期, phase 阶段}。注意：标题栏设计/审核/批准不能填同一人。"""
    with cad.lock():
        app, doc, name = _doc(create=True)
        r = sheets.draw_frame(doc, size, fields or {})
        cad.zoom_extents(doc)
        return r


@mcp.tool()
def save_drawing(path: str | None = None) -> dict:
    """保存当前文档。path 为 .dwg 完整路径；缺省则原位保存。"""
    with cad.lock():
        app, doc, _ = _doc()
        if path:
            doc.SaveAs(os.path.abspath(path))
        else:
            doc.Save()
        return {"saved": doc.FullName if hasattr(doc, "FullName") else doc.Name}


@mcp.tool()
def export_drawing(png_path: str | None = None, pdf_path: str | None = None) -> dict:
    """将当前图形按范围(Extents)满幅导出为 PNG / PDF（含线宽）。返回生成的文件路径。"""
    with cad.lock():
        app, doc, _ = _doc()
        out = {}
        if png_path:
            ok, p = cad.export_png(doc, png_path)
            out["png"] = p if ok else None
        if pdf_path:
            ok, p = cad.export_pdf(doc, pdf_path)
            out["pdf"] = p if ok else None
        return out


@mcp.tool()
def run_command(command: str) -> str:
    """向 AutoCAD 命令行发送原生命令（高级调试用），如 '_ZOOM _E '。返回模型空间对象数。"""
    with cad.lock():
        app, doc, _ = _doc()
        doc.SendCommand(command if command.endswith(" ") else command + " ")
        return f"sent; entities={doc.ModelSpace.Count}"


# ================================================================ 图元级
@mcp.tool()
def add_equipment(kind: str, tag: str = "", name: str = "", x: float = 0, y: float = 0,
                  size: float | None = None, rotation: float = 0.0,
                  options: dict | None = None, label: bool = True) -> dict:
    """按 PFD 图例绘制设备并登记位号。kind: pump/compressor/blower/heat_exchanger/column/
    vessel/reactor/fired_heater/separator/storage_tank/mixer（list_equipment_kinds 查详情）。
    size=主要尺寸mm(塔为总高)；options 例 {"internals":"tray|packing","n_trays":12,"horizontal":true}。
    label=True 时在设备上方自动标注 位号/名称（粗实线分隔）。
    返回 ports：各接口的世界坐标，用于 add_pipe 连接。"""
    with cad.lock():
        app, doc, dn = _doc(create=True)
        r = symbols.draw_equipment(doc, kind, float(x), float(y), size, float(rotation), options)
        if tag:
            e1 = r["ext"]
            _st(dn)["equipment"][tag] = {"kind": kind, "x": float(x), "y": float(y),
                                         "rotation": float(rotation),
                                         "size": r["size"], "ports": r["ports"],
                                         "rect": (float(x) + e1[0], float(y) + e1[1],
                                                  float(x) + e1[2], float(y) + e1[3])}
            if label:
                h = std.TEXT_HEIGHTS["digit"]
                lxy = (options or {}).get("label_xy") or [float(x), float(y) + r["ext"][3] + 12]
                sheets.add_equipment_tag(doc, tag, name or std.EQUIPMENT_CODES.get(tag[0], ""),
                                         float(lxy[0]), float(lxy[1]))
        return {"kind": kind, "tag": tag, "size": r["size"], "ports": r["ports"]}


def _polyline_with_circle_gap(doc, pts, layer, lw, li, mx, my, r=3.5):
    """画管线折线，但在第 li 段的 (mx,my) 处断开留缺口（流股号圆圈骑在线上，
    缺口半径 r+1.5）——替代白色遮罩，深色/浅色背景下数字均可读。"""
    a, b = pts[li], pts[li + 1]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 2 * (r + 1.0):
        cad.add_polyline(doc, [list(p) for p in pts], layer, lw)
        return
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    g = r + 1.5
    c1 = [mx - ux * g, my - uy * g]
    c2 = [mx + ux * g, my + uy * g]
    cad.add_polyline(doc, [list(p) for p in pts[:li + 1]] + [c1], layer, lw)
    cad.add_polyline(doc, [c2] + [list(p) for p in pts[li + 1:]], layer, lw)


@mcp.tool()
def add_pipe(points: list, kind: str = "main", stream_no: int | None = None,
             label: dict | str | None = None, arrow: bool = True,
             vertical_label: bool | None = None) -> dict:
    """绘制管道折线。points=[[x,y],...]（用 add_equipment 返回的 ports 连接）。
    kind: main 主物料(粗1.0mm)/aux 辅助(中0.5)/utility 公用。
    stream_no: 在最长段中点画流股号圆圈（管线断开留缺口）；label: 管道标注 dict
    {material 物料代号,section 主项,seq 分段号,dn 管径mm,grade 等级,insulation 隔热}
    或字符串。横向管道标注在上方，竖向在左侧（vertical_label 可强制）。"""
    with cad.lock():
        app, doc, dn = _doc(create=True)
        pts = [(float(a), float(b)) for a, b in points]
        if len(pts) < 2:
            raise ValueError("points 至少 2 个")
        layer = {"main": "PFD-PIPE-MAIN", "aux": "PFD-PIPE-AUX", "utility": "PFD-PIPE-AUX"}[kind]
        lw = std.LINE_WEIGHTS.get(kind, 50)
        total = 0.0
        segs = []
        for i in range(len(pts) - 1):
            d = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            segs.append(d)
            total += d
        # 标注位置：最长段中点
        li = max(range(len(segs)), key=lambda i: segs[i]) if segs else 0
        mx = (pts[li][0] + pts[li + 1][0]) / 2 if segs else pts[0][0]
        my = (pts[li][1] + pts[li + 1][1]) / 2 if segs else pts[0][1]
        vertical = vertical_label if vertical_label is not None else (segs and abs(pts[li + 1][1] - pts[li][1]) > abs(pts[li + 1][0] - pts[li][0]))
        if stream_no is not None:
            _polyline_with_circle_gap(doc, pts, layer, lw, li, mx, my)
        else:
            cad.add_polyline(doc, pts, layer, lw)
        if arrow and total > 0:
            x1, y1 = pts[-2]
            x2, y2 = pts[-1]
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            sheets.add_arrow(doc, (x2, y2), ang, layer=layer)
        if stream_no is not None:
            sheets.add_stream_number(doc, stream_no, mx, my, r=3.5)
        if label is not None:
            if vertical:
                sheets.add_pipe_label(doc, sheets.pipe_tag_text(label), mx, my + 14, vertical=True)
            else:
                sheets.add_pipe_label(doc, sheets.pipe_tag_text(label), mx,
                                      my + (14 if stream_no is None else 16), vertical=False)
        _st(dn)["pipes"].append(pts)
        return {"length_mm": round(total, 1), "label_at": [round(mx, 1), round(my, 1)]}


@mcp.tool()
def add_valve(kind: str, x: float, y: float, rotation: float = 0.0, size: float = 6.0) -> dict:
    """在管道上画阀门（细线，符号中心在 x,y）。kind 见 list_valve_kinds：
    gate 闸阀/globe 截止阀/check 止回阀/ball 球阀/butterfly 蝶阀/throttle 节流阀/
    reducing 减压阀/control 调节阀(气动薄膜执行机构)/safety 安全阀/foot 底阀/
    needle 针型阀/plug 旋塞/diaphragm 隔膜阀。
    rotation 与管道走向一致（0=水平管，90=立管）。size≈半宽 mm。
    批量成图时在管道 valves 里用 {"kind":.., "at_xy":[x,y]} 按坐标放阀（自动吸附到管线）。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        return symbols.draw_valve(doc, kind, float(x), float(y), float(rotation), float(size))


@mcp.tool()
def add_instrument(letters: str, number: str, x: float, y: float, mount: str = "field",
                   signal: str = "mechanical", connect_to: list | None = None,
                   dia: float = 8.0) -> dict:
    """仪表符号：小圆圈，上半=检测参数+功能字母(如 FTIC：F流量 T温度 I指示 C控制)，
    下半=仪表位号数字(如 1001)。mount: field 就地/central 集中盘面/local 就地盘面/
    dcs 集散系统/plc。signal: mechanical 实线/pneumatic 虚线/electric 点划线，
    connect_to=[px,py] 为工艺管道测点。字母含义见 get_standards('instrument')。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        return symbols.draw_instrument(doc, letters, number, float(x), float(y),
                                       mount=mount, signal=signal,
                                       connect_to=tuple(connect_to) if connect_to else None,
                                       dia=float(dia))


@mcp.tool()
def add_equipment_tag(tag: str, name: str, x: float, y: float, above: bool = True) -> dict:
    """单独标注设备位号与名称：位号在上、粗实线、名称在下（或相反）。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        return {"at": sheets.add_equipment_tag(doc, tag, name, float(x), float(y), above)}


@mcp.tool()
def add_stream_number(number: int, x: float, y: float) -> dict:
    """流股编号小圆圈（与物料表物流代号一致）。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        return {"at": list(sheets.add_stream_number(doc, number, float(x), float(y)))}


@mcp.tool()
def add_stream_connector(text: str, x: float, y: float, flow_dir: int = 1,
                         label: str = "") -> dict:
    """管道进/出图纸符号（标准图例第9页）：尖头端框，框内写管线号(如 0210-3)，
    尖头朝物流方向(flow_dir=1 向右/-1 向左)，label 写"来自T-201"/"至E-206"。
    用于进出车间的管道或接至另一流程图的管道断开处。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        tip = sheets.add_stream_connector(doc, text, float(x), float(y),
                                          int(flow_dir), label)
        return {"tip": list(tip)}


@mcp.tool()
def add_heat_load(text: str, x: float, y: float) -> dict:
    """在换热/加热设备旁标注热量计算值，如 'Q=1250 kW'。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        cad.add_text(doc, (float(x), float(y)), 5.0, text, "PFD-TEXT", align="middle")
        return {"at": [x, y]}


@mcp.tool()
def add_text(text: str, x: float, y: float, height: float = 5.0,
             rotation: float = 0.0, align: str = "middle") -> dict:
    """工程字文本（GBCENT 样式：gbenor+gbcbig 长仿宋工程字）。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        cad.add_text(doc, (float(x), float(y)), float(height), text,
                     rotation=float(rotation), align=align)
        return {"at": [x, y]}


@mcp.tool()
def draw_material_table(streams: list, x: float = 100, y: float = 60,
                        components: list | None = None, col_w: float = 26.0,
                        row_h: float = 8.0, text_height: float = 3.5,
                        label_w: float = 48.0) -> dict:
    """PFD 物料平衡表（与图不可分，流股号与图中一致）。x,y=表格左下角。
    streams: [{"no":1,"T":20.0,"P":0.10,"vap":1.0,"mol":299.62,"mass":16520.0,
    "comp":{"正丁烷":330.4,...}}, ...]；行序：物流代号/温度℃/压力MPa/汽相分率/
    摩尔流率kmol/h/总质量流率kg/h/各组分质量流量kg/h。components 缺省取并集。"""
    with cad.lock():
        app, doc, _ = _doc(create=True)
        return sheets.draw_material_table(doc, float(x), float(y), streams,
                                          components, float(col_w), float(row_h),
                                          float(text_height), float(label_w))


# ================================================================ 组合工具
@mcp.tool()
def list_equipment_kinds() -> dict:
    """列出全部设备图例 kind、默认尺寸与接口(ports)说明。"""
    return {k: {"default_size": v[1], "desc": v[2]} for k, v in symbols.EQUIPMENT.items()}


@mcp.tool()
def list_valve_kinds() -> dict:
    """列出阀门图例 kind 与名称（表2-8）。"""
    return {k: v[1] for k, v in symbols.VALVES.items()}


@mcp.tool()
def get_standards(section: str = "all") -> dict:
    """查询规范常量。section: paper/line_weights/text_heights/equipment_codes/
    material_codes(物料代号表4-1)/pipe_grades/insulation/instrument(参数+功能代号)/mounts/all。"""
    d = {
        "paper": std.PAPER_SIZES, "line_weights": std.LINE_WEIGHTS,
        "text_heights": std.TEXT_HEIGHTS, "equipment_codes": std.EQUIPMENT_CODES,
        "material_codes": std.MATERIAL_CODES,
        "pipe_material": std.PIPE_MATERIAL_GRADE, "pipe_pressure": std.PIPE_PRESSURE_GRADE,
        "insulation": std.INSULATION_CODES,
        "instrument": {"measure": std.MEASURE_CODES, "function": std.FUNCTION_CODES},
        "mounts": std.INSTRUMENT_MOUNTS,
        "equip_tag_rule": std.EQUIP_TAG_HELP, "pipe_tag_rule": std.PIPE_TAG_HELP,
    }
    return d if section == "all" else {section: d.get(section, "未知 section，可选: " + ",".join(d))}


def _seg_hits_rect(p, q, r, pad=1.0):
    """线段-轴对齐矩形相交检测（Liang-Barsky）。"""
    x1, y1, x2, y2 = r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, dq in ((-dx, p[0] - x1), (dx, x2 - p[0]), (-dy, p[1] - y1), (dy, y2 - p[1])):
        if abs(pp) < 1e-9:
            if dq < 0:
                return False
        else:
            t = dq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def _route(p0, d0, p1, d1, obstacles=(), stub=12.0):
    """按端口出向自动正交走线，优先选择不穿越设备包围盒的候选路径。"""
    a = (p0[0] + d0[0] * stub, p0[1] + d0[1] * stub)
    b = (p1[0] + d1[0] * stub, p1[1] + d1[1] * stub)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    cands = [
        [p0, a, (b[0], a[1]), b, p1],                       # L 横先
        [p0, a, (a[0], b[1]), b, p1],                       # L 竖先
        [p0, a, (mx, a[1]), (mx, b[1]), b, p1],             # Z 竖中
        [p0, a, (a[0], my), (b[0], my), b, p1],             # Z 横中
        [p0, a, (a[0], max(a[1], b[1]) + 45), (b[0], max(a[1], b[1]) + 45), b, p1],  # 绕上
        [p0, a, (a[0], min(a[1], b[1]) - 45), (b[0], min(a[1], b[1]) - 45), b, p1],  # 绕下
        [p0, a, (max(a[0], b[0]) + 45, a[1]), (max(a[0], b[0]) + 45, b[1]), b, p1],  # 绕右
        [p0, a, (min(a[0], b[0]) - 45, a[1]), (min(a[0], b[0]) - 45, b[1]), b, p1],  # 绕左
    ]

    def clean(pts):
        return all(not _seg_hits_rect(s, e, r) for s, e in zip(pts, pts[1:]) for r in obstacles)

    chosen = next((c for c in cands if clean(c)), cands[2])
    out = []
    for p in chosen:
        p = [round(float(p[0]), 2), round(float(p[1]), 2)]
        if not out or (abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6):
            out.append(p)
    return out


def _point_on_polyline(pts, t):
    total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    target = total * t
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + d >= target or d == total:
            f = (target - acc) / d if d else 0
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), ang
        acc += d
    return (pts[-1][0], pts[-1][1]), 0.0


def _snap_on_polyline(pts, xy):
    """把任意坐标吸附到折线上最近点，返回 (吸附点, 该段角度)。
    供阀门用 at_xy 按绝对坐标定位——吸附保证阀门永远骑在管线上。"""
    x, y = float(xy[0]), float(xy[1])
    best = None
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            px, py, d = a[0], a[1], math.hypot(x - a[0], y - a[1])
        else:
            f = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
            px, py = a[0] + f * dx, a[1] + f * dy
            d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            ang = math.degrees(math.atan2(dy, dx))
            best = (d, (px, py), ang)
    return best[1], best[2]


@mcp.tool()
def _seg_rect(a, b, pad=3.0):
    """把已画管线段转成细长矩形，供后续自动走线避让。"""
    if abs(a[0] - b[0]) < 1e-6:
        return (a[0] - pad, min(a[1], b[1]) - pad, a[0] + pad, max(a[1], b[1]) + pad)
    return (min(a[0], b[0]) - pad, a[1] - pad, max(a[0], b[0]) + pad, a[1] + pad)


def _auto_layout(spec):
    """equipment 缺 x/y 时按给定顺序自动排布：自左向右流式排、行满换行（A0）。
    行基线=该行设备包围盒顶缘（自上而下堆叠），只做首次布局，精调由调用方微调。"""
    eqs = spec.get("equipment", [])
    if not any("x" not in e or "y" not in e for e in eqs):
        return
    from unittest.mock import MagicMock
    doc = MagicMock()
    cursor_x, row_top, row_h = 80.0, 780.0, 0.0
    for e in eqs:
        try:
            r = symbols.draw_equipment(doc, e["kind"], 0, 0, e.get("size"),
                                       float(e.get("rotation", 0)), e.get("options"))
            ext = r["ext"]
        except Exception:
            half = e.get("size", 40) / 2.0
            ext = (-half, -half, half, half)
        w, h = ext[2] - ext[0], ext[3] - ext[1]
        if cursor_x + w > 1120.0 and cursor_x > 80.0:   # 行满换行
            cursor_x = 80.0
            row_top -= row_h + 130.0
            row_h = 0.0
        e["x"] = cursor_x - ext[0] + w / 2.0
        e["y"] = row_top - ext[3]                       # 包围盒顶缘对齐 row_top
        cursor_x = e["x"] + ext[2] + 60.0
        row_h = max(row_h, h)


def _auto_number(spec):
    """auto_stream_no=True 时给未编号的主物料管线按顺序补流股号（从现有最大号+1 起）。"""
    if not spec.get("auto_stream_no"):
        return
    mains = [p for p in spec.get("pipes", []) if p.get("kind", "main") == "main"]
    nxt = 1 + max([p["stream_no"] for p in mains if p.get("stream_no") is not None] or [0])
    for p in mains:
        if p.get("stream_no") is None:
            p["stream_no"] = nxt
            nxt += 1


def draw_pfd(spec: dict) -> dict:
    """一次性绘制整张 PFD。spec:
    {
      "frame": "A0",
      "title": {project_name, drawing_name, drawing_no, unit_name, designer, checker, approver, date},
      "equipment": [{kind, tag, name, x, y, size, rotation, options}],
      "pipes": [{from:[tag,port], to:[tag,port], via:[[x,y],...](可选,给出则按此走线),
                 kind:"main|aux", stream_no, label:{material,section,seq,dn,grade,insulation},
                 valves:[{kind, at:0~1 沿线位置}]}],
      "instruments": [{letters, number, x, y, mount, signal, connect_to:[x,y]}],
      "heat_loads": [{text, x, y}],
      "table": {x, y, streams:[...], col_w, row_h},
      "texts": [{text, x, y, height, rotation}],
      "save_as": "C:\\\\out.dwg", "export_png": "C:\\\\out.png", "export_pdf": "C:\\\\out.pdf"
    }
    设备端口方向自动正交走线。返回 {drawn:{equipment,pipes,...}, warnings}。

    成图前自动执行布局预检（layout_check.check_spec）：管线穿设备/文字压线压设备/
    悬空接管/斜线/出图框/入标题栏等硬伤存在时**拒绝成图**并抛出完整违规清单——
    按清单修正 spec 后重试即可；warnings（端点悬空/假T）随返回值带回。"""
    _auto_layout(spec)   # 缺坐标的设备自动排布（已有坐标不动）
    errs, warns = [], []
    try:
        errs, warns = layout_check.check_spec(spec)
    except Exception as _e:  # 预检器自身异常不阻塞成图
        warns.append("布局预检器异常(已跳过): %r" % (_e,))
    if errs:
        raise RuntimeError("spec 布局自检未通过，未成图。共 %d 项硬伤：\n" % len(errs)
                           + "\n".join(" - " + e for e in errs))
    if spec.get("auto_stream_no"):
        _auto_number(spec)
    with cad.lock():
        app, doc, dn = _doc(create=True)
        if not spec.get("append"):
            # 一次性成图：默认新建空白文档，避免把图形画进用户正在编辑的图纸。
            # 新文档建图层偶发 COM 竞态（Add.color 拒绝），关掉重建最多重试 3 次。
            import time as _time
            for _try in range(3):
                try:
                    doc = cad.new_document(app)
                    cad.ensure_layers(doc)
                    break
                except Exception as _e:
                    try:
                        doc.Close(False)
                    except Exception:
                        pass
                    if _try == 2:
                        raise
                    _time.sleep(1.5)
            dn = doc.Name
        warnings = []
        frame = spec.get("frame", "A0")
        if spec.get("title") or spec.get("draw_frame", True):
            sheets.draw_frame(doc, frame, spec.get("title"))
        drawn = {"equipment": [], "pipes": 0, "valves": 0, "instruments": 0}
        eq_state = _st(dn)["equipment"]
        for eq in spec.get("equipment", []):
            r = symbols.draw_equipment(doc, eq["kind"], float(eq.get("x", 0)), float(eq.get("y", 0)),
                                       eq.get("size"), float(eq.get("rotation", 0)), eq.get("options"))
            tag = eq.get("tag", "")
            if tag:
                e1 = r["ext"]
                rot = float(eq.get("rotation", 0))
                if abs(rot - 90) < 1e-6 or abs(rot + 270) < 1e-6:
                    wrect = (float(eq.get("x", 0)) - e1[3], float(eq.get("y", 0)) + e1[0],
                             float(eq.get("x", 0)) - e1[1], float(eq.get("y", 0)) + e1[2])
                elif abs(rot - 180) < 1e-6 or abs(rot + 180) < 1e-6:
                    wrect = (float(eq.get("x", 0)) - e1[2], float(eq.get("y", 0)) - e1[3],
                             float(eq.get("x", 0)) - e1[0], float(eq.get("y", 0)) - e1[1])
                else:
                    wrect = (float(eq.get("x", 0)) + e1[0], float(eq.get("y", 0)) + e1[1],
                             float(eq.get("x", 0)) + e1[2], float(eq.get("y", 0)) + e1[3])
                eq_state[tag] = {"kind": eq["kind"], "x": float(eq.get("x", 0)), "y": float(eq.get("y", 0)),
                                 "rotation": rot, "size": r["size"], "ports": r["ports"],
                                 "port_dir": r.get("port_dir", {}), "rect": wrect}
                h = std.TEXT_HEIGHTS["digit"]
                lxy = eq.get("label_xy") or [float(eq.get("x", 0)),
                                             float(eq.get("y", 0)) + r["ext"][3] + 12]
                sheets.add_equipment_tag(doc, tag, eq.get("name", ""),
                                         float(lxy[0]), float(lxy[1]))
            drawn["equipment"].append(tag or eq["kind"])
        for pipe in spec.get("pipes", []):
            def resolve(end):
                if len(end) == 2 and isinstance(end[0], (int, float)) and isinstance(end[1], (int, float)):
                    # 原始坐标（图纸边界进出线）：出向默认指向远离目标
                    return (float(end[0]), float(end[1])), None
                tag, port = end[0], end[1]
                e = eq_state.get(tag)
                if not e:
                    raise ValueError(f"未登记设备 {tag}（先放 equipment）")
                p = e["ports"].get(port)
                if not p:
                    raise ValueError(f"设备 {tag} 无接口 {port}，可选: {list(e['ports'])}")
                d = e.get("port_dir", {}).get(port)
                if d is None:
                    d = (p[0] - e["x"], p[1] - e["y"])
                    n = math.hypot(*d) or 1.0
                    d = (d[0] / n, d[1] / n)
                return p, d
            p0, d0 = resolve(pipe["from"])
            p1, d1 = resolve(pipe["to"])
            if d0 is None:
                d0 = (1.0 if p1[0] >= p0[0] else -1.0, 0.0)
            if d1 is None:
                d1 = (1.0 if p0[0] >= p1[0] else -1.0, 0.0)
            obstacles = [e["rect"] for t, e in eq_state.items()
                         if t not in (pipe["from"][0], pipe["to"][0]) and "rect" in e]
            # 自动走线时避让已画管线（细长矩形障碍），避免交叉穿行
            obstacles = obstacles + [_seg_rect(a, b) for pl in _st(dn)["pipes"]
                                     for a, b in zip(pl, pl[1:])]
            pts = [list(map(float, q)) for q in pipe["via"]] if pipe.get("via") else _route(p0, d0, p1, d1, obstacles)
            if pts[0] != [p0[0], p0[1]]:
                pts.insert(0, [p0[0], p0[1]])
            if pts[-1] != [p1[0], p1[1]]:
                pts.append([p1[0], p1[1]])
            layer = {"main": "PFD-PIPE-MAIN", "aux": "PFD-PIPE-AUX", "utility": "PFD-PIPE-AUX"}.get(pipe.get("kind", "main"), "PFD-PIPE-AUX")
            lw = std.LINE_WEIGHTS.get(pipe.get("kind", "main"), 50)
            segs = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
            li = max(range(len(segs)), key=lambda i: segs[i])
            mx = (pts[li][0] + pts[li + 1][0]) / 2
            my = (pts[li][1] + pts[li + 1][1]) / 2
            vertical = abs(pts[li + 1][1] - pts[li][1]) > abs(pts[li + 1][0] - pts[li][0])
            if pipe.get("stream_no") is not None:
                _polyline_with_circle_gap(doc, pts, layer, lw, li, mx, my)
            else:
                cad.add_polyline(doc, pts, layer, lw)
            ang = math.degrees(math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0]))
            sheets.add_arrow(doc, (pts[-1][0], pts[-1][1]), ang, layer=layer)
            if pipe.get("stream_no") is not None:
                sheets.add_stream_number(doc, pipe["stream_no"], mx, my)
            if pipe.get("label") is not None:
                if vertical:
                    # 竖管：标注放管线左侧，并沿管线偏移避开流股号圆圈
                    sheets.add_pipe_label(doc, sheets.pipe_tag_text(pipe["label"]), mx, my + 14,
                                          vertical=True)
                else:
                    sheets.add_pipe_label(doc, sheets.pipe_tag_text(pipe["label"]), mx,
                                          my + (14 if pipe.get("stream_no") is None else 16),
                                          vertical=False)
            for v in pipe.get("valves", []):
                if v.get("at_xy") is not None:
                    (vx, vy), vang = _snap_on_polyline(pts, v["at_xy"])
                else:
                    (vx, vy), vang = _point_on_polyline(pts, float(v.get("at", 0.5)))
                if v["kind"] in symbols.SYM_VALVES:
                    vang %= 180.0  # 对称阀体：执行机构/阀杆恒朝上(横管)或朝左(立管)
                symbols.draw_valve(doc, v["kind"], vx, vy, vang, float(v.get("size", 6)))
                drawn["valves"] += 1
            _st(dn)["pipes"].append(pts)
            drawn["pipes"] += 1
        for ins in spec.get("instruments", []):
            symbols.draw_instrument(doc, ins["letters"], str(ins["number"]), float(ins["x"]), float(ins["y"]),
                                    mount=ins.get("mount", "field"), signal=ins.get("signal", "mechanical"),
                                    connect_to=tuple(ins["connect_to"]) if ins.get("connect_to") else None)
            drawn["instruments"] += 1
        for hl in spec.get("heat_loads", []):
            cad.add_text(doc, (float(hl["x"]), float(hl["y"])), 5.0, hl["text"], "PFD-TEXT", align="middle")
        for cn in spec.get("connectors", []):
            sheets.add_stream_connector(doc, str(cn["text"]), float(cn["x"]), float(cn["y"]),
                                        int(cn.get("flow_dir", 1)), str(cn.get("label", "")))
        et = spec.get("equipment_table")
        if et:
            entries = [(eq.get("tag", ""), eq.get("name", ""))
                       for eq in spec.get("equipment", []) if eq.get("tag")]
            sheets.draw_equipment_table(doc, float(et.get("x", 60)), float(et.get("y", 96)),
                                        entries, width=float(et.get("width", 740)),
                                        per_row=et.get("per_row"))
        tb = spec.get("table")
        if tb:
            sheets.draw_material_table(doc, float(tb.get("x", 100)), float(tb.get("y", 60)),
                                       tb["streams"], tb.get("components"),
                                       float(tb.get("col_w", 26)), float(tb.get("row_h", 8)),
                                       float(tb.get("text_height", 3.5)), float(tb.get("label_w", 48)))
        for t in spec.get("texts", []):
            cad.add_text(doc, (float(t["x"]), float(t["y"])), float(t.get("height", 5.0)),
                         t["text"], "PFD-TEXT", float(t.get("rotation", 0)), t.get("align", "middle"))
        cad.zoom_extents(doc)
        result = {"drawn": drawn, "warnings": warnings, "document": doc.Name}
        if spec.get("save_as"):
            try:
                doc.SaveAs(os.path.abspath(spec["save_as"]))
            except Exception:
                # 同名文件已在 AutoCAD 中打开 → 关闭它再存
                target = os.path.basename(os.path.abspath(spec["save_as"])).lower()
                for i in range(app.Documents.Count - 1, -1, -1):
                    d2 = app.Documents.Item(i)
                    try:
                        if os.path.basename(str(d2.Name)).lower() == target and d2 is not doc:
                            d2.Close(False)
                    except Exception:
                        pass
                doc.SaveAs(os.path.abspath(spec["save_as"]))
            result["saved"] = spec["save_as"]
        import time as _time
        for kind, fn in (("export_png", cad.export_png), ("export_pdf", cad.export_pdf)):
            path = spec.get(kind)
            if not path:
                continue
            ok, p = False, None
            for _try in range(3):   # 新文档 Layouts 偶发 COM 竞态，重试
                try:
                    ok, p = fn(doc, path)
                    break
                except Exception as e:
                    if _try == 2:
                        warnings.append(f"{kind} 导出失败: {e}")
                    else:
                        _time.sleep(2.0)
            if kind == "export_png":
                result["png"] = p if ok else None
            else:
                result["pdf"] = p if ok else None
        if warns:
            result["layout_warnings"] = warns
        result["layout_check"] = "PASS" if not warns else "PASS_WITH_WARNINGS"
        return result


@mcp.tool()
def list_references() -> dict:
    """列出插件参考资料目录（references/）：
    generated/ = 本 MCP 全部设备符号的成图总表（symbols_all.png，校验基准）；
    其余子目录 = 自备图例参考资料（设备图例扫描件/手册裁剪图等，放入后自动列出）。
    绘制不熟悉的设备前，先 Read 对应参考图核对画法，再写符号/规格。"""
    base = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "references"))
    catalog = {}
    if os.path.isdir(base):
        for d in sorted(os.listdir(base)):
            p = os.path.join(base, d)
            if os.path.isdir(p):
                catalog[d] = sorted(f for f in os.listdir(p) if not f.startswith("."))
    return {"base": base, "catalog": catalog}


@mcp.tool()
def check_pfd_layout(spec: dict) -> dict:
    """对 draw_pfd 的 spec 做布局预检（不连 AutoCAD、不画图）。
    errors=必须修复的硬伤：管线穿设备本体、文字压线/压设备/互压、悬空接管、
    斜线（管线必须正交）、出图框、入标题栏、管线闯入设备一览区、阀门落进设备；
    warnings=提醒：端点悬空（进出料建议标 来源/去向）、假 T 连接。
    成图前 errors 必须清零——draw_pfd 会在成图前自动跑同一套预检并拒绝带硬伤成图。"""
    errs, warns = layout_check.check_spec(spec)
    return {"ok": not errs, "errors": errs, "warnings": warns}


if __name__ == "__main__":
    mcp.run()
