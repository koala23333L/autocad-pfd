# -*- coding: utf-8 -*-
"""关闭所有可见的 #32770 模态对话框（含跨进程的"登录 - Autodesk"窗口）。
只发 ESC / WM_CLOSE，绝不输入任何凭据。"""
import ctypes
import sys
sys.stdout.reconfigure(encoding="utf-8")

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

WM_CLOSE = 0x0010
targets = []
def cb(hwnd, lp):
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, 512)
    if cls.value == "#32770" and user32.IsWindowVisible(hwnd):
        targets.append((hwnd, title.value))
    return True
user32.EnumWindows(EnumWindowsProc(cb), 0)

for h, title in targets:
    if "登录" in title or "login" in title.lower() or "sign in" in title.lower():
        # 登录框对 ESC 不敏感，直接 WM_CLOSE 关闭（等同用户点 X）
        print("CLOSE ->", title)
        user32.PostMessageW(h, WM_CLOSE, 0, 0)
    else:
        print("ESC ->", title)
        user32.PostMessageW(h, 0x0100, 0x1B, 0)
        user32.PostMessageW(h, 0x0101, 0x1B, 0)
        user32.PostMessageW(h, WM_CLOSE, 0, 0)
