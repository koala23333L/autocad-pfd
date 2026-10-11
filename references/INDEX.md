# 图例参考资料目录（references/）

绘制任何不熟悉的设备前，**先 Read 对应参考图核对画法**，再写符号/规格。
可用 MCP 工具 `list_references` 获取本目录实时清单。

## generated/ —— 本 MCP 全部符号的成图基准
- symbols_all.png：全部设备符号总表（A0 图幅，由 draw_pfd 实绘导出）。
  每次修改 symbols.py 后应重新生成并比对。

## 自备参考资料（可选）
- 可自行放入设备图例扫描件 / 制图手册裁剪图 / 参考 PFD 截图等，
  按子目录归类（如 `my_legends/`），`list_references` 会动态扫描列出全部文件。
- 参考件只用于**核对画法与图例样式**；布局与走线一律按本 MCP 的预检规则
  与 SKILL.md 红线自行生成，不照抄任何来源的排布。
