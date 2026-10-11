# -*- coding: utf-8 -*-
"""冒烟测试：连接本机 AutoCAD，绘制示例 PFD（严格对照图例表8-2 图例与第13页范例布局），
保存 DWG 并导出 PNG/PDF。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cad
import server

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

t0 = time.time()
print("[1] 连接 AutoCAD...", flush=True)
_app = cad.get_app(create=True)

def _dismiss():
    import subprocess
    try:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dismiss_login.py")],
                       capture_output=True, timeout=15)
    except Exception:
        pass

# 关闭全部遗留文档（含上次保存的 pfd_demo.dwg）并新建空白文档；
# 文档级调用可能被忙态/登录模态框拒绝，重试并在每次重试前关窗。
def _fresh_doc():
    docs = None
    for _try in range(30):
        try:
            cad.wait_ready(_app, timeout=60)
            docs = _app.Documents
            _ = docs.Count
            break
        except Exception:
            _dismiss()
            time.sleep(3)
    if docs is None:
        raise RuntimeError("AutoCAD 文档集合持续不可用（可能有无法关闭的模态框）")
    for i in range(docs.Count - 1, -1, -1):
        for _try in range(15):
            try:
                docs.Item(i).Close(False)
                break
            except Exception:
                _dismiss()
                time.sleep(2)
    _new = cad.new_document(_app)
    print("新建文档:", _new.Name, flush=True)

_fresh_doc()

spec = {
    "frame": "A0",
    "title": {
        "unit_name": "XX 化工工程有限公司",
        "project_name": "丁二烯抽提装置示例工程",
        "drawing_name": "丁二烯抽提工段\n物料流程图（PFD）",
        "drawing_no": "PFD-0001",
        "phase": "初步设计",
        "designer": "张三", "proofreader": "李四", "checker": "王五", "approver": "赵六",
        "dates": ["10.01", "10.02", "10.03", "10.05"],
        "date": "2026-10", "scale": "1:50", "sheet": 1, "total_sheets": 1,
    },
    "equipment": [
        {"kind": "storage_tank", "tag": "V101", "name": "原料罐", "x": 140, "y": 430, "size": 90,
         "options": {"nozzles": ["outlet"]}, "label_xy": [140, 500]},
        {"kind": "pump", "tag": "P101", "name": "原料泵", "x": 270, "y": 360, "size": 26,
         "label_xy": [270, 318]},
        {"kind": "heat_exchanger", "tag": "E101", "name": "原料预热器", "x": 430, "y": 420, "size": 34,
         "options": {"nozzles": ["tube_in", "tube_out"]}},
        {"kind": "column", "tag": "T101", "name": "脱丁烷塔", "x": 640, "y": 440, "size": 360,
         "options": {"internals": "tray", "n_trays": 14,
                     "nozzles": ["top", "top_L", "bottom", "side_L_up", "side_R_dn"]},
         "label_xy": [568, 640]},
        {"kind": "heat_exchanger", "tag": "E102", "name": "塔顶冷凝器", "x": 850, "y": 720, "size": 34,
         "label_xy": [905, 772]},
        {"kind": "vessel", "tag": "V102", "name": "回流罐", "x": 1030, "y": 560, "size": 90,
         "options": {"nozzles": ["top", "bottom"]}, "label_xy": [930, 600]},
        {"kind": "pump", "tag": "P102", "name": "回流泵", "x": 1080, "y": 440, "size": 26,
         "label_xy": [1145, 445]},
        {"kind": "reboiler", "tag": "E103", "name": "再沸器", "x": 760, "y": 200, "size": 70,
         "label_xy": [700, 240]},
    ],
    "pipes": [
        # 1 原料罐→原料泵（罐底出料，水平接入泵左侧吸入）
        {"from": ["V101", "outlet"], "via": [[140, 360]], "to": ["P101", "suction"],
         "kind": "main", "stream_no": 1,
         "label": {"material": "PL", "section": "08", "seq": "01", "dn": "80", "grade": "B1A"}},
        # 2 泵排出→预热器管程进口（左）；排出口在圆右缘切线 x=283
        {"from": ["P101", "discharge"], "via": [[283, 420]], "to": ["E101", "tube_in"],
         "kind": "main", "stream_no": 2},
        # 3 预热器管程出口（右）→塔进料
        {"from": ["E101", "tube_out"], "via": [[512, 420], [512, 530]], "to": ["T101", "side_L_up"],
         "kind": "main", "stream_no": 3,
         "label": {"material": "PL", "section": "08", "seq": "03", "dn": "80", "grade": "B1A",
                   "insulation": "C"}},
        # 4 塔顶蒸汽→冷凝器壳程进口（上）
        {"from": ["T101", "top"], "via": [[640, 760], [838.3, 760]], "to": ["E102", "shell_in"],
         "kind": "main", "stream_no": 4,
         "label": {"material": "PG", "section": "08", "seq": "04", "dn": "150", "grade": "B1A"}},
        # 5 冷凝器壳程出口（下）→回流罐顶
        {"from": ["E102", "shell_out"], "via": [[861.7, 640], [1030, 640]], "to": ["V102", "top"],
         "kind": "main", "stream_no": 5},
        # 6 回流罐底→回流泵吸入（左）
        {"from": ["V102", "bottom"], "via": [[1030, 440]], "to": ["P102", "suction"],
         "kind": "main", "stream_no": 6},
        # 7 回流泵排出→绕右上方→塔顶左回流口
        {"from": ["P102", "discharge"], "via": [[1130, 460.8], [1130, 795], [618.4, 795]],
         "to": ["T101", "top_L"], "kind": "main", "stream_no": 7},
        # 8 塔釜液→再沸器釜体底（process_in）
        {"from": ["T101", "bottom"], "via": [[640, 160], [788, 160]], "to": ["E103", "process_in"],
         "kind": "main", "stream_no": 8},
        # 9 再沸器汽相空间顶（vapor_out）→塔下部返回
        {"from": ["E103", "vapor_out"], "via": [[774, 350]], "to": ["T101", "side_R_dn"],
         "kind": "main", "stream_no": 9,
         "label": {"material": "PL", "section": "08", "seq": "09", "dn": "100", "grade": "B2A"}},
        # 10/11 冷凝器循环水（进出图纸，配去向符号）
        {"from": [732, 720], "to": ["E102", "tube_in"], "kind": "aux",
         "label": {"material": "CWS", "section": "08", "seq": "10", "dn": "50", "grade": "B1A"}},
        {"from": ["E102", "tube_out"], "to": [946, 720], "kind": "aux",
         "label": {"material": "CWR", "section": "08", "seq": "11", "dn": "50", "grade": "B1A"}},
    ],
    "connectors": [
        {"text": "08 10-50", "x": 700, "y": 720, "flow_dir": 1, "label": "来自循环水站"},
        {"text": "08 11-50", "x": 946, "y": 720, "flow_dir": 1, "label": "去循环水回水"},
    ],
    "instruments": [
        {"letters": "TIC", "number": "101", "x": 720, "y": 640, "mount": "field", "connect_to": [640, 640]},
        # PIC 引线若画在 x=700 会穿过循环水接入符号框(690..710)，左移至 660
        {"letters": "PIC", "number": "102", "x": 660, "y": 700, "mount": "field", "connect_to": [660, 760]},
        # LIC 接回流罐右侧平直筒体壁（x=1057, y542..578 为直壁段；600 已进入椭圆封头弧区）
        {"letters": "LIC", "number": "103", "x": 1110, "y": 570, "mount": "field", "connect_to": [1057, 570]},
        {"letters": "FIC", "number": "104", "x": 320, "y": 400, "mount": "field", "connect_to": [283, 400]},
    ],
    "heat_loads": [
        {"text": "Q=4250 kW", "x": 430, "y": 350},
        {"text": "Q=6300 kW", "x": 850, "y": 655},
        {"text": "Q=8100 kW", "x": 760, "y": 150},
    ],
    "table": {
        "x": 60, "y": 40, "col_w": 26, "row_h": 8, "label_w": 48,
        "streams": [
            {"no": 1, "T": 20.00, "P": 0.10, "vap": 0.00, "mol": 299.62, "mass": 16520.00,
             "comp": {"正丁烷": 330.40, "异丁烯": 3634.40, "1-丁烯": 2312.80,
                      "1,3-丁二烯": 7929.60, "乙腈": 0.00, "水": 129.07}},
            {"no": 2, "T": 60.00, "P": 0.60, "vap": 0.00, "mol": 299.62, "mass": 16520.00,
             "comp": {"正丁烷": 330.40, "异丁烯": 3634.40, "1-丁烯": 2312.80,
                      "1,3-丁二烯": 7929.60, "乙腈": 0.00, "水": 129.07}},
            {"no": 3, "T": 116.46, "P": 0.59, "vap": 0.00, "mol": 799.19, "mass": 34989.08,
             "comp": {"正丁烷": 0.00, "异丁烯": 0.00, "1-丁烯": 0.00,
                      "1,3-丁二烯": 2492.96, "乙腈": 30857.45, "水": 1532.08}},
            {"no": 4, "T": 48.03, "P": 0.54, "vap": 1.00, "mol": 609.52, "mass": 34000.00,
             "comp": {"正丁烷": 1321.60, "异丁烯": 14537.60, "1-丁烯": 9251.20,
                      "1,3-丁二烯": 806.54, "乙腈": 49.99, "水": 103.52}},
            {"no": 5, "T": 40.00, "P": 0.60, "vap": 0.00, "mol": 2595.43, "mass": 100442.87,
             "comp": {"正丁烷": 0.00, "异丁烯": 0.00, "1-丁烯": 0.00,
                      "1,3-丁二烯": 0.00, "乙腈": 95667.67, "水": 4775.20}},
        ],
    },
    "texts": [
        {"text": "至T-101回流", "x": 700, "y": 808, "height": 3.5, "align": "middle"},
    ],
    "save_as": os.path.join(OUT, "pfd_demo.dwg"),
    "export_png": os.path.join(OUT, "pfd_demo.png"),
    "export_pdf": os.path.join(OUT, "pfd_demo.pdf"),
}

print("[2] draw_pfd ...", flush=True)
res = None
for _attempt in range(3):
    try:
        res = server.draw_pfd(spec)
        break
    except Exception as e:
        print(f"  第{_attempt + 1}次绘制失败: {e}", flush=True)
        _dismiss()
        time.sleep(2)
        if _attempt < 2:
            try:
                _fresh_doc()   # 丢弃画了一半的文档，重来
            except Exception:
                pass
if res is None:
    raise RuntimeError("draw_pfd 连续 3 次失败")
print(json.dumps(res, ensure_ascii=False, default=str), flush=True)
print(f"[3] 完成，用时 {time.time()-t0:.0f}s", flush=True)
