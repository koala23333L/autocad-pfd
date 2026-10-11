# -*- coding: utf-8 -*-
"""最终校验：编译、MCP 握手、工具列表、清单一致性。"""
import asyncio
import glob
import json
import os
import py_compile
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 1. 编译
for f in glob.glob(os.path.join(HERE, "*.py")):
    py_compile.compile(f, doraise=True)
print("[1] compile ok")

# 2. MCP 握手 + 工具列表
sys.path.insert(0, HERE)
import server  # noqa

async def main():
    tools = await server.mcp.list_tools()
    names = sorted(t.name for t in tools)
    print(f"[2] mcp ok, {len(names)} tools:")
    for n in names:
        print("   -", n)

asyncio.run(main())

# 3. 清单一致性
pj = json.load(open(os.path.join(ROOT, ".zcode-plugin", "plugin.json"), encoding="utf-8"))
mj = json.load(open(os.path.join(ROOT, ".mcp.json"), encoding="utf-8"))
mk = json.load(open(os.path.join(ROOT, "..", "marketplace.json"), encoding="utf-8"))
assert pj["name"] == "autocad-pfd"
assert mj["mcpServers"]["autocad-pfd"]["args"][0].endswith("server/server.py")
entry = mk["plugins"][0]
assert entry["name"] == pj["name"] and entry["version"] == pj["version"]
assert os.path.exists(os.path.join(ROOT, "skills", "autocad-pfd", "SKILL.md"))
print("[3] manifests consistent:", pj["name"], pj["version"], "| market:", mk["name"])
print("ALL CHECKS PASSED")
