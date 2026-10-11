# -*- coding: utf-8 -*-
"""在 AutoCAD 中打开 pfd_demo.dwg，置前显示并 Zoom Extents，让用户直接看实物图。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cad

DWG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "pfd_demo.dwg")
if not os.path.exists(DWG):
    raise SystemExit("找不到 " + DWG)

app = cad.get_app(create=True)
cad.wait_ready(app, timeout=120)

# 关闭其他遗留文档，只留本图
try:
    docs = app.Documents
    for i in range(docs.Count - 1, -1, -1):
        d = docs.Item(i)
        if os.path.normcase(os.path.abspath(d.FullName)) != os.path.normcase(os.path.abspath(DWG)):
            d.Close(False)
except Exception as e:
    print("关闭遗留文档失败（忽略）:", e)

# 已打开则直接激活，否则打开
opened = False
try:
    docs = app.Documents
    for i in range(docs.Count):
        if os.path.normcase(os.path.abspath(docs.Item(i).FullName)) == os.path.normcase(os.path.abspath(DWG)):
            opened = True
            break
except Exception:
    pass
if not opened:
    doc = app.Documents.Open(DWG)
    print("已打开:", doc.Name)
else:
    doc = app.ActiveDocument
    print("已存在，激活:", doc.Name)

app.Visible = True
try:
    app.WindowState = 3  # acMax
except Exception:
    pass
try:
    app.ActiveDocument = doc
except Exception:
    pass
cad.zoom_extents(doc)
print("AutoCAD 已置前显示:", DWG)
