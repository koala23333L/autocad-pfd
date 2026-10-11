# autocad-pfd — 化工 PFD 图绘制 MCP 服务器（驱动本机 AutoCAD，即插即用）

通过 Windows COM 自动化控制本机 AutoCAD（**AutoCAD 2027 中文版**实测通过），按
**HG/T 20519-2009** 及化工 PFD/PID 制图规范绘制工艺物料流程图（PFD），导出 DWG / PDF / PNG。
设备画法逐条对照常用化工图例（设备/阀门/仪表）并经多轮实图校验；内置**布局预检器**，
几何红线（斜线/穿设备/压字/悬空接管/入标题栏等）不过检直接拒绝成图。

## 安装（即插即用）

1. 要求：Windows + 本机 AutoCAD（支持 `AutoCAD.Application` COM 的版本）+ Python 3.10+。
2. 安装依赖：`pip install -r server/requirements.txt`（mcp、pywin32、pypdfium2、pillow）。
3. 将本插件目录放入 ZCode 插件目录（或在 ZCode 中"添加本地插件"指向本目录），
   重启会话后 `autocad-pfd` MCP 工具与 `autocad-pfd` 技能即自动加载。

## 工具一览

| 工具 | 说明 |
|---|---|
| `draw_pfd(spec)` | 一份 JSON spec 一次画出整张 PFD。**成图前自动布局预检，硬伤拒绝成图并返回违规清单**；缺 x/y 的设备自动排布（自左向右流式、行满换行）；`auto_stream_no:true` 自动补流股号；自动走线避让已画管线 |
| `check_pfd_layout(spec)` | 只预检不画图：errors（必须修复）/warnings（提醒）清单 |
| `list_references()` | 列出图例参考资料（符号成图总表；自备扫描件放入 references/ 后动态扫描） |
| `add_equipment` 等 | 21 类设备图例（返回端口坐标+端口方向，nozzles 过滤）：泵/压缩机/风机/水环真空泵/换热器/空冷器/塔(板式·填料)/容器/分离器(闪蒸罐)/釜式再沸器/混合器(倒三角)/固定床反应器/搅拌釜/分层器/旋风分离器/喷射器/火炬/压滤机/离心机/储罐/加热炉 |
| `add_pipe` / `add_valve` / `add_instrument` 等 | 图元级逐步绘制（正交走线+流向箭头+断线留缺口流股号+表2-8 阀门（含调节阀气动薄膜头）+仪表圆圈） |
| `draw_frame` / `draw_material_table` / `get_standards` 等 | 图框标题栏 / 物料表 / 规范常量 |

## 推荐工作流（新任务一次成图）

1. 写 spec（设备 kind/tag/name/nozzles/label_xy + 管线 from/to/via + 文本标注来源去向）；
   **设备坐标可省略**（自动排布），管线复杂走向给 via 沿端口轴线正交引入。
2. `check_pfd_layout(spec)` → 按清单修 spec → **errors 清零**。
3. `draw_pfd(spec)`（内部再跑一遍预检）→ 得 dwg/png/pdf。
4. `python server/inspect_png.py 导出的png spec路径` → 逐台设备特写 qa_*.png 目视复核。
5. AutoCAD 打开 DWG（ZOOM E）交付。

几何红线（斜线、穿设备、压字、悬空接管、入标题栏、内件悬空等）由预检器**强制拦截**；
工艺逻辑（多股进料进混合器、来源/去向标注、工段组合）按任务描述与 SKILL.md 红线清单执行。
设备画法标准与全部红线见 `skills/autocad-pfd/SKILL.md`。

## 依赖

- Windows + 本机 AutoCAD；Python 3.10+：`pip install -r server/requirements.txt`

## 目录

```
autocad-pfd/
  .zcode-plugin/plugin.json     插件清单
  .mcp.json                     MCP 服务器定义（stdio: python server/server.py）
  server/
    server.py                   MCP 工具层（draw_pfd / check_pfd_layout / 图元工具）
    layout_check.py             布局预检器（9 类几何红线，errors 拒绝成图）
    cad.py                      COM 连接/图元/图层/导出（2027 API 适配）
    symbols.py                  设备/阀门/仪表图例库（含端口与方向）
    sheets.py                   图框/标题栏/设备一览/流股号/去向符号
    standards.py                HG/T 20519 规范常量
    inspect_png.py              成图 QA：图框标定+逐台设备裁剪特写
    dismiss_login.py / wait_ready.py   AutoCAD 弹窗处理/就绪等待（只关窗不输凭据）
    smoke_test.py               冒烟测试（丁二烯示例 PFD）
  skills/autocad-pfd/SKILL.md   使用指南 + 一次成图 checklist + 画法红线记录
```

## 已知环境坑（已在代码中处理）

- 动态绑定下 AutoCAD 子对象解析失败 → 统一 `gencache.EnsureDispatch` 早期绑定。
- `IAcadPlot` 2027 无配置属性 → Model 布局对象 + `StandardScale=0`（Fit）+ `BACKGROUNDPLOT=0`。
- PNG 设备无法设纸张 → PNG 经 PDF 中转用 pypdfium2 渲染。
- 教育版"登录 - Autodesk"模态框致 COM 拒绝 → `dismiss_login.py`（只关窗不输凭据）。
- 流股号禁用白色遮罩（深色背景数字不可读）→ 断线留缺口画法。
