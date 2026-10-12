# -*- coding: utf-8 -*-
"""PFD 图例：设备、阀门、仪表符号（参照图例表8-2 常用设备图例、表2-8 阀门、附表2-4 仪表）。

约定：模型空间 mm；设备以插入点为中心绘制，size 为主要尺寸（塔/容器=总高，
换热器=壳高，泵/压缩机=圆直径）。所有符号在局部坐标（+x 右，+y 上）绘制，
rotation 角度由 Builder 统一旋转。每个设备函数返回"接口(ports)"局部坐标字典，
供管道连接使用。
"""
import math

import cad

# ================================================================ 绘图器
class B:
    def __init__(self, doc, ox, oy, rot=0.0, layer="PFD-EQUIP", lw=None):
        self.doc = doc
        self.ox, self.oy, self.rot = ox, oy, rot
        self.layer = layer
        self.lw = lw if lw is not None else 25

    def p(self, dx, dy):
        return cad.transform((dx, dy), self.ox, self.oy, self.rot)

    def line(self, pts, layer=None, lw=None):
        wpts = [self.p(*q) for q in pts]
        return cad.add_polyline(self.doc, wpts, layer or self.layer, lw or self.lw)

    def seg(self, p1, p2, layer=None, lw=None):
        return cad.add_line(self.doc, self.p(*p1), self.p(*p2), layer or self.layer, lw or self.lw)

    def rect(self, p1, p2, layer=None, lw=None):
        x1, y1 = p1
        x2, y2 = p2
        return self.line([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)], layer, lw)

    def circle(self, c, r, layer=None, lw=None):
        return cad.add_circle(self.doc, self.p(*c), r, layer or self.layer, lw or self.lw)

    def arc(self, c, r, a1, a2, layer=None, lw=None):
        return cad.add_arc(self.doc, self.p(*c), r, a1 + self.rot, a2 + self.rot, layer or self.layer, lw or self.lw)

    def tri(self, pts, layer=None, lw=None):
        return cad.add_solid_tri(self.doc, [self.p(*q) for q in pts], layer or self.layer, lw or self.lw)

    def outline_tri(self, pts, layer=None, lw=None):
        p = [self.p(*q) for q in pts]
        p.append(p[0])
        return cad.add_polyline(self.doc, p, layer or self.layer, lw or self.lw, closed=False)

    def text(self, dx, dy, h, txt, align="middle"):
        return cad.add_text(self.doc, self.p(dx, dy), h, txt, self.layer, align=align)


# ================================================================ 设备
def _pump(b, s):
    """离心泵（图例表8-2）：圆 + 左侧水平吸入（画到圆心）+ 右侧切线竖直排出
    （自底部向上、顶端朝上箭头）+ 底部开口梯形支座（两斜腿+底线，不封闭）。"""
    r = s / 2.0
    st = 0.6 * r
    b.circle((0, 0), r)
    # 支座：开口梯形（两斜腿+底横线，顶边由圆弧收口，图例不画封闭三角形）
    bh = st * 0.7
    b.line([(-r * 0.45, -r * 0.89), (-r * 0.62, -r - bh),
            (r * 0.62, -r - bh), (r * 0.45, -r * 0.89)])
    # 吸入：水平线自左侧伸到圆心（图例画法）
    b.seg((-r - st, 0), (0, 0))
    # 排出：自圆右缘切点起笔竖直向上（与圆相切、不穿过圆），顶端箭头
    b.seg((r, 0), (r, r + st))
    b.tri([(r - st * 0.26, r + st * 0.62), (r + st * 0.26, r + st * 0.62), (r, r + st)])
    return {"suction": (-r - st, 0), "discharge": (r, r + st)}


def _compressor(b, s):
    """旋转压缩机（图例表8-2）：卧式胶囊 + 内接两圆（叶轮）。"""
    H = 0.7 * s
    L = 1.25 * s
    r = H / 2.0
    _rounded_vessel(b, L, H, horizontal=True)
    rc = H * 0.32
    b.circle((-L * 0.18, 0), rc)
    b.circle((L * 0.18, 0), rc)
    return {"inlet": (-L / 2, 0), "outlet": (L / 2, 0)}


def _blower(b, s):
    """鼓风机/水环真空泵类（图例表8-2）：圆 + 左水平吸入(到圆心) + 右缘切线竖直排出带箭头 + 三角支座。"""
    r = s / 2.0
    st = 0.6 * r
    b.circle((0, 0), r)
    bh = st * 0.7
    b.line([(-r * 0.45, -r * 0.89), (-r * 0.62, -r - bh),
            (r * 0.62, -r - bh), (r * 0.45, -r * 0.89)])
    b.seg((-r - st, 0), (0, 0))
    b.seg((r, -r), (r, r + st))
    b.tri([(r - st * 0.26, r + st * 0.62), (r + st * 0.26, r + st * 0.62), (r, r + st)])
    return {"inlet": (-r - st, 0), "outlet": (r, r + st)}


def _rounded_vessel(b, L, H, horizontal=False):
    """两端半圆封头的矩形壳体。立式：封头半径=L/2；卧式：封头半径=H/2。"""
    if horizontal:
        r = H / 2.0
        x1, x2 = -L / 2.0 + r, L / 2.0 - r
        b.seg((x1, -H / 2), (x2, -H / 2))
        b.seg((x1, H / 2), (x2, H / 2))
        b.arc((x1, 0), r, 90, 270)
        b.arc((x2, 0), r, -90, 90)
    else:
        r = L / 2.0
        b.seg((-L / 2, -H / 2 + r), (-L / 2, H / 2 - r))
        b.seg((L / 2, -H / 2 + r), (L / 2, H / 2 - r))
        b.arc((0, H / 2 - r), r, 0, 180)
        b.arc((0, -H / 2 + r), r, 180, 360)


def _shallow_vessel(b, W, H, hh=None):
    """立式容器（图例表8-2 容器-立式/塔/反应器通用画法）：直壁 + 浅椭圆封头。
    封头高 hh（默认 0.25W），用参数折线逼近椭圆弧，避免画成大半球头'椭圆罐'。"""
    if hh is None:
        hh = 0.25 * W
    r = W / 2.0
    n = 10
    b.seg((-r, -H / 2 + hh), (-r, H / 2 - hh))
    b.seg((r, -H / 2 + hh), (r, H / 2 - hh))
    top = [(-r * math.cos(math.pi * k / n),
            H / 2 - hh + hh * math.sin(math.pi * k / n)) for k in range(n + 1)]
    bot = [(-r * math.cos(math.pi * k / n),
            -H / 2 + hh - hh * math.sin(math.pi * k / n)) for k in range(n + 1)]
    b.line(top)
    b.line(bot)
    return hh


def _heat_exchanger(b, s, nozzles=None):
    """卧式管壳式换热器（图例表8-2 固定管板式）：胶囊壳 + 两端各一条竖直管板线封口 +
    两管板间水平管束细线；管程接管在左右两端(水平)、壳程接管上(偏左)下(偏右)。s=壳高。"""
    H = s
    L = 2.3 * s
    r = H / 2.0
    _rounded_vessel(b, L, H, horizontal=True)
    # 管板：两端各一条竖直管板线（固定管板=管束两端均固定在管板上，必须封口）
    b.seg((-L / 2 + r, -H / 2), (-L / 2 + r, H / 2))
    b.seg((L / 2 - r, -H / 2), (L / 2 - r, H / 2))
    # 管束：两管板之间 4 条水平细线（图例固定管板式，细线不抢壳体线宽）
    for f in (-0.375, -0.125, 0.125, 0.375):
        y = f * H
        b.line([(-L / 2 + r, y), (L / 2 - r, y)], lw=18)
    st = 0.35 * s  # 接管长
    ports = {
        "tube_in": (-L / 2 - st, 0), "tube_out": (L / 2 + st, 0),
        "shell_in": (-0.15 * L, H / 2 + st), "shell_out": (0.15 * L, -H / 2 - st),
    }
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name == "tube_in":
            b.seg((-L / 2, 0), (dx, 0))
        elif name == "tube_out":
            b.seg((L / 2, 0), (dx, 0))
        elif dy > 0:
            b.seg((dx, H / 2), (dx, dy))
        else:
            b.seg((dx, -H / 2), (dx, dy))
    return ports


def _column(b, s, internals="tray", n=12, nozzles=None):
    """立式塔设备（图例表8-2 塔T）：细高壳体+椭圆封头+塔板/填料。s=总高。
    塔板示意画法：满跨均匀分布（最多画 12 条，间距随高度自适应），贴近上下封头。"""
    H = s
    W = max(0.2 * s, 14.0)
    r = W / 2.0
    hh = 0.35 * W
    _shallow_vessel(b, W, H, hh)
    y1, y2 = -H / 2 + 1.15 * hh, H / 2 - 1.15 * hh
    if internals == "tray":
        n_draw = max(4, min(int(n), 12))   # 塔板示意：最多 12 条，避免过密
        step = (y2 - y1) / max(n_draw - 1, 1)
        for k in range(n_draw):
            y = y1 + k * step
            # 塔板线通宽（图例表8-2 板式塔：水平线横跨两壁）
            b.seg((-r * 0.98, y), (r * 0.98, y))
    elif internals == "packing":
        # 填料塔（图例）：上分布器横线 + 一段大X填料 + 下支撑横线
        b.seg((-r * 0.98, y2), (r * 0.98, y2))
        b.seg((-r * 0.98, y1), (r * 0.98, y1))
        b.seg((-r * 0.98, y1), (r * 0.98, y2))
        b.seg((-r * 0.98, y2), (r * 0.98, y1))
        b.seg((-r * 0.5, y2 + 0.06 * s), (r * 0.5, y2 + 0.06 * s))  # 液体分布器
    st = 0.12 * s
    ports = {"top": (0, H / 2), "top_L": (-0.4 * r, H / 2), "top_R": (0.4 * r, H / 2),
             "bottom": (0, -H / 2),
             "side_L_up": (-r - st, 0.25 * H), "side_L": (-r - st, 0.0), "side_L_dn": (-r - st, -0.25 * H),
             "side_R_up": (r + st, 0.25 * H), "side_R": (r + st, 0.0), "side_R_dn": (r + st, -0.25 * H)}

    def _head_y(dx, top):
        """封头椭圆曲线上横坐标 dx 处的高度——接管短桩从曲线起笔，设备内不留线头。"""
        f = math.sqrt(max(0.0, 1.0 - (dx / r) ** 2))
        return (H / 2 - hh + hh * f) if top else (-H / 2 + hh - hh * f)

    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name.startswith("top"):
            y0 = _head_y(dx, True)
            if dy - y0 > 0.3:
                b.seg((dx, y0), (dx, dy))
        elif name == "bottom":
            y0 = _head_y(dx, False)
            if y0 - dy > 0.3:
                b.seg((dx, y0), (dx, dy))
        elif name.startswith("side_L"):
            b.seg((-r, dy), (dx, dy))
        else:
            b.seg((r, dy), (dx, dy))
    return ports


def _vessel(b, s, horizontal=False, nozzles=None):
    if horizontal:
        L, H = 2.2 * s, s
        _rounded_vessel(b, L, H, horizontal=True)
        # 顶部人孔凸出（图例表8-2 卧式）
        b.rect((-0.08 * s, H / 2), (0.08 * s, H / 2 + 0.1 * s))
        st = 0.3 * s
        r = H / 2.0
        x1, x2 = -L / 2.0 + r, L / 2.0 - r
        ports = {"inlet": (x1, H / 2 + st), "vent": (x2, H / 2 + st), "outlet": ((x1 + x2) / 2, -H / 2 - st)}
        for name, (dx, dy) in ports.items():
            if nozzles is not None and name not in nozzles:
                continue
            b.seg((dx, H / 2 if dy > 0 else -H / 2), (dx, dy))
        return ports
    L, H = 0.5 * s, s
    _shallow_vessel(b, L, H)
    st = 0.2 * s
    r = L / 2.0
    ports = {"top": (0, H / 2 + st), "bottom": (0, -H / 2 - st),
             "side_L": (-r - st, 0.15 * H), "side_R": (r + st, -0.15 * H)}
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name == "top":
            b.seg((0, H / 2), (dx, dy))
        elif name == "bottom":
            b.seg((0, -H / 2), (dx, dy))
        elif name == "side_L":
            b.seg((-r, dy), (dx, dy))
        else:
            b.seg((r, dy), (dx, dy))
    return ports


def _reactor(b, s):
    """搅拌反应器（图例表8-2 反应釜）：立式容器 + 顶部 M 电机圆 + 轴 + Z 形搅拌桨 + 夹套。"""
    L, H = 0.55 * s, 0.78 * s
    _shallow_vessel(b, L, H)
    r = L / 2.0
    # 夹套（壳外两侧线 + 底部随浅封头外扩的包络 + 顶部内折边，如图例）
    jw = 0.09 * s
    hh = 0.25 * L
    b.line([(-r, H * 0.15), (-r - jw, H * 0.15), (-r - jw, -H / 2 + hh)])
    b.line([(r, H * 0.15), (r + jw, H * 0.15), (r + jw, -H / 2 + hh)])
    n = 10
    b.line([(-(r + jw) * math.cos(math.pi * k / n),
             -H / 2 + hh - (hh + jw) * math.sin(math.pi * k / n)) for k in range(n + 1)])
    # 搅拌电机：圆 + M
    mr = 0.11 * s
    myc = H / 2 + mr + 0.05 * s
    b.circle((0, myc), mr)
    b.text(0, myc, mr * 1.3, "M")
    # 轴 + Z 形桨
    b.seg((0, myc - mr), (0, -H * 0.12))
    b.line([(0, -H * 0.12), (-0.16 * s, -H * 0.2), (0.16 * s, -H * 0.28), (0, -H * 0.36)])
    st = 0.2 * s
    b.seg((-r - jw - st, H * 0.25), (-r - jw, H * 0.25))   # 进料接管
    b.seg((0, -H / 2 - jw), (0, -H / 2 - jw - st))         # 出料
    return {"feed": (-r - jw - st, H * 0.25), "top": (0, myc + mr),
            "outlet": (0, -H / 2 - jw - st)}


def _fired_heater(b, s):
    """工业炉(F)：矩形炉体 + 顶部烟囱 + 炉管(顶集合管+四根辐射管) + 底部燃烧器锯齿线。"""
    W, H = 1.4 * s, s
    b.rect((-W / 2, -H / 2), (W / 2, H / 2))
    # 炉管：顶部集合管横跨内壁 + 4 根下垂辐射管
    y0 = H * 0.12
    b.seg((-W * 0.38, y0), (W * 0.38, y0))
    for k in range(4):
        x = -W * 0.38 + k * W * 0.76 / 3.0
        b.seg((x, y0), (x, -H * 0.22))
    # 燃烧器锯齿线（炉底）
    n = 6
    pts = []
    for i in range(n + 1):
        x = -W / 2 + i * W / n
        pts.append((x, -H / 2 + (H * 0.08 if i % 2 else 0)))
    b.line(pts)
    # 烟囱
    b.rect((W * 0.25, H / 2), (W * 0.45, H / 2 + 0.5 * s))
    st = 0.25 * s
    b.seg((-W / 2, H * 0.25), (-W / 2 - st, H * 0.25))
    b.seg((W / 2, -H * 0.15), (W / 2 + st, -H * 0.15))
    return {"feed": (-W / 2 - st, H * 0.25), "product": (W / 2 + st, -H * 0.15),
            "flue": (W * 0.35, H / 2 + 0.5 * s)}


def _separator(b, s, nozzles=None):
    L, H = 0.45 * s, s
    _shallow_vessel(b, L, H)
    r = L / 2
    st = 0.25 * s
    ports = {"inlet": (-r - st, H * 0.28), "top": (0, H / 2 + st * 0.6),
             "bottom": (0, -H / 2 - st * 0.6), "vapor_out": (r + st, H * 0.05)}
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name == "inlet":
            b.seg((-r, H * 0.28), (dx, dy))
        elif name == "top":
            b.seg((0, H / 2), (0, dy))
        elif name == "bottom":
            b.seg((0, -H / 2), (0, dy))
        else:
            b.seg((r, H * 0.05), (dx, dy))
    # 进口挡板：全高挡板，上下端均落在封头曲线上——两端搭壳体，不悬空
    if nozzles is None or "inlet" in nozzles:
        hh = 0.25 * L
        fx = 0.45
        yc = H / 2 - hh * (1 - math.sqrt(1 - fx * fx))
        b.seg((-r * fx, -yc), (-r * fx, yc))
    # 丝网除沫器（闪蒸罐顶标件）：满跨虚线（两壁到壁）
    if nozzles is None or "top" in nozzles:
        o = b.seg((-r * 0.98, H * 0.34), (r * 0.98, H * 0.34))
        cad.set_dashed(o, 2.0)
    return ports


def _storage_tank(b, s, nozzles=None):
    """储罐（图例表8-2 容器-平顶罐）：矩形 + 底部地平线（向两侧外伸）。"""
    W, H = 1.1 * s, 0.8 * s
    b.rect((-W / 2, -H / 2), (W / 2, H / 2))
    b.seg((-W / 2 - 0.1 * W, -H / 2), (W / 2 + 0.1 * W, -H / 2))  # 地平线
    st = 0.2 * s
    ports = {"inlet": (0, H / 2 + st), "outlet": (0, -H / 2 - st)}
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        b.seg((0, H / 2 if dy > 0 else -H / 2), (dx, dy))
    return ports


def _kettle_reboiler(b, s, nozzles=None):
    """釜式重沸器（图例表8-2 换热器-釜式）：左侧小通道封头 + 右侧带汽相空间的釜体
    （顶线向右抬升、右端圆弧），内画 U 形管束；接管：通道上/下（加热介质进/出）、
    汽相空间顶（气相返塔）、釜体底（塔底液进料）。s=总宽。"""
    L = s
    c = 0.16 * s            # 通道半高
    v = 0.34 * s            # 汽相空间顶高
    e = 0.22 * L            # 通道宽
    rc = 0.10 * L           # 釜体右端弧半径
    xc = -L / 2 + e         # 通道右壁 x
    xr = L / 2 - rc         # 釜体右端弧心 x
    st = 0.12 * s
    # 通道：左端半圆封头 + 矩形
    b.arc((-L / 2 + c, 0), c, 90, 270)
    b.seg((-L / 2 + c, c), (xc, c))
    b.seg((-L / 2 + c, -c), (xc, -c))
    # 釜体轮廓：底线、右端半圆、顶线（汽相空间）、斜升线接回通道顶
    b.seg((xc, -c), (xr, -c))
    rv = (v + c) / 2.0
    b.arc((xr, (v - c) / 2.0), rv, -90, 90)
    xd = xr - 0.30 * L      # 斜升线起点
    b.seg((xr, v), (xd, v))
    b.seg((xd, v), (xc, c))
    # 管束：圆角矩形管束（标准图例釜式格画法）+ 通道内管板横线
    bx1, bx2 = xc + 0.02 * L, xr - 0.06 * L
    bh = c * 0.72
    b.seg((bx1, -bh), (bx1, bh))            # 左端管板竖线
    b.seg((bx1, bh), (bx2, bh))             # 上横线
    b.arc((bx2, 0), bh, -90, 90)            # 右端半圆封
    b.seg((bx1, -bh), (bx2, -bh))           # 下横线
    b.seg((-L / 2 + 0.55 * c, 0), (xc, 0))  # 通道内管板横线
    # 接管
    ports = {
        "heating_in": (-L / 2 + c, c + st),    # 通道顶（加热介质进）
        "heating_out": (-L / 2 + c, -c - st),  # 通道底（凝液出）
        "vapor_out": (xd + 0.10 * L, v + st),  # 汽相空间顶（气相返塔）
        "process_in": (xd + 0.30 * L, -c - st) # 釜体底（塔底液进）
    }
    b.seg((ports["vapor_out"][0], v), ports["vapor_out"])
    b.seg((ports["process_in"][0], -c), ports["process_in"])
    # 加热介质接管末端箭头（图例四口均带流向箭头）
    aw = 0.05 * s
    hx = -L / 2 + c
    if nozzles is None or "heating_in" in nozzles:
        b.seg((hx, c), (hx, c + st))
        b.tri([(hx - aw, c + st), (hx + aw, c + st), (hx, c + st - aw * 1.6)])          # 进（朝下）
    if nozzles is None or "heating_out" in nozzles:
        b.seg((hx, -c), (hx, -c - st))
        b.tri([(hx - aw, -c - st + aw * 1.6), (hx + aw, -c - st + aw * 1.6), (hx, -c - st)])  # 出（朝下）
    return ports


def _mixer(b, s, nozzles=None):
    """混合器（PFD 气/液混合器标准画法，Aspen MIXER 同形）：倒三角形，
    顶边进料（TL/T/TR 三向），底角出料（B）。s=顶边宽基准。nozzles 选择画出的接管。"""
    W, H = 1.6 * s, 0.9 * s
    b.line([(-W / 2, H / 2), (W / 2, H / 2), (0, -H / 2), (-W / 2, H / 2)])
    st = 0.30 * s
    ports = {"TL": (-W / 3, H / 2 + st), "T": (0, H / 2 + st), "TR": (W / 3, H / 2 + st),
             "B": (0, -H / 2 - st)}
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name == "B":
            b.seg((0, -H / 2), (0, dy))
        else:
            b.seg((dx, H / 2), (dx, dy))
    return ports


def _fixed_bed_reactor(b, s, nozzles=None):
    """固定床反应器（图例表8-2 反应器-固定床反应器）：立式细壳+浅封头 +
    中部催化剂床层（矩形框+单X）。s=壳体总高。
    侧口必须开在床层矩形的上/下方直壁段（side_L/side_R 在上方 0.33s，
    side_L_low/side_R_low 在下方 −0.33s），绝不能开在床层正中——
    那正好是 X 对角线交叉点，进料管会视觉上捅穿床层。
    侧上进=气相自上而下穿床层（与标准图例顶进底出同向）。"""
    W = 0.30 * s
    r = W / 2.0
    _shallow_vessel(b, W, s)
    bh = 0.45 * s
    b.seg((-r, bh / 2), (r, bh / 2))
    b.seg((-r, -bh / 2), (r, bh / 2))
    b.seg((-r, bh / 2), (r, -bh / 2))
    b.seg((-r, -bh / 2), (r, -bh / 2))
    st = 0.15 * s
    ports = {"top": (0, s / 2 + st), "bottom": (0, -s / 2 - st),
             "side_L": (-W / 2 - st, 0.33 * s), "side_R": (W / 2 + st, 0.33 * s),
             "side_L_low": (-W / 2 - st, -0.33 * s), "side_R_low": (W / 2 + st, -0.33 * s)}
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name == "top":
            b.seg((0, s / 2), (0, dy))
        elif name == "bottom":
            b.seg((0, -s / 2), (0, dy))
        else:  # 侧口短桩：从壁面水平引出
            x0 = -W / 2 if name.startswith("side_L") else W / 2
            b.seg((x0, dy), (dx, dy))
    return ports


def _decanter(b, s):
    """分层器/倾析器（立式）：浅封头壳体 + 右侧溢流挡板 + 液液分界虚线；
    顶部进料、轻相由挡板上方溢至右侧出口、重相底出。s=壳体总高。"""
    W, H = 0.6 * s, s
    r = W / 2.0
    _shallow_vessel(b, W, H)
    # 溢流挡板：上下端均落在封头曲线上（全高挡板，两端搭壳体，不悬空）
    hh = 0.25 * W
    fx = 0.48
    ytop = H / 2 - hh * (1 - math.sqrt(1 - fx * fx))
    ybot = -H / 2 + hh * (1 - math.sqrt(1 - fx * fx))
    b.seg((0.24 * W, ybot), (0.24 * W, ytop))
    o = b.seg((-r, -0.06 * H), (0.24 * W, -0.06 * H))  # 液液分界（左端贴壁）
    cad.set_dashed(o, 3.0)
    st = 0.22 * s
    b.seg((0, H / 2), (0, H / 2 + st))
    b.seg((W / 2, 0.34 * H), (W / 2 + st, 0.34 * H))
    b.seg((0, -H / 2), (0, -H / 2 - st))
    return {"feed": (0, H / 2 + st), "organic": (W / 2 + st, 0.34 * H),
            "aqueous": (0, -H / 2 - st)}


def _flare_stack(b, s, nozzles=None):
    """火炬/烟囱(S)：下宽上窄细锥筒身+顶端火苗；泄放管线从底部进。s=筒身高。"""
    w0, w1 = 0.05 * s, 0.032 * s
    top = s / 2 - 0.12 * s
    b.line([(-w0, -s / 2), (-w1, top), (w1, top), (w0, -s / 2), (-w0, -s / 2)])
    b.outline_tri([(-w1 * 1.8, top), (w1 * 1.8, top), (0, top + 0.15 * s)])
    st = 0.12 * s
    ports = {"inlet": (0, -s / 2 - st)}
    if nozzles is None or "inlet" in nozzles:
        b.seg((0, -s / 2), (0, -s / 2 - st))
    return ports


def _cyclone(b, s, nozzles=None):
    """旋风分离器（除尘/气固分离）：上圆筒+下锥；切向进口、顶出气、底出料。s=总高。"""
    W = 0.5 * s
    y1 = s / 2 - 0.45 * s
    st = 0.12 * s
    b.rect((-W / 2, y1), (W / 2, s / 2))
    b.seg((-W / 2, y1), (0, -s / 2))
    b.seg((W / 2, y1), (0, -s / 2))
    ports = {"inlet": (W / 2 + st, s / 2 - 0.1 * s), "vapor_out": (0, s / 2 + st),
             "solids_out": (0, -s / 2 - st)}
    for name, (dx, dy) in ports.items():
        if nozzles is not None and name not in nozzles:
            continue
        if name == "inlet":
            b.seg((W / 2, dy), (dx, dy))
        elif name == "vapor_out":
            b.seg((0, s / 2), (0, dy))
        else:
            b.seg((0, -s / 2), (0, dy))
    return ports


def _ejector(b, s, nozzles=None):
    """蒸汽喷射器/真空喷射泵：文丘里轮廓+喉部吸入口。
    动力汽左进、被吸介质顶进、混合汽右出。s=总长。"""
    t, e = 0.05 * s, 0.18 * s
    st = 0.14 * s
    b.line([(-s / 2, e), (-0.15 * s, t), (0.15 * s, t), (s / 2, e)])
    b.line([(-s / 2, -e), (-0.15 * s, -t), (0.15 * s, -t), (s / 2, -e)])
    ports = {"motive_in": (-s / 2 - st, 0), "suction": (0, t + 0.25 * s),
             "discharge": (s / 2 + st, 0)}
    if nozzles is None or "motive_in" in nozzles:
        b.seg((-s / 2, 0), (-s / 2 - st, 0))
    if nozzles is None or "suction" in nozzles:
        b.seg((0, t), (0, t + 0.25 * s))
    if nozzles is None or "discharge" in nozzles:
        b.seg((s / 2, 0), (s / 2 + st, 0))
    return ports


def _air_cooler(b, s, nozzles=None):
    """空气冷却器：管束矩形（内三横线）+顶部风机圆（叶轮十字）；工艺管左进右出。s=管束宽。"""
    H = 0.3 * s
    st = 0.12 * s
    b.rect((-s / 2, -H / 2), (s / 2, H / 2))
    for f in (-0.5, 0.0, 0.5):
        b.seg((-s / 2 + 0.03 * s, f * H), (s / 2 - 0.03 * s, f * H))
    fr = 0.18 * s
    fc = H / 2 + 0.12 * s + fr
    b.circle((0, fc), fr)
    b.seg((-fr * 0.7, fc - fr * 0.7), (fr * 0.7, fc + fr * 0.7))
    b.seg((-fr * 0.7, fc + fr * 0.7), (fr * 0.7, fc - fr * 0.7))
    ports = {"process_in": (-s / 2 - st, 0), "process_out": (s / 2 + st, 0)}
    if nozzles is None or "process_in" in nozzles:
        b.seg((-s / 2, 0), (-s / 2 - st, 0))
    if nozzles is None or "process_out" in nozzles:
        b.seg((s / 2, 0), (s / 2 + st, 0))
    return ports


def _vacuum_pump(b, s, nozzles=None):
    """水环真空泵（标准图例泵行）：圆+梯形支座+左侧水平吸入+顶部切线排出带箭头。s=圆直径。"""
    r = s / 2.0
    st = 0.6 * r
    b.circle((0, 0), r)
    bh = st * 0.7
    b.line([(-r * 0.45, -r * 0.89), (-r * 0.62, -r - bh),
            (r * 0.62, -r - bh), (r * 0.45, -r * 0.89)])
    ports = {"inlet": (-r - st, 0), "outlet": (0, r + st)}
    if nozzles is None or "inlet" in nozzles:
        b.seg((-r, 0), (-r - st, 0))
    if nozzles is None or "outlet" in nozzles:
        b.seg((0, r), (0, r + st))
        b.tri([(-st * 0.26, r + st * 0.62), (st * 0.26, r + st * 0.62), (0, r + st)])
    return ports


def _filter_press(b, s, nozzles=None):
    """板框压滤机(M)：滤板矩形组（内部竖线）+左上进浆+底出滤液。s=机宽。"""
    W, H = 0.9 * s, 0.62 * s
    b.rect((-W / 2, -H / 2), (W / 2, H / 2))
    for k in range(1, 6):
        x = -W / 2 + k * W / 6
        b.seg((x, -H / 2), (x, H / 2))
    ports = {"feed": (-W / 2 - 0.12 * s, 0.15 * H), "filtrate": (0, -H / 2 - 0.12 * s)}
    if nozzles is None or "feed" in nozzles:
        b.seg((-W / 2, 0.15 * H), (-W / 2 - 0.12 * s, 0.15 * H))
    if nozzles is None or "filtrate" in nozzles:
        b.seg((0, -H / 2), (0, -H / 2 - 0.12 * s))
    return ports


def _centrifuge(b, s, nozzles=None):
    """离心机(M)：转鼓矩形（内部双竖线）+支腿；顶部进料、底出固渣、右侧溢流。s=鼓高。"""
    W, H = 0.55 * s, s
    b.rect((-W / 2, -H / 2), (W / 2, H / 2))
    for x in (-0.12 * s, 0.12 * s):
        b.seg((x, -H / 2), (x, H / 2))
    for sx in (-1, 1):
        b.line([(sx * W * 0.18, -H / 2), (sx * W * 0.32, -H / 2 - 0.12 * s)])
        b.line([(sx * W * 0.32, -H / 2), (sx * W * 0.32, -H / 2 - 0.12 * s)])
    st = 0.14 * s
    ports = {"feed": (0, H / 2 + st), "solids_out": (0, -H / 2 - 0.12 * s),
             "liquid_out": (W / 2 + st, 0.2 * H)}
    if nozzles is None or "feed" in nozzles:
        b.seg((0, H / 2), (0, H / 2 + st))
    if nozzles is None or "solids_out" in nozzles:
        b.seg((0, -H / 2), (0, -H / 2 - 0.12 * s))
    if nozzles is None or "liquid_out" in nozzles:
        b.seg((W / 2, 0.2 * H), (W / 2 + st, 0.2 * H))
    return ports


EQUIPMENT = {
    "pump": (_pump, 24, "离心泵(P)：圆+左吸入(到圆心)+右缘切线竖直排出带箭头+开口梯形支座；接口 suction(左)/discharge(右上)"),
    "compressor": (_compressor, 24, "旋转压缩机(C)：卧式胶囊+两叶轮圆；接口 inlet(左)/outlet(右)"),
    "blower": (_blower, 24, "鼓风机(C)：圆+左吸+顶排箭头+支座；接口 inlet/outlet"),
    "heat_exchanger": (_heat_exchanger, 30, "固定管板换热器(E)：卧式胶囊+两端各一条竖直管板线封口+两管板间4条水平细管束线；管程 tube_in(左)/tube_out(右)，壳程 shell_in(上偏左)/shell_out(下偏右)；加热器/冷却器/冷凝器同符号"),
    "column": (_column, 220, "塔(T)：细身浅封头壳+通宽塔板(internals=tray)或单段X填料+分布器(packing)；接口 top/top_L/top_R/bottom/side_L(_up/_dn)/side_R(_up/_dn)"),
    "vessel": (_vessel, 90, "立式容器(V)：浅椭圆封头；接口 top/bottom/side_L/side_R；options.horizontal=true 为卧式(带人孔)"),
    "reactor": (_reactor, 110, "搅拌反应器(R)：夹套(顶内折边)+M电机圆+轴+Z形桨；接口 feed/top/outlet"),
    "fired_heater": (_fired_heater, 90, "工业炉(F)；接口 feed/product/flue"),
    "separator": (_separator, 90, "分离器/闪蒸罐(V)：浅封头壳+进口挡板+顶部除沫器虚线；气相走 top、液相走 bottom、进料走 inlet(侧)"),
    "storage_tank": (_storage_tank, 80, "储罐(V)：平顶罐=矩形+底部地平线；接口 inlet/outlet"),
    "reboiler": (_kettle_reboiler, 70, "釜式重沸器(E)：通道封头+带汽相空间釜体+U形管束；接口 heating_in/out(通道上下)/vapor_out(汽相顶,返塔)/process_in(釜底,塔底液)"),
    "mixer": (_mixer, 30, "混合器(M)：倒三角形，顶边进料(TL/T/TR)、底角出料(B)；options.nozzles 选画接管"),
    "fixed_bed_reactor": (_fixed_bed_reactor, 110, "固定床反应器(R，标准图例反应器行)：立式细壳浅封头+催化剂床(矩形+X)；进料 top(上进)或 side_L/side_R(侧进)，bottom 出料；nozzles 选画接管"),
    "decanter": (_decanter, 80, "分层器/倾析器(D)：立式浅封头壳+溢流挡板+分界虚线；接口 feed(顶)/organic(右轻相)/aqueous(底重相)"),
    "cyclone": (_cyclone, 80, "旋风分离器：上圆筒+下锥；切向 inlet(右)/vapor_out(顶)/solids_out(底)；除尘、气固分离"),
    "ejector": (_ejector, 60, "蒸汽喷射器/真空喷射泵：文丘里体；motive_in(左动力汽)/suction(顶被吸)/discharge(右混合出)"),
    "air_cooler": (_air_cooler, 70, "空气冷却器：管束矩形+顶部风机圆；process_in(左)/process_out(右)"),
    "vacuum_pump": (_vacuum_pump, 26, "水环真空泵：圆+支座+顶部切线排出带箭头；inlet(左)/outlet(顶)"),
    "flare_stack": (_flare_stack, 120, "火炬/烟囱(S)：细锥筒身+顶端火苗；inlet(底)，泄放气接入"),
    "filter_press": (_filter_press, 60, "板框压滤机(M)：滤板矩形组；feed(左上进浆)/filtrate(底出滤液)"),
    "centrifuge": (_centrifuge, 60, "离心机(M)：转鼓矩形+支腿；feed(顶)/solids_out(底固渣)/liquid_out(右溢流)"),
}


# 各设备端口的短桩轴向外法线（自动布线沿此方向正交引入，杜绝斜线）
PORT_DIR = {
    "pump": {"suction": (-1, 0), "discharge": (0, 1)},
    "compressor": {"inlet": (-1, 0), "outlet": (1, 0)},
    "blower": {"inlet": (-1, 0), "outlet": (0, 1)},
    "heat_exchanger": {"tube_in": (-1, 0), "tube_out": (1, 0),
                       "shell_in": (0, 1), "shell_out": (0, -1)},
    "column": {"top": (0, 1), "top_L": (0, 1), "top_R": (0, 1), "bottom": (0, -1),
               "side_L_up": (-1, 0), "side_L": (-1, 0), "side_L_dn": (-1, 0),
               "side_R_up": (1, 0), "side_R": (1, 0), "side_R_dn": (1, 0)},
    "vessel": {"top": (0, 1), "bottom": (0, -1), "side_L": (-1, 0), "side_R": (1, 0),
               "inlet": (0, 1), "vent": (0, 1), "outlet": (0, -1)},
    "reactor": {"feed": (-1, 0), "top": (0, 1), "outlet": (0, -1)},
    "fired_heater": {"feed": (-1, 0), "product": (1, 0), "flue": (0, 1)},
    "separator": {"inlet": (-1, 0), "top": (0, 1), "bottom": (0, -1), "vapor_out": (1, 0)},
    "storage_tank": {"inlet": (0, 1), "outlet": (0, -1)},
    "reboiler": {"heating_in": (0, 1), "heating_out": (0, -1),
                 "vapor_out": (0, 1), "process_in": (0, -1)},
    "mixer": {"TL": (0, 1), "T": (0, 1), "TR": (0, 1), "B": (0, -1), "L": (-1, 0), "R": (1, 0)},
    "fixed_bed_reactor": {"top": (0, 1), "bottom": (0, -1), "side_L": (-1, 0), "side_R": (1, 0),
                          "side_L_low": (-1, 0), "side_R_low": (1, 0)},
    "decanter": {"feed": (0, 1), "organic": (1, 0), "aqueous": (0, -1)},
    "cyclone": {"inlet": (1, 0), "vapor_out": (0, 1), "solids_out": (0, -1)},
    "ejector": {"motive_in": (-1, 0), "suction": (0, 1), "discharge": (1, 0)},
    "air_cooler": {"process_in": (-1, 0), "process_out": (1, 0)},
    "vacuum_pump": {"inlet": (-1, 0), "outlet": (0, 1)},
    "flare_stack": {"inlet": (0, -1)},
    "filter_press": {"feed": (-1, 0), "filtrate": (0, -1)},
    "centrifuge": {"feed": (0, 1), "solids_out": (0, -1), "liquid_out": (1, 0)},
}


def draw_equipment(doc, kind, x, y, size=None, rotation=0.0, options=None):
    """绘制设备图例，返回 {ports: 世界坐标接口字典, port_dir: 各口外法线(世界),
    size, ext: 包围盒(局部)}。"""
    options = options or {}
    fn, dsize, _desc = EQUIPMENT[kind]
    size = float(size or dsize)
    b = B(doc, x, y, rotation)
    nz = options.get("nozzles")
    if kind == "column":
        ports = fn(b, size, internals=options.get("internals", "tray"),
                   n=int(options.get("n_trays", 12)), nozzles=nz)
    elif kind == "vessel":
        ports = fn(b, size, horizontal=bool(options.get("horizontal", False)), nozzles=nz)
    elif kind == "heat_exchanger":
        ports = fn(b, size, nozzles=nz)
    elif kind == "storage_tank":
        ports = fn(b, size, nozzles=nz)
    elif kind == "mixer":
        ports = fn(b, size, nozzles=nz)
    elif kind == "separator":
        ports = fn(b, size, nozzles=nz)
    elif kind == "reboiler":
        ports = fn(b, size, nozzles=nz)
    elif kind == "fixed_bed_reactor":
        ports = fn(b, size, nozzles=nz)
    elif kind in ("cyclone", "ejector", "air_cooler", "vacuum_pump",
                  "flare_stack", "filter_press", "centrifuge"):
        ports = fn(b, size, nozzles=nz)
    else:
        ports = fn(b, size)
    world = {k: cad.transform(v, x, y, rotation) for k, v in ports.items()}
    dirs = {k: cad.transform(PORT_DIR.get(kind, {}).get(k, (1, 0)), 0.0, 0.0, rotation)
            for k in ports}
    return {"ports": world, "port_dir": dirs, "size": size,
            "ext": equipment_extents(kind, size, options)}


def equipment_extents(kind, size, options=None):
    """设备包围盒（局部坐标，未旋转）：(dx1, dy1, dx2, dy2)。用于走线避障。"""
    s = float(size)
    o = options or {}
    if kind == "column":
        W = max(0.2 * s, 14.0); st = 0.12 * s
        return (-W / 2 - st, -s / 2, W / 2 + st, s / 2)
    if kind == "heat_exchanger":
        L = 2.3 * s; st = 0.35 * s
        return (-L / 2 - st, -s / 2 - st, L / 2 + st, s / 2 + st)
    if kind == "vessel":
        if o.get("horizontal"):
            L = 2.2 * s; st = 0.3 * s
            return (-L / 2, -s / 2 - st, L / 2, s / 2 + st + 0.1 * s)
        L = 0.5 * s; st = 0.2 * s
        return (-L / 2 - st, -s / 2 - st, L / 2 + st, s / 2 + st)
    if kind == "reactor":
        L = 0.55 * s; H = 0.78 * s; jw = 0.09 * s; st = 0.2 * s; mr = 0.11 * s
        return (-L / 2 - jw - st, -H / 2 - jw - st, L / 2 + jw + st, H / 2 + 2 * mr + 0.05 * s)
    if kind == "pump":
        return (-0.85 * s, -0.85 * s, 0.85 * s, 0.85 * s)
    if kind == "blower":
        return (-0.85 * s, -0.85 * s, 0.85 * s, 0.85 * s)
    if kind == "compressor":
        return (-0.625 * s, -0.35 * s, 0.625 * s, 0.35 * s)
    if kind == "fired_heater":
        W = 1.4 * s; st = 0.25 * s
        return (-W / 2 - st, -s / 2, W / 2 + st, s / 2 + 0.5 * s)
    if kind == "separator":
        L = 0.45 * s; st = 0.25 * s
        return (-L / 2 - st, -s / 2 - 0.15 * s, L / 2 + st, s / 2 + 0.15 * s)
    if kind == "storage_tank":
        W = 1.1 * s; H = 0.8 * s; st = 0.2 * s
        return (-W / 2, -H / 2 - st, W / 2, H / 2 + st)
    if kind == "reboiler":
        return (-s / 2, -0.28 * s, s / 2, 0.46 * s)
    if kind == "fixed_bed_reactor":
        W = 0.30 * s; st = 0.15 * s
        return (-W / 2 - st, -s / 2 - st, W / 2 + st, s / 2 + st)
    if kind == "decanter":
        W = 0.6 * s; st = 0.22 * s
        return (-W / 2, -s / 2 - st, W / 2 + st, s / 2 + st)
    if kind == "mixer":
        W, H = 1.6 * s, 0.9 * s; st = 0.30 * s
        return (-W / 2, -H / 2 - st, W / 2, H / 2 + st)
    if kind == "cyclone":
        st = 0.12 * s
        return (-0.25 * s - st, -s / 2 - st, 0.25 * s + st, s / 2 + st)
    if kind == "ejector":
        st = 0.14 * s
        return (-s / 2 - st, -0.2 * s, s / 2 + st, 0.32 * s)
    if kind == "air_cooler":
        st = 0.12 * s
        return (-s / 2 - st, -0.15 * s, s / 2 + st, 0.45 * s)
    if kind == "vacuum_pump":
        return (-0.85 * s, -0.85 * s, 0.85 * s, 1.0 * s)
    if kind == "flare_stack":
        st = 0.12 * s
        return (-0.15 * s, -s / 2 - st, 0.15 * s, s / 2 + 0.16 * s)
    if kind == "filter_press":
        return (-0.57 * s, -0.43 * s, 0.45 * s, 0.31 * s)
    if kind == "centrifuge":
        return (-0.275 * s, -0.62 * s, 0.415 * s, 0.62 * s)
    if kind == "blower":
        return (-s / 2, -s / 2, s / 2, s / 2 + 0.35 * s)
    return (-s / 2, -s / 2, s / 2, s / 2)


# ================================================================ 阀门
def _bowtie(b, s):
    b.outline_tri([(-s, -s), (-s, s), (0, 0)])
    b.outline_tri([(s, -s), (s, s), (0, 0)])


def _v_gate(b, s):
    _bowtie(b, s)  # 闸阀（表2-8 #1）：纯双三角，无阀杆


def _v_globe(b, s):
    _bowtie(b, s)  # 截止阀：纯双三角（表2-8）


def _v_check(b, s):
    b.tri([(-s, -s), (-s, s), (0, 0)])
    b.outline_tri([(s, -s), (s, s), (0, 0)])


def _v_ball(b, s):
    _bowtie(b, s)
    b.circle((0, 0), s * 0.55)


def _v_butterfly(b, s):
    b.rect((-s * 0.8, -s * 0.8), (s * 0.8, s * 0.8))  # 蝶阀：矩形+斜蝶板（表2-8）
    b.seg((-s * 0.5, s * 0.7), (s * 0.5, -s * 0.7))


def _v_plug(b, s):
    _bowtie(b, s)
    b.seg((-s * 0.4, -s * 0.4), (s * 0.4, s * 0.4))
    b.seg((-s * 0.4, s * 0.4), (s * 0.4, -s * 0.4))


def _v_throttle(b, s):
    b.tri([(-s, -s), (-s, s), (0, 0)])
    b.tri([(s, -s), (s, s), (0, 0)])


def _v_reducing(b, s):
    """减压阀（图例表2-8 序号13）：矩形框 + 框内两条对角线汇聚到右边中点(右指三角) +
    左侧粗实心箭头进流。沿管线方向为 +x。"""
    w, h = 1.7 * s, s
    b.rect((-w / 2, -h / 2), (w / 2, h / 2))
    b.seg((-w / 2, h / 2), (w / 2, 0))
    b.seg((-w / 2, -h / 2), (w / 2, 0))
    aw = 0.42 * s
    b.tri([(-w / 2 - 1.9 * s, -aw), (-w / 2 - 1.9 * s, aw), (-w / 2 - 0.9 * s, 0)])


def _v_safety(b, s):
    _bowtie(b, s)
    b.seg((0, 0), (0, s * 0.5))
    zs = 4
    pts = [(0, s * 0.5)]
    for i in range(zs):
        pts.append(((-s * 0.3 if i % 2 else s * 0.3), s * 0.5 + (i + 0.5) * s * 0.25))
    pts.append((0, s * 1.6))
    b.line(pts)
    b.seg((0, s * 1.25), (s * 0.9, s * 1.25))
    b.tri([(s * 0.9, s * 1.05), (s * 0.9, s * 1.45), (s * 1.35, s * 1.25)])


def _v_foot(b, s):
    b.outline_tri([(-s, -s), (-s, s), (0, 0)])
    b.seg((0, -s * 0.9), (s * 0.7, s * 0.4))
    b.seg((0, -s), (0, s))


def _v_needle(b, s):
    _bowtie(b, s)
    b.seg((0, 0), (0, s * 1.1))
    b.seg((-s * 0.45, s * 1.1), (s * 0.45, s * 1.1))


def _v_diaphragm(b, s):
    _bowtie(b, s)
    b.seg((0, -s), (0, s))
    b.arc((0, s * 0.3), s * 0.6, 0, 180)


def _v_control(b, s):
    """调节阀：双三角 + 阀杆 + 气动薄膜执行机构（圆顶，附表2-4）。
    阀杆必须从阀体中心一直连到膜头底边（1.35s），否则膜头与阀体断开。"""
    _bowtie(b, s)
    b.seg((0, 0), (0, s * 1.35))
    b.arc((0, s * 1.35), s * 0.55, 0, 180)
    b.seg((-s * 0.55, s * 1.35), (s * 0.55, s * 1.35))


VALVES = {
    "gate": (_v_gate, "闸阀"), "globe": (_v_globe, "截止阀"), "check": (_v_check, "止回阀"),
    "plug": (_v_plug, "旋塞"), "butterfly": (_v_butterfly, "蝶阀"), "ball": (_v_ball, "球阀"),
    "throttle": (_v_throttle, "节流阀"), "reducing": (_v_reducing, "减压阀"),
    "safety": (_v_safety, "弹簧式安全阀"), "foot": (_v_foot, "底阀"),
    "needle": (_v_needle, "针型阀"), "diaphragm": (_v_diaphragm, "隔膜阀"),
    "control": (_v_control, "调节阀(气动薄膜)"),
}

# 阀体沿流向对称的类型：180° 与 0° 等效、90° 与 -90° 等效——成图时把角度
# 归一化到 [0,180)，执行机构/阀杆恒朝上（横管）或朝左（立管），
# 不因流向反向而倒挂。check/reducing 有方向性，保持真实流向角。
SYM_VALVES = {"gate", "globe", "control", "ball", "butterfly", "needle",
              "plug", "throttle", "diaphragm"}


def draw_valve(doc, kind, x, y, rotation=0.0, size=6.0):
    fn, _ = VALVES[kind]
    b = B(doc, x, y, rotation, layer="PFD-VALVE", lw=25)
    fn(b, float(size))
    return {"kind": kind, "at": (x, y)}


# ================================================================ 仪表
def draw_instrument(doc, letters, number, x, y, mount=None, dia=8.0,
                    connect_to=None, signal="mechanical"):
    """仪表位号圆圈：上半写字母代号(检测参数+功能)，下半写数字位号。
    mount 省略时按位号字母推断：控制器（以 C 结尾，如 FIC/TIC/LIC/PIC）默认
    central（集中安装=圆内横线，HG/T 20519 附表），其余默认 field（就地=空心圆）。"""
    if mount is None:
        mount = "central" if str(letters).upper().endswith("C") else "field"
    r = dia / 2.0
    cad.add_circle(doc, (x, y), r, "PFD-INSTR", 25)
    if mount == "inpipe":
        # 嵌在管道中：横线穿出圆圈两侧
        cad.add_line(doc, (x - r * 1.6, y), (x + r * 1.6, y), "PFD-INSTR", 25)
    elif mount == "central":
        # 集中仪表盘安装：圆内水平线
        cad.add_line(doc, (x - r, y), (x + r, y), "PFD-INSTR", 25)
    elif mount == "local":
        # 就地仪表盘安装：圆内十字
        cad.add_line(doc, (x - r, y), (x + r, y), "PFD-INSTR", 25)
        cad.add_line(doc, (x, y - r), (x, y + r), "PFD-INSTR", 25)
    elif mount == "dcs":
        # 集散控制系统(DCS)：圆圈外接方框
        k = r * 1.25
        cad.add_polyline(doc, [(x - k, y - k), (x + k, y - k), (x + k, y + k), (x - k, y + k), (x - k, y - k)],
                         "PFD-INSTR", 25)
    elif mount == "plc":
        k = r * 0.6
        cad.add_polyline(doc, [(x - k, y - k), (x + k, y - k), (x + k, y + k), (x - k, y + k), (x - k, y - k)],
                         "PFD-INSTR", 25)
    h = dia * 0.3
    cad.add_text(doc, (x, y + dia * 0.24), h, letters, "PFD-INSTR", align="middle")
    cad.add_text(doc, (x, y - dia * 0.24), h, str(number), "PFD-INSTR", align="middle")
    if connect_to:
        cx, cy = connect_to
        ang = math.atan2(y - cy, x - cx)
        sx, sy = x - r * math.cos(ang), y - r * math.sin(ang)
        ln = cad.add_line(doc, (sx, sy), (cx, cy), "PFD-SIGNAL", 25)
        if signal == "pneumatic":
            cad.set_dashed(ln, 3.0)
        elif signal == "electric":
            cad.set_dashdot(ln, 3.0)
    return {"letters": letters, "number": number}
