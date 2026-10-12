# -*- coding: utf-8 -*-
"""PFD spec 布局自检（纯 Python 干跑，零 COM 依赖）。

draw_pfd 每次成图前自动调用 check_spec：errors 非空则拒绝成图并把清单抛给调用方；
warnings 随返回值带回提醒。红线全部来自历轮用户实拍指认：

  errors（一票否决）：
    1 管线穿设备本体           2 文字压线/压设备/文字互压
    3 画了没用的悬空接管       4 管线出图框
    5 管线/文字入标题栏        6 斜线（管线必须正交）
    7 管线闯入设备一览区
  warnings（提醒，不拦截）：
    8 端点悬空（进出料线未标去向时常见）  9 假 T 连接（端点搭在别的管线中段）
"""
import math
from unittest.mock import MagicMock

import symbols

FRAMES = {
    "A0": {"frame": (25, 20, 1169, 821), "title": (829, 20, 1169, 140)},
    "A1": {"frame": (25, 20, 829, 591), "title": (589, 20, 829, 110)},
    "A2": {"frame": (25, 20, 599, 431), "title": (429, 20, 599, 90)},
}


def _tw(txt, h):
    return sum(h if ord(c) > 0x2E80 else h * 0.62 for c in str(txt))


def _body_rect(kind, s, options):
    """设备本体矩形（不含接管凸出）。"""
    o = options or {}
    if kind == "column":
        W = max(0.2 * s, 14.0)
        return (-W / 2, -s / 2, W / 2, s / 2)
    if kind == "heat_exchanger":
        return (-1.15 * s, -s / 2, 1.15 * s, s / 2)
    if kind == "vessel":
        if o.get("horizontal"):
            return (-1.1 * s, -s / 2, 1.1 * s, s / 2)
        return (-0.25 * s, -s / 2, 0.25 * s, s / 2)
    if kind == "separator":
        return (-0.225 * s, -s / 2, 0.225 * s, s / 2)
    if kind == "mixer":
        # 矩形混合器壳体（HG/T 20519 混合机），接管短桩不算本体
        return (-0.85 * s, -0.8 * s, 0.85 * s, 0.8 * s)
    if kind == "reboiler":
        # 釜式再沸器本体=通道+釜体的公共包络（汽包顶/釜底以下的接管区不算本体）
        return (-s / 2, -0.16 * s, s / 2, 0.16 * s)
    if kind == "fixed_bed_reactor":
        return (-0.15 * s, -s / 2, 0.15 * s, s / 2)
    if kind == "decanter":
        return (-0.3 * s, -s / 2, 0.3 * s, s / 2)
    if kind == "cyclone":
        return (-0.25 * s, -s / 2, 0.25 * s, s / 2)
    if kind == "ejector":
        return (-0.5 * s, -0.18 * s, 0.5 * s, 0.18 * s)
    if kind == "air_cooler":
        return (-0.5 * s, -0.15 * s, 0.5 * s, 0.45 * s)
    if kind == "vacuum_pump":
        return (-0.5 * s, -0.5 * s, 0.5 * s, 0.5 * s)
    if kind == "flare_stack":
        return (-0.08 * s, -s / 2, 0.08 * s, 0.44 * s)
    if kind == "filter_press":
        return (-0.45 * s, -0.31 * s, 0.45 * s, 0.31 * s)
    if kind == "centrifuge":
        return (-0.275 * s, -0.5 * s, 0.275 * s, 0.5 * s)
    return None


def _rot_rect(ex, ey, ext, rot):
    rot = float(rot)
    if abs(rot - 90) < 1e-6 or abs(rot + 270) < 1e-6:
        return (ex - ext[3], ey + ext[0], ex - ext[1], ey + ext[2])
    if abs(rot - 180) < 1e-6 or abs(rot + 180) < 1e-6:
        return (ex - ext[2], ey - ext[3], ex - ext[0], ey - ext[1])
    return (ex + ext[0], ey + ext[1], ex + ext[2], ey + ext[3])


def _route(p0, d0, p1, d1, obstacles=(), stub=12.0):
    a = (p0[0] + d0[0] * stub, p0[1] + d0[1] * stub)
    b = (p1[0] + d1[0] * stub, p1[1] + d1[1] * stub)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    cands = [
        [p0, a, (b[0], a[1]), b, p1],
        [p0, a, (a[0], b[1]), b, p1],
        [p0, a, (mx, a[1]), (mx, b[1]), b, p1],
        [p0, a, (a[0], my), (b[0], my), b, p1],
        [p0, a, (a[0], max(a[1], b[1]) + 45), (b[0], max(a[1], b[1]) + 45), b, p1],
        [p0, a, (a[0], min(a[1], b[1]) - 45), (b[0], min(a[1], b[1]) - 45), b, p1],
        [p0, a, (max(a[0], b[0]) + 45, a[1]), (max(a[0], b[0]) + 45, b[1]), b, p1],
        [p0, a, (min(a[0], b[0]) - 45, a[1]), (min(a[0], b[0]) - 45, b[1]), b, p1],
    ]

    def _hit(s, e2, r):
        x1, y1, x2, y2 = r
        if max(s[0], e2[0]) < x1 or min(s[0], e2[0]) > x2 or max(s[1], e2[1]) < y1 or min(s[1], e2[1]) > y2:
            return False
        for p in (s, e2):
            if x1 < p[0] < x2 and y1 < p[1] < y2:
                return True
        pts = [s, e2]
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        for i in range(4):
            a1, a2 = corners[i], corners[(i + 1) % 4]
            if _ccw(s, e2, a1) * _ccw(s, e2, a2) < 0 and _ccw(a1, a2, s) * _ccw(a1, a2, e2) < 0:
                return True
        return False

    def _ccw(a1, a2, b1):
        return (a2[0] - a1[0]) * (b1[1] - a1[1]) - (a2[1] - a1[1]) * (b1[0] - a1[0])

    ok = [c for c in cands if all(not _hit(s, e2, r) for s, e2 in zip(c, c[1:]) for r in obstacles)]
    return (ok[0] if ok else cands[2]), True


def _seg_rect(a, b, pad=3.0):
    """把已画管线段转成细长矩形，供自动走线避让（与 server.draw_pfd 一致）。"""
    if abs(a[0] - b[0]) < 1e-6:
        return (a[0] - pad, min(a[1], b[1]) - pad, a[0] + pad, max(a[1], b[1]) + pad)
    return (min(a[0], b[0]) - pad, a[1] - pad, max(a[0], b[0]) + pad, a[1] + pad)


def _pt_on(pts, t):
    total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    target = total * t
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + d >= target or d == total:
            f = (target - acc) / d if d else 0
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        acc += d
    return (pts[-1][0], pts[-1][1])


def _snap(pts, xy):
    """坐标吸附到折线最近点（与 server._snap_on_polyline 一致，供阀门 at_xy）。"""
    x, y = float(xy[0]), float(xy[1])
    best = None
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            px, py = a[0], a[1]
        else:
            f = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
            px, py = a[0] + f * dx, a[1] + f * dy
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            best = (d, (px, py))
    return best[1]


def _seg_rect_hit(s, e, r, margin=0.0):
    x1, y1, x2, y2 = r[0] + margin, r[1] + margin, r[2] - margin, r[3] - margin
    if x2 <= x1 or y2 <= y1:
        return False
    if max(s[0], e[0]) < x1 or min(s[0], e[0]) > x2 or max(s[1], e[1]) < y1 or min(s[1], e[1]) > y2:
        return False

    def ccw(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    for j in range(4):
        a1, a2 = corners[j], corners[(j + 1) % 4]
        if ccw(s, e, a1) * ccw(s, e, a2) < 0 and ccw(a1, a2, s) * ccw(a1, a2, e) < 0:
            return True
    for p in (s, e):
        if x1 < p[0] < x2 and y1 < p[1] < y2:
            return True
    return False


def _dist_pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def check_spec(spec):
    """返回 (errors, warnings)，均为字符串清单。"""
    doc = MagicMock()
    eqs = {}
    for e in spec.get("equipment", []):
        try:
            r = symbols.draw_equipment(doc, e["kind"], float(e.get("x", 0)), float(e.get("y", 0)),
                                       e.get("size"), float(e.get("rotation", 0)), e.get("options"))
        except Exception as ex:  # 设备画不出来也是硬伤
            return (["设备 %s 绘制失败: %s" % (e.get("tag", e["kind"]), ex)], [])
        ext = r["ext"]
        wrect = _rot_rect(float(e.get("x", 0)), float(e.get("y", 0)), ext, e.get("rotation", 0))
        s_default = symbols.EQUIPMENT[e["kind"]][1]
        br = _body_rect(e["kind"], e.get("size") or s_default, e.get("options"))
        if br is None:
            br = ext
        ex_, ey_ = float(e.get("x", 0)), float(e.get("y", 0))
        eqs[e["tag"]] = {"ports": r["ports"], "port_dir": r.get("port_dir", {}),
                         "rect": wrect,
                         "body": (ex_ + br[0], ey_ + br[1], ex_ + br[2], ey_ + br[3]),
                         "nozzles": (e.get("options") or {}).get("nozzles"),
                         "label_xy": e.get("label_xy"), "tag": e["tag"],
                         "name": e.get("name", ""), "kind": e["kind"], "xy": (ex_, ey_)}

    errors, warnings = [], []

    def V(msg):
        errors.append(msg)

    def W(msg):
        warnings.append(msg)

    # ---- 管线折线 ----
    pipes = []
    for i, p in enumerate(spec.get("pipes", [])):
        def resolve(end):
            if len(end) == 2 and isinstance(end[0], (int, float)) and isinstance(end[1], (int, float)):
                return (float(end[0]), float(end[1])), None, None
            tag, port = end[0], end[1]
            e = eqs.get(tag)
            if not e:
                V("管线 p%d 引用未登记设备 %s" % (i, tag))
                return (0.0, 0.0), (1.0, 0.0), None
            pt = e["ports"].get(port)
            if not pt:
                V("设备 %s 无接口 %s（可选: %s）" % (tag, port, list(e["ports"])))
                return (0.0, 0.0), (1.0, 0.0), None
            d = e["port_dir"].get(port)
            if d is None:
                ddx, ddy = pt[0] - e["xy"][0], pt[1] - e["xy"][1]
                n = math.hypot(ddx, ddy) or 1.0
                ddx, ddy = ddx / n, ddy / n
                d = (round(ddx), round(ddy)) if abs(ddx) > 1e-9 and abs(ddy) > 1e-9 else (ddx, ddy)
                if abs(d[0]) > 0.5 and abs(d[1]) > 0.5:  # 兜底：按主轴取正交
                    d = (1.0 if d[0] > 0 else -1.0, 0.0) if abs(ddx) > abs(ddy) else (0.0, 1.0 if d[1] > 0 else -1.0)
            return pt, d, None
        p0, d0, _ = resolve(p["from"])
        p1, d1, _ = resolve(p["to"])
        if d0 is None:
            d0 = (1.0 if p1[0] >= p0[0] else -1.0, 0.0)
        if d1 is None:
            d1 = (1.0 if p0[0] >= p1[0] else -1.0, 0.0)
        obstacles = [e["rect"] for t, e in eqs.items()
                     if t not in (p["from"][0] if not isinstance(p["from"][0], (int, float)) else None,
                                  p["to"][0] if not isinstance(p["to"][0], (int, float)) else None)]
        # 自动走线避让已排管线（与 server.draw_pfd 一致）
        obstacles = obstacles + [_seg_rect(a, b) for qq in pipes
                                 for a, b in zip(qq["pts"], qq["pts"][1:])]
        if p.get("via"):
            pts = [[float(a), float(b)] for a, b in p["via"]]
        else:
            pts, _ = _route(p0, d0, p1, d1, obstacles)
        if pts[0] != [p0[0], p0[1]]:
            pts.insert(0, [p0[0], p0[1]])
        if pts[-1] != [p1[0], p1[1]]:
            pts.append([p1[0], p1[1]])
        valves = [_snap(pts, v["at_xy"]) if v.get("at_xy") is not None
                  else _pt_on(pts, float(v.get("at", 0.5))) for v in p.get("valves", [])]
        sn = None
        if p.get("stream_no") is not None:
            segs = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
            li = max(range(len(segs)), key=lambda k: segs[k])
            mx = (pts[li][0] + pts[li + 1][0]) / 2
            my = (pts[li][1] + pts[li + 1][1]) / 2
            sn = (mx, my)   # 流股号圆圈骑线（断线留缺口画法）
        pipes.append({"id": i, "pts": pts, "valves": valves, "sn": sn,
                      "kind": p.get("kind", "main")})

    # ---- 文字框清单 ----
    texts = []
    for t in spec.get("texts", []):
        h = float(t.get("height", 5.0))
        if h < 3.5:
            V("文字过小 %r height=%.1f（A0 图中文注释高度必须 ≥3.5mm，设备位号/名称 5mm）"
              % (t.get("text"), h))
        w = _tw(t.get("text", ""), h)
        texts.append((t["x"] - w / 2, t["y"] - h * 0.75, t["x"] + w / 2, t["y"] + h * 1.25,
                      "text:" + str(t.get("text"))))
    for tag, e in eqs.items():
        lx, ly = e["label_xy"] or [e["xy"][0], e["xy"][1]]
        h = 5.0
        w = max(_tw(tag, h), _tw(e["name"], h)) + h * 0.5
        texts.append((lx - w / 2, ly + h * 0.9, lx + w / 2, ly + h * 2.4, "tag:" + tag))
        texts.append((lx - w / 2, ly - h * 2.4, lx + w / 2, ly - h * 0.9, "name:" + tag))
        texts.append((lx - w / 2, ly - 0.6, lx + w / 2, ly + 0.6, "uline:" + tag))
    for ins in spec.get("instruments", []):
        texts.append((ins["x"] - 4, ins["y"] - 4, ins["x"] + 4, ins["y"] + 4,
                      "instr:" + str(ins.get("letters")) + "-" + str(ins.get("number"))))
    # ---- 仪表引线落点：必须在某条管线上或某台设备本体壁上（禁止悬空引线） ----
    for ins in spec.get("instruments", []):
        if not ins.get("connect_to"):
            continue
        c = (float(ins["connect_to"][0]), float(ins["connect_to"][1]))
        ok = False
        for pp in pipes:
            for a, b in zip(pp["pts"], pp["pts"][1:]):
                if _dist_pt_seg(c, a, b) <= 1.5:
                    ok = True
                    break
            if ok:
                break
        if not ok:
            for tag, e in eqs.items():
                x1, y1, x2, y2 = e["body"]
                edge = min(abs(c[0] - x1), abs(c[0] - x2), abs(c[1] - y1), abs(c[1] - y2))
                inside = x1 - 1.5 <= c[0] <= x2 + 1.5 and y1 - 1.5 <= c[1] <= y2 + 1.5
                if inside and edge <= 1.5:
                    ok = True
                    break
        if not ok:
            V("仪表 %s-%s 引线端点 (%g,%g) 悬空：不在任何管线或设备壁上（液位表接筒体直壁段，"
              "温度/压力/流量表接对应工艺管线）"
              % (ins.get("letters"), ins.get("number"), c[0], c[1]))
    for pp in pipes:
        if pp["sn"]:
            x, y = pp["sn"]
            texts.append((x - 3.5, y - 3.5, x + 3.5, y + 3.5,
                          "stream:%s@p%d" % (spec["pipes"][pp["id"]].get("stream_no"), pp["id"])))

    # ---- 仪表引线穿撞：引线（圆心→落点）不得穿过流股号圈/文字/其它仪表 ----
    for ins in spec.get("instruments", []):
        if not ins.get("connect_to"):
            continue
        a = (float(ins["x"]), float(ins["y"]))
        b = (float(ins["connect_to"][0]), float(ins["connect_to"][1]))
        own = "instr:" + str(ins.get("letters")) + "-" + str(ins.get("number"))
        for (x1, y1, x2, y2, desc) in texts:
            if desc == own:
                continue
            if _seg_rect_hit(a, b, (x1, y1, x2, y2), margin=0.2):
                V("仪表 %s-%s 引线穿过 %s" % (ins.get("letters"), ins.get("number"), desc))

    fr = FRAMES.get(spec.get("frame", "A0"), FRAMES["A0"])
    FRAME = spec.get("frame_zone") or fr["frame"]
    TITLE = spec.get("title_zone") or fr["title"]

    # 1 管线穿设备本体
    for pp in pipes:
        for a, b in zip(pp["pts"], pp["pts"][1:]):
            for tag, e in eqs.items():
                if _seg_rect_hit(a, b, e["body"], margin=1.5):
                    V("管线穿设备 p%d [%s] 段%s-%s 进入 %s 内部" %
                      (pp["id"], pp["kind"], tuple(map(round, a)), tuple(map(round, b)), tag))
    # 2 文字压线/压设备/互压
    for (x1, y1, x2, y2, desc) in texts:
        owner = int(desc.split("@p")[1]) if "@p" in desc else None
        for pp in pipes:
            if pp["id"] == owner:
                continue
            for a, b in zip(pp["pts"], pp["pts"][1:]):
                if _seg_rect_hit(a, b, (x1, y1, x2, y2), margin=0.4):
                    V("文字压线 %s × p%d 段%s-%s" % (desc, pp["id"], tuple(map(round, a)), tuple(map(round, b))))
        for tag, e in eqs.items():
            if desc.endswith(":" + tag):
                continue
            if _seg_rect_hit((x1, y1), (x2, y2), e["body"], margin=0.5):
                V("文字压设备 %s × %s" % (desc, tag))
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                V("文字互压 %s × %s" % (a[4], b[4]))
    # 3 悬空接管（画了口没接线）
    port_used = {}
    for pp in pipes:
        for end in (pp["pts"][0], pp["pts"][-1]):
            for tag, e in eqs.items():
                for name, pt in e["ports"].items():
                    if _dist_pt_seg(pt, end, end) < 2.5:
                        port_used[(tag, name)] = True
    for tag, e in eqs.items():
        drawn = e["nozzles"]
        for name, pt in e["ports"].items():
            if drawn is not None and name not in drawn:
                continue
            if (tag, name) not in port_used:
                V("悬空接管 %s.%s @ %s（nozzles 里删掉它或补管线）" % (tag, name, tuple(map(round, pt))))
    # 4 出图框
    for pp in pipes:
        for pt in pp["pts"]:
            if not (FRAME[0] - 1 <= pt[0] <= FRAME[2] + 1 and FRAME[1] - 1 <= pt[1] <= FRAME[3] + 1):
                V("管线出图框 p%d @ %s" % (pp["id"], tuple(map(round, pt))))
    # 5 入标题栏
    for pp in pipes:
        for a, b in zip(pp["pts"], pp["pts"][1:]):
            if _seg_rect_hit(a, b, TITLE, margin=1.0):
                V("管线入标题栏 p%d" % pp["id"])
    for (x1, y1, x2, y2, desc) in texts:
        if x1 < TITLE[2] and TITLE[0] < x2 and y1 < TITLE[3] and TITLE[1] < y2:
            V("文字入标题栏 %s" % desc)
    # 6 斜线
    for pp in pipes:
        for a, b in zip(pp["pts"], pp["pts"][1:]):
            if abs(a[0] - b[0]) > 0.5 and abs(a[1] - b[1]) > 0.5:
                V("斜线 p%d 段%s-%s（管线必须正交，侧口连线给 via）" %
                  (pp["id"], tuple(map(round, a)), tuple(map(round, b))))
    # 7 设备一览区
    et = spec.get("equipment_table")
    if et:
        n = len([e for e in spec.get("equipment", []) if e.get("tag")])
        per = int(et.get("per_row") or max(1, min(n, int((et.get("width", 740)) // 40))))
        rows = max(1, math.ceil(n / per))
        ytop = float(et.get("y", 96))
        ET_RECT = (float(et["x"]) - 5, ytop - rows * 15.0 - 3,
                   float(et["x"]) + float(et.get("width", 740)) + 5, ytop + 6)
        for pp in pipes:
            for a, b in zip(pp["pts"], pp["pts"][1:]):
                if _seg_rect_hit(a, b, ET_RECT, margin=1.0):
                    V("管线入设备一览区 p%d 段%s-%s" % (pp["id"], tuple(map(round, a)), tuple(map(round, b))))
    # 8 端点悬空（提醒）+ 来源/去向标注检查
    def is_port(pt):
        return any(_dist_pt_seg(pt, ept, ept) < 2.5 for e in eqs.values() for ept in e["ports"].values())

    def near_edge(pt):
        return (pt[0] < FRAME[0] + 18 or pt[0] > FRAME[2] - 18 or
                pt[1] < FRAME[1] + 18 or pt[1] > FRAME[3] - 18)

    def has_src_dst_text(pt):
        """端点 80mm 内有标注（含'来自/去/至'的来源去向，或公用工程介质名）→ 视为已标。"""
        for (x1, y1, x2, y2, desc) in texts:
            if not desc.startswith("text:"):
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            if math.hypot(cx - pt[0], cy - pt[1]) < 80:
                return True
        return False

    for pp in pipes:
        ends = (pp["pts"][0], pp["pts"][-1])
        for end in ends:
            if is_port(end) or near_edge(end):
                continue
            other = ends[1] if end is ends[0] else ends[0]
            if is_port(other) or near_edge(other):
                if not has_src_dst_text(end):
                    W("p%d 端点 %s 悬空且附近无 来源/去向 标注（进料标'来自XX'、出料标'去XX'）" %
                      (pp["id"], tuple(map(round, end))))
            else:
                W("p%d 端点 %s 悬空" % (pp["id"], tuple(map(round, end))))
    # 8b 位号必须紧贴设备（用户红线：不许甩远成"无标识罐体"）
    for tag, e in eqs.items():
        lx, ly = e["label_xy"] or e["xy"]
        bx1, by1, bx2, by2 = e["rect"]
        dx = max(bx1 - lx, 0.0, lx - bx2)
        dy = max(by1 - ly, 0.0, ly - by2)
        if math.hypot(dx, dy) > 90:
            W("设备 %s 的位号距本体 %.0fmm 过远（label_xy 应贴设备放置）" % (tag, math.hypot(dx, dy)))
    # 9 假 T（提醒）
    for pp in pipes:
        for end in (pp["pts"][0], pp["pts"][-1]):
            for qq in pipes:
                if qq["id"] == pp["id"]:
                    continue
                for a, b in zip(qq["pts"], qq["pts"][1:]):
                    if _dist_pt_seg(end, a, b) < 1.2 and _dist_pt_seg(end, a, a) > 1.2 \
                            and _dist_pt_seg(end, b, b) > 1.2:
                        W("假连接 p%d 端点 %s 落在 p%d 中段（合法三通请忽略）" %
                          (pp["id"], tuple(map(round, end)), qq["id"]))
    # 阀门压设备
    for pp in pipes:
        for vp in pp["valves"]:
            for tag, e in eqs.items():
                if e["body"][0] - 4 < vp[0] < e["body"][2] + 4 and e["body"][1] - 4 < vp[1] < e["body"][3] + 4:
                    V("阀门落进设备 %s 内部 @ %s（调 valves.at）" % (tag, tuple(map(round, vp))))
    return errors, warnings
