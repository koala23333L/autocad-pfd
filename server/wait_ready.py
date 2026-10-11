# -*- coding: utf-8 -*-
"""等待 AutoCAD 就绪并清掉启动/登录模态框。"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cad

app = cad.get_app(create=True)
for t in range(120):
    try:
        v = app.Version
        print("ready:", v, flush=True)
        break
    except Exception:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dismiss_login.py")],
                       capture_output=True)
        time.sleep(3)
else:
    sys.exit("AutoCAD 未就绪")
