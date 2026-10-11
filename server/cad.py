# -*- coding: utf-8 -*-
"""AutoCAD COM 连接与图元原语（模型空间，1 单位 = 1 mm）。

所有 COM 调用通过全局锁串行化；每个工作线程首次调用时 CoInitialize。
"""
import math
import os
import threading
import time

import pythoncom
import win32com.client as win32
from win32com.client import VARIANT

PROGID = "AutoCAD.Application"

_lock = threading.RLock()
_tls = threading.local()


def lock():
    return _lock


def _coinit():
    if not getattr(_tls, "inited", False):
        pythoncom.CoInitialize()
        _tls.inited = True


def _find_acad_exe():
    r"""从注册表定位 acad.exe（HKLM Autodesk\AutoCAD\*\ACAD-*\ACAD AcadLocation，
    其次 Uninstall 的 InstallLocation）。"""
    import winreg
    locs = []
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\AutoCAD")
        for i in range(winreg.QueryInfoKey(k)[0]):
            rel = winreg.EnumKey(k, i)
            try:
                k2 = winreg.OpenKey(k, rel)
                for j in range(winreg.QueryInfoKey(k2)[0]):
                    sub = winreg.EnumKey(k2, j)
                    if sub.upper().startswith("ACAD"):
                        try:
                            k3 = winreg.OpenKey(k2, sub + r"\ACAD")
                            v, _ = winreg.QueryValueEx(k3, "AcadLocation")
                            if v:
                                locs.append(v)
                        except OSError:
                            pass
            except OSError:
                pass
    except OSError:
        pass
    try:
        ku = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        for i in range(winreg.QueryInfoKey(ku)[0]):
            try:
                k4 = winreg.OpenKey(ku, winreg.EnumKey(ku, i))
                dn, _ = winreg.QueryValueEx(k4, "DisplayName")
                if "AutoCAD" in dn and "Update" not in dn and "MCP" not in dn:
                    try:
                        il, _ = winreg.QueryValueEx(k4, "InstallLocation")
                        if il:
                            locs.append(il)
                    except OSError:
                        pass
            except OSError:
                pass
    except OSError:
        pass
    for loc in locs:
        exe = os.path.join(loc, "acad.exe")
        if os.path.exists(exe):
            return exe
    return None


def _launch_process():
    import subprocess
    exe = _find_acad_exe()
    if not exe:
        raise RuntimeError("注册表中未找到 AutoCAD 安装路径，请手动启动 AutoCAD 后重试。")
    subprocess.Popen([exe])
    return exe


def _wrap(app):
    """动态绑定下 AutoCAD 子对象(Documents/ActiveDocument)解析会失败，统一转 makepy 早期绑定。"""
    try:
        return win32.gencache.EnsureDispatch(app)
    except Exception:
        return app


def get_app(create=True, wait_s=300):
    """连接正在运行的 AutoCAD。未运行时：先试 COM 自动启动（DispatchEx），失败则直接
    启动 acad.exe 并轮询注册，最长等待 wait_s 秒（首次冷启动约 1~3 分钟）。"""
    import time
    _coinit()
    try:
        return _wrap(win32.GetActiveObject(PROGID))
    except Exception:
        if not create:
            raise RuntimeError("AutoCAD 未在运行。请先手动启动 AutoCAD，或调用带 create=True 的工具。")
    try:
        return _wrap(win32.DispatchEx(PROGID))
    except Exception:
        _launch_process()
    deadline = time.time() + wait_s
    last_err = None
    while time.time() < deadline:
        try:
            return _wrap(win32.GetActiveObject(PROGID))
        except Exception as e:
            last_err = e
            time.sleep(5)
    raise RuntimeError(f"等待 AutoCAD 启动超时（{wait_s}s）: {last_err}")


def active_doc(app, wait_s=0.0):
    """取当前文档并验证 COM 可用；AutoCAD 刚启动时对象可能未就绪，用 wait_s 重试。"""
    import time
    deadline = time.time() + max(wait_s, 0)
    last = None
    while True:
        try:
            d = app.ActiveDocument
            _ = d.Name  # 触发真实解析，确认服务器就绪
            return d
        except Exception as e:
            last = e
            if time.time() >= deadline:
                return None
            time.sleep(2)


def wait_ready(app, timeout=90.0):
    """轮询直到 AutoCAD 接受 COM 调用（忙/被呼叫方拒绝时重试）。"""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            _ = app.Version  # 应用级 ping，无文档时也可用
            return True
        except Exception as e:
            last = e
            time.sleep(1.0)
    raise RuntimeError(f"AutoCAD 持续忙/拒绝调用（可能有对话框未关闭）: {last}")


def new_document(app):
    tpl = ""
    try:
        cand = os.path.join(app.Path, "Template", "acadiso.dwt")
        if cand and os.path.exists(cand):
            tpl = cand
    except Exception:
        pass
    wait_ready(app)
    for i in range(10):
        try:
            return app.Documents.Add(tpl) if tpl else app.Documents.Add()
        except Exception as e:
            if getattr(e, "hresult", None) == -2147418111:
                time.sleep(1.5)
                continue
            raise
    raise RuntimeError("新建文档失败：AutoCAD 持续拒绝调用")


# ---------------------------------------------------------------- 点与图元
def P(x, y):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (float(x), float(y), 0.0))


def PP(points):
    flat = []
    for p in points:
        flat.extend([float(p[0]), float(p[1]), 0.0])
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, flat)


def add_line(doc, p1, p2, layer="PFD-EQUIP", lw=None):
    o = doc.ModelSpace.AddLine(P(*p1), P(*p2))
    o.Layer = layer
    if lw:
        o.Lineweight = int(lw)
    return o


def add_polyline(doc, points, layer="PFD-EQUIP", lw=None, closed=False):
    o = doc.ModelSpace.AddPolyline(PP(points))
    if closed:
        o.Closed = True
    o.Layer = layer
    if lw:
        o.Lineweight = int(lw)
    return o


def add_circle(doc, center, radius, layer="PFD-EQUIP", lw=None):
    o = doc.ModelSpace.AddCircle(P(*center), float(radius))
    o.Layer = layer
    if lw:
        o.Lineweight = int(lw)
    return o


def add_arc(doc, center, radius, a1_deg, a2_deg, layer="PFD-EQUIP", lw=None):
    o = doc.ModelSpace.AddArc(P(*center), float(radius), math.radians(a1_deg), math.radians(a2_deg))
    o.Layer = layer
    if lw:
        o.Lineweight = int(lw)
    return o


_ALIGN = {"left": 0, "center": 1, "right": 2, "middle": 4}


def add_text(doc, ins, height, text, layer="PFD-TEXT", rotation=0.0, align="middle", style="GBCENT"):
    """工程字文本。align: left/center(基线居中)/right/middle(完全居中)。"""
    t = doc.ModelSpace.AddText(" ", P(*ins), float(height))
    try:
        t.StyleName = style
    except Exception:
        pass
    t.Layer = layer
    t.Rotation = math.radians(rotation)
    a = _ALIGN[align]
    t.Alignment = a
    if a != 0:
        t.TextAlignmentPoint = P(*ins)
    t.TextString = str(text)
    return t


def add_solid_tri(doc, pts, layer="PFD-EQUIP", lw=None):
    """实心三角形（4 点 2D solid，第 4 点重合）。pts = [(x,y),(x,y),(x,y)]"""
    p1, p2, p3 = pts
    o = doc.ModelSpace.AddSolid(P(*p1), P(*p2), P(*p3), P(*p3))
    o.Layer = layer
    if lw:
        o.Lineweight = int(lw)
    return o


def add_filled_circle(doc, c, r, layer="PFD-MASK", n=24):
    """白色实心圆（扇形 solid 拼合），用于流股号圆圈压断管线。"""
    import math as _m
    cx, cy = c
    pts = [(cx + r * _m.cos(2 * _m.pi * k / n), cy + r * _m.sin(2 * _m.pi * k / n))
           for k in range(n)]
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        o = doc.ModelSpace.AddSolid(P(*a), P(*b), P(cx, cy), P(cx, cy))
        o.Layer = layer


def set_dashed(obj, scale=5.0):
    try:
        obj.Document.Linetypes.Load("DASHED", "acadiso.lin")
    except Exception:
        pass
    try:
        obj.Linetype = "DASHED"
        obj.LinetypeScale = scale
    except Exception:
        pass


def set_dashdot(obj, scale=5.0):
    try:
        obj.Document.Linetypes.Load("DASHDOT", "acadiso.lin")
    except Exception:
        pass
    try:
        obj.Linetype = "DASHDOT"
        obj.LinetypeScale = scale
    except Exception:
        pass


# ---------------------------------------------------------------- 图层 / 文字样式 / 环境
LAYERS = [
    # (名称, 线宽 COM 值, ACI 颜色) —— 全部单色(7)，对照标准图例：打印版不能体现颜色区别
    ("PFD-PIPE-MAIN", 100, 7),
    ("PFD-PIPE-AUX", 50, 7),
    ("PFD-EQUIP", 25, 7),
    ("PFD-VALVE", 25, 7),
    ("PFD-INSTR", 25, 7),
    ("PFD-SIGNAL", 25, 7),
    ("PFD-TEXT", 25, 7),
    ("PFD-TABLE", 25, 7),
    ("PFD-FRAME", 50, 7),
    ("PFD-MASK", 25, 255),  # 绝对白色填充遮罩（流股号圆圈压断管线用；ACI7 打印会变黑）
]


def ensure_layers(doc):
    for name, lw, color in LAYERS:
        try:
            lyr = doc.Layers.Add(name)
        except Exception:
            lyr = doc.Layers.Item(name)
        lyr.color = color  # 类型库中为小写 color
        lyr.Lineweight = lw
    try:
        st = doc.TextStyles.Add("GBCENT")
    except Exception:
        st = doc.TextStyles.Item("GBCENT")
    # 早期绑定下 SetFont 必须给全 5 个参数 (Typeface, Bold, Italic, Charset, PitchAndFamily)
    ok = False
    for args in (("gbenor.shx", False, False, 0, 257), ("宋体", False, False, 134, 34)):
        try:
            st.SetFont(*args)
            ok = True
            break
        except Exception:
            continue
    if ok and args[0].endswith(".shx"):
        try:
            st.BigFontFile = "gbcbig.shx"
        except Exception:
            pass
    try:
        doc.ActiveTextStyle = st
    except Exception:
        pass
    try:
        doc.SetVariable("INSUNITS", 4)  # mm
    except Exception:
        pass
    try:
        doc.LineweightDisplay = True
    except Exception:
        pass
    try:
        doc.SetVariable("TEXTQLTY", 50)
    except Exception:
        pass


# ---------------------------------------------------------------- 导出
# AutoCAD 2027 的 IAcadPlot 不再暴露配置属性；IAcadLayout 继承 IAcadPlotConfiguration，
# 直接在 Model 布局上设置打印参数，再传给 PlotToFile(path, layout)。
def _model_layout(doc):
    for i in range(doc.Layouts.Count):
        lay = doc.Layouts.Item(i)
        try:
            nm = str(lay.Name).lower()
        except Exception:
            nm = ""
        if nm in ("model", "模型"):
            return lay
    return doc.Layouts.Item(0)


def _setup_layout_plot(lay, pc3, units_mm=True):
    """2027 版 IAcadLayout：StandardScale 是枚举(0=acScaleToFit)，不能传字符串；
    默认设备即 DWG To PDF.pc3。逐项 try，单项失败不影响其余。"""
    def _try(fn):
        try:
            fn()
        except Exception:
            pass
    if pc3:
        _try(lambda: setattr(lay, "ConfigName", pc3))
    _try(lambda: lay.RefreshPlotDeviceInfo())
    _try(lambda: setattr(lay, "PaperUnits", 1 if units_mm else 2))
    _try(lambda: setattr(lay, "PlotType", 1))       # acExtents
    _try(lambda: setattr(lay, "UseStandardScale", True))
    _try(lambda: setattr(lay, "StandardScale", 0))  # 枚举 0 = acScaleToFit
    _try(lambda: setattr(lay, "CenterPlot", True))
    _try(lambda: setattr(lay, "PlotWithLineweights", True))
    _try(lambda: setattr(lay, "ScaleLineweights", False))
    _try(lambda: setattr(lay, "PlotRotation", 0))


def _largest_pixel_paper(lay, min_px=2000):
    try:
        names = list(lay.GetCanonicalMediaNames())
    except Exception:
        return None
    best, best_area = None, 0
    for name in names:
        s = str(name)
        if "pixel" in s.lower():
            digits = [int(t) for t in "".join(c if c.isdigit() else " " for c in s).split()]
            if len(digits) >= 2 and digits[0] >= min_px and digits[0] * digits[1] > best_area:
                best, best_area = s, digits[0] * digits[1]
    return best


def plot_to_file(doc, path, pc3=None):
    """导出当前图形范围（Extents+适应图纸+线宽）。2027 版需 BACKGROUNDPLOT=0 同步出图。"""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    lay = _model_layout(doc)
    _setup_layout_plot(lay, pc3)
    try:
        doc.SetVariable("BACKGROUNDPLOT", 0)
    except Exception:
        pass
    try:
        doc.Plot.QuietErrorMode = True
    except Exception:
        pass
    doc.Plot.PlotToFile(path)
    deadline = time.time() + 60
    while time.time() < deadline:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True, path
        time.sleep(0.5)
    return os.path.exists(path), path


def export_pdf(doc, path):
    return plot_to_file(doc, path, "DWG To PDF.pc3")


def export_png(doc, path, scale=3.0):
    """PNG 导出：先出 PDF 再高清渲染（2027 布局对象无法设置 PNG 设备纸张尺寸）。"""
    path = os.path.abspath(path)
    tmp_pdf = path + ".tmp.pdf"
    ok, tmp_pdf = plot_to_file(doc, tmp_pdf, "DWG To PDF.pc3")
    if not ok:
        raise RuntimeError("PDF 中间导出失败，无法生成 PNG")
    ok2 = False
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(tmp_pdf)
        bitmap = pdf[0].render(scale=scale)  # scale=3 ≈ 216dpi
        bitmap.to_pil().save(path)
        ok2 = os.path.exists(path) and os.path.getsize(path) > 0
    finally:
        try:
            os.remove(tmp_pdf)
        except OSError:
            pass
    if not ok2:
        raise RuntimeError("pypdfium2 渲染 PNG 失败（pip install pypdfium2）")
    return True, path


def zoom_extents(doc):
    try:
        doc.ActiveViewport.ZoomExtents()
    except Exception:
        try:
            doc.SendCommand("ZOOM _E ")
        except Exception:
            pass


# ---------------------------------------------------------------- 几何辅助
def rot(dx, dy, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return dx * c - dy * s, dx * s + dy * c


def transform(pt, ox, oy, deg):
    x, y = rot(pt[0], pt[1], deg)
    return (ox + x, oy + y)
