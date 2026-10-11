# -*- coding: utf-8 -*-
"""列出所有可见顶层窗口（标题/类名/进程名），并尝试向疑似登录/模态窗口发关闭。"""
import ctypes
import ctypes.wintypes as wt
import sys

user32 = ctypes.windll.user32
psapi = ctypes.windll.psapi

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
GetWindowText = user32.GetWindowTextW
GetWindowTextLength = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
GetClassName = user32.GetClassNameW
GetWindowThreadProcessId = user32.GetWindowThreadProcessId

def proc_name(pid):
    PROCESS_QUERY_LIMITED = 0x1000
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED | 0x0400, False, pid)
    if not h:
        return "?"
    buf = (wt.WCHAR * 260)()
    ctypes.windll.psapi.GetModuleBaseNameW(h, None, buf, 260)
    ctypes.windll.kernel32.CloseHandle(h)
    return buf.value

rows = []
def cb(hwnd, lparam):
    if not IsWindowVisible(hwnd):
        return True
    n = GetWindowTextLength(hwnd)
    title = (" " * (n + 1))
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowText(hwnd, buf, n + 1)
    cls = ctypes.create_unicode_buffer(256)
    GetClassName(hwnd, cls, 256)
    pid = wt.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if buf.value or cls.value in ("#32770",):
        rows.append((hwnd, pid.value, proc_name(pid.value), cls.value, buf.value))
    return True

EnumWindows(EnumWindowsProc(cb), 0)
for hwnd, pid, pname, cls, title in rows:
    if any(k in (pname or "").lower() for k in ("acad", "adsk", "autodesk", "aapps", "adapp", "gsdk")) or "登录" in title or "login" in title.lower() or "Autodesk" in title:
        print(hex(hwnd), pid, pname, "|", cls, "|", title)
