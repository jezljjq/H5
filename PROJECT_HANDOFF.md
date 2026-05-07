# 全自动辅助助手项目交接文档

更新时间：2026-05-07

## 1. 项目目标与关键决策

项目路径：`D:\Ai\codex\H5`

项目名称：**全自动辅助助手**

目标：为《斗罗大陆H5》多开微端/客户端提供界面级图像识别、任务流程编排和后台点击辅助。

关键边界：

- 只做界面级识图和鼠标点击辅助。
- 不读取或修改游戏内存。
- 不拦截网络请求。
- 不修改客户端文件。
- 自动运行必须后台处理，不能主动抢前台。
- 遵守项目指令：禁止批量删除文件。

核心技术决策：

- 统一使用 **32 位 Python 3.14** 运行：
  `C:\Users\Administrator\AppData\Local\Programs\Python\Python314-32\python.exe`
- UI 从 `PySide6` 迁移为 `PyQt5`，因为 `PySide6` 没有可用的 Windows 32 位 Python 包。
- 大漠插件使用当前 32 位 `dm.dll`，通过 32 位 Python 进程内 `win32com.client.Dispatch("dm.dmsoft")` 直接调用。
- 已废弃 `cscript.exe` / VBS / helper 子进程桥接方案。
- 大漠优先负责后台绑定、后台识图和点击；OpenCV/Win32 保留为回退能力。
- 模板目录默认是 `assets/templates/`，模板支持 `.bmp`、`.png`、`.jpg`、`.jpeg`。
- 软件启动后不自动添加窗口，由用户手动扫描或拖动准星绑定窗口。
- 窗口任务绑定按窗口标题保存，不按 hwnd 保存，因为 hwnd 每次启动可能变化。

## 2. 当前已完成内容

### 启动与运行环境

- 已迁移到 `PyQt5` 主界面。
- `requirements.txt` 当前依赖：
  - `PyQt5`
  - `opencv-python`
  - `numpy`
  - `pywin32`
- 推荐安装命令：

```powershell
py -3.14-32 -m pip install -r D:\Ai\codex\H5\requirements.txt
```

- 推荐启动命令：

```powershell
py -3.14-32 D:\Ai\codex\H5\main.py
```

- `main.py` 保留 Windows 管理员自提权逻辑。
- 桌面快捷方式和开始菜单快捷方式已指向 32 位 `pythonw.exe`：
  - `C:\Users\Administrator\Desktop\全自动辅助助手.lnk`
  - `C:\Users\Administrator\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\全自动辅助助手.lnk`

### UI 与交互

- 主界面标题：`全自动辅助助手`。
- 当前界面结构：
  - 顶部：标题、状态条、全局按钮。
  - 左侧：多开窗口管理（窗口列表显示窗口标题、队列数量、当前执行任务和状态）。
  - 中间：任务模板库 + 当前窗口任务队列（上半区），下半区配置工作台（QTabWidget 分离普通流程和自动抢拍）。
  - 右侧：全局识别参数、当前步骤详情（普通流程）/ 自动抢拍运行状态（抢拍模式）、运行日志。
- 方案/plan 管理控件已从主界面布局中移除（plan_combo、task_combo、task_type_combo、新增/重命名/删除方案按钮、新增/复制/删除任务按钮不再加入布局）。
- 中间区域标题改为"任务模板库 + 当前窗口任务队列"。
- 新增 QTabWidget 将下半区配置拆分为两个 Tab：
  - Tab 0「普通流程配置」：显示流程路径、流程步骤表、步骤操作按钮、当前步骤详情。
  - Tab 1「自动抢拍配置」：只显示抢拍配置面板，不显示流程路径和步骤表。
- 任务模板列表显示格式改为"任务名（任务类型）"。
- 默认识别阈值和默认重试次数位于右侧"全局识别参数"，不要写回中间区域。
- UI 已按 `ui-ux-pro-max` 的工具型控制台原则做轻量优化：
  - 更清晰的青绿色控制台配色。
  - 更大的按钮点击区域。
  - 更明显的焦点、悬停、按下、危险操作状态。
- 运行日志支持双击清空。
- 手动添加窗口入口已从界面移除，保留扫描和准星绑定两种添加方式。
- 准星绑定按钮已移动到原手动添加窗口按钮位置，显示为准星样式。
- 流程表的"模板组"列显示摘要；双击模板组或点击"编辑模板组"会打开弹窗。
- 模板组弹窗支持添加图片、截图添加、移除选中模板。
- 截图裁剪流程已改为先截图/框选，确认裁剪区域后再输入文件名保存。
- 底部旧的全局"单倍状态模板 / 双倍状态模板 / 单倍动作模板 / 双倍动作模板"配置已删除；单双倍处理统一走流程步骤。
- 准星绑定窗口已修复 PyQt5 鼠标事件闪退：
  - PySide6 风格：`globalPosition()`
  - PyQt5 风格：`globalPos()`
  - 通过 `_event_pos()` / `_event_global_pos()` 兼容。

### 多窗口管理

- 支持按关键词扫描窗口，默认关键词是 `斗罗大陆H5`。
- 支持拖动准星到游戏窗口后松开绑定窗口。
- 支持多选窗口后批量移除。
- 支持多选窗口后批量分配当前任务。
- 支持右键菜单：
  - `批量分配当前任务`
  - `移除选中窗口`
- 软件启动时窗口列表为空，必须由用户主动添加。

### 任务模板与窗口队列

- 主界面运行关系是 `窗口 -> 任务队列`，方案仅作为内部兼容数据和任务模板来源保留。
- 主界面不再显示方案下拉框、新增方案、重命名方案、删除方案等方案层级控件。
- 左侧窗口区只负责窗口管理和窗口队列摘要。
- 中间上半区显示"可选任务（模板库）"和"当前窗口任务队列"。
- 当前窗口任务队列支持多个任务，队列项显示序号、任务名称、任务类型和启用状态。
- 任务模板库第一版使用模板引用，窗口队列里的任务仍引用任务模板配置。
- 支持新增、删除、上移、下移流程步骤。
- 每个步骤支持：
  - 启用/禁用。
  - 多模板组，流程表显示摘要，弹窗中维护完整列表。
  - ROI：`x1,y1,x2,y2`。
  - 点击后等待。
  - 找到后的动作：`click`、`jump`、`click_jump`、`stop`。
  - 找不到后的动作：`skip`、`jump`、`restart`、`fail`。
- 单步阈值和单步重试说明：
  - 底层 `FlowStep` 仍兼容旧配置中的 `threshold` / `retries` 字段。
  - 当前 UI 不显示、不编辑单步阈值和单步重试。
  - 当前识别默认使用右侧"全局识别参数"中的默认识别阈值和默认重试次数。
  - 不要把单步阈值和单步重试重新加回 UI。
- `FlowRunner` 已有跳转次数保护，避免流程死循环。
- `FlowRunner` 不再在流程结束后执行旧的全局单双倍模板逻辑；单双倍选择由普通流程步骤负责。

### 识图与点击

- 自动运行优先走大漠：
  - 32 位 Python 进程内直接创建 `dm.dmsoft`。
  - 每个窗口第一次使用时 `BindWindow(hwnd, "normal", mode, "windows", 0)`。
  - 支持模式尝试顺序：`windows3`、`windows2`、`windows`。
  - 绑定成功后复用同一会话执行 `FindPic + MoveTo + LeftClick`。
  - 任务结束后统一 `UnBindWindow`。
- 大漠识图返回模板左上角，`automation.py` 会读取模板尺寸并转换成中心点点击。
- 同一步骤的同目录模板组会合并为 `a.bmp|b.bmp|c.bmp` 一次调用大漠 `FindPic`，减少 COM 调用次数。
- 大漠会话会缓存当前 `SetPath` 目录，同一模板目录连续识别时不会重复调用 `SetPath`。
- 大漠不可用时回退：
  - OpenCV 后台截图识别。
  - Win32 `PostMessage` 后台点击。
- 自动运行使用后台截图/后台识图，不主动置前。
- "截图裁剪模板"使用前台截图，便于人工裁剪模板；确认裁剪区域后再命名保存。
- "测试当前步骤识别"只识别，不点击。
- 模板图片已做缓存，避免循环中重复 `cv2.imread()` 同一张模板。
- 支持 `.bmp` 图片识别。

### 旧脚本与文档资源

- 熊猫精灵导出脚本解析器仍保留：
  - 读取 GB18030 文本。
  - 解析 `INSERT INTO 步骤`。
  - 解析图片组。
  - 提取 Base64 BMP。
  - 导出模板图片。
- 大漠 CHM 文档已提取：
  - CHM 副本：`docs/dm.chm`
  - 解包目录：`docs/dm_chm`
  - 关键接口文档：
    - `docs/dm_chm/后台设置/BindWindow.htm`
    - `docs/dm_chm/后台设置/BindWindowEx.htm`
    - `docs/dm_chm/图色/FindPic.htm`
    - `docs/dm_chm/图色/FindPicEx.htm`
    - `docs/dm_chm/图色/EnableFindPicMultithread.htm`
    - `docs/dm_chm/键鼠/MoveTo.htm`
    - `docs/dm_chm/键鼠/LeftClick.htm`
    - `docs/dm_chm/基本设置/Reg.htm`

## 3. 测试与验证状态

最近验证命令：

```powershell
py -3.14-32 -m unittest discover -s tests
py -3.14-32 -m compileall h5bot main.py tests
py -3.14-32 -c "import PyQt5, cv2, numpy, win32gui, win32com.client; print('ok')"
py -3.14-32 -c "import win32com.client; dm=win32com.client.Dispatch('dm.dmsoft'); print(dm.Ver())"
```

最近结果（2026-05-07）：

- 单元测试通过：`Ran 70 tests`，`OK (skipped=6)`。
  - 6 个 skipped 是 test_ui_helpers.py 因无 PyQt5 跳过（仅 Windows GUI 环境可用），属正常。
- 编译检查通过（compileall 退出码 0）。
- PyQt5 主窗口可创建。
- 大漠 COM 可直连，版本返回：`7.2607`。
- `DmSoftClicker().available()` 返回 `True`。
- 最近一次打包通过，最终 EXE：
  `D:\Ai\codex\H5\dist\全自动辅助助手\全自动辅助助手.exe`

### 2026-05-07 本轮修复（Git + 测试 + UI 重构）

#### Git 工作区修复

- README.md 冲突已手动解决（保留 HEAD 版本内容，删除冲突标记）。
- docs/dm_chm/ 已通过 git worktree 恢复为 origin/main 版本，工作区文件与源一致。
- 残留问题：`.git/index.lock` 被沙箱锁定，无法写入 index，因此 git add/commit 不可用，docs/dm_chm 在 git status 中仍显示为 modified。

#### 测试修复

- `h5bot/dm_clicker.py`：`find_templates()` 中路径分隔符归一化（`str(parent).replace("/", "\\")`），修复 Linux 沙箱下路径断言失败。
- `tests/test_ui_helpers.py`：PyQt5 不存在时跳过测试（`@unittest.skipIf` + 模块级 try/except ImportError），避免 unittest 发现时崩溃。
- 完整测试结果：70 个测试全部通过，6 个 skipped（Windows-only PyQt5），属正常。
- compileall 全部通过。

#### UI 重构

- 删除中心面板中隐藏的"方案"管理控件（plan_combo/task_combo 不再加入布局）。
- 中心面板标题改为"任务模板库 + 当前窗口任务队列"。
- 添加 QTabWidget，普通流程配置和自动抢拍配置分两个 Tab。
- 自动抢拍 Tab 只显示抢拍配置，不显示流程路径和步骤表。
- 任务模板列表显示格式改为"任务名（任务类型）"。

### 2026-05-06 目录整理与模板检查记录

本次只做目录整理、模板同步检查和配置引用检查，没有新增功能，没有改动业务逻辑、识图逻辑或点击逻辑。遵守用户指令：没有删除任何文件，没有批量删除文件，模板图片和 `dm_license.json` 均未删除。

模板同步检查：

- 源码模板目录：`D:\Ai\codex\H5\assets\templates`
- 打包模板目录：`D:\Ai\codex\H5\dist\全自动辅助助手\assets\templates`
- 两边检查时各有 2 个模板。
- `dist` 中没有发现源码目录缺失的模板。
- 没有发生同名文件大小或修改时间冲突。
- 从 `dist` 补回源码目录的模板数量：`0`。

`config/app_config.json` 模板引用检查：

- 扫描 `template` / `templates` 字段共发现模板引用：`36` 个。
- 唯一模板引用数量：`32` 个。
- 已存在模板：`神界大陆.bmp`。
- 未被配置引用但存在于 `assets/templates`：`111.png`。
- 当前默认任务模板不完整，不能认为默认任务已经可完整运行。
- 缺失模板需要后续通过截图裁剪模板或导入旧模板补齐。
- 不要删除缺失引用，不要删除 `111.png`，不要自动改 `app_config.json` 删除这些模板引用。

缺失模板清单（31 个）：

- `01_入口图标.png` ~ `07_确定.png`、`2.bmp` ~ `4.bmp`、`按钮2.bmp`、`单倍按钮1.bmp`、`单倍选择1.bmp`、`加入战场按钮1.bmp`、`奖励界面按钮1.bmp` ~ `奖励界面按钮2.bmp`、`全部挑战按钮1.bmp` ~ `全部挑战按钮2.bmp`、`是否中枢界面1.bmp`、`双倍按钮1.bmp`、`提示按钮1.bmp` ~ `提示按钮2.bmp`、`无boss按钮1.bmp`、`误碰城池1.bmp`、`一键挑战按钮1.bmp` ~ `一键挑战按钮2.bmp`、`一键选择按钮1.bmp` ~ `一键选择按钮2.bmp`、`中枢按钮1.bmp` ~ `中枢按钮2.bmp`、`Boss按钮1.bmp`

目录整理移动记录：

- 原始 C 类可再生成内容已移动到：`D:\Ai\codex\H5\_cleanup_backup`
- 验证过程重新生成的内容已移动到：`D:\Ai\codex\H5\_cleanup_backup\post_validation_generated`
- `dm_help` 为空目录，已标记为可清理，但未移动、未删除。
- 打包验证重新生成的 `dist` 已保留，因为里面包含最终 EXE。

## 4. 重要文件修改记录

### `main.py`

- 应用入口。
- 保留管理员权限自提权。
- 延迟导入 UI，避免依赖缺失时直接崩溃。
- 当前应由 32 位 Python 启动。

### `requirements.txt`

- 已从 `PySide6` 改为 `PyQt5`。
- 当前依赖适配 32 位 Python：
  - `PyQt5>=5.15`
  - `opencv-python>=4.9`
  - `numpy>=1.26`
  - `pywin32>=306`

### `h5bot/ui.py`

- 主界面，已迁移到 `PyQt5`。
- 使用 `pyqtSignal`。
- Qt 枚举已改成 PyQt5 兼容写法。
- `QMenu.exec_()`、`QDialog.exec_()`、`QApplication.exec_()` 已适配 Qt5。
- 增加 `_event_pos()` / `_event_global_pos()`，修复准星绑定和裁剪窗口的鼠标事件兼容问题。
- 样式表已调整为更清晰的工具控制台风格。
- 已移除界面上的手动添加窗口按钮和旧全局单双倍模板输入区。
- 新增 `StepTemplateDialog`，用于维护步骤模板组，支持添加图片、截图添加和移除模板。
- 流程表模板组列改为摘要展示，完整模板列表保存在单元格数据中。
- 截图裁剪保存顺序改为先截图/裁剪，确认后再输入模板文件名。
- 方案/plan 管理控件已从布局中移除（plan_combo/task_combo 不再加入布局）。
- 中心面板标题改为"任务模板库 + 当前窗口任务队列"。
- 添加 QTabWidget 分离"普通流程配置"和"自动抢拍配置"。
- 任务模板列表显示格式改为"任务名（任务类型）"。

### `h5bot/dm_clicker.py`

- 当前大漠核心模块。
- 已删除旧的 `cscript.exe` / VBS / helper 进程逻辑。
- 使用 `win32com.client.Dispatch("dm.dmsoft")` 进程内直连。
- `DmSoftClicker` 管理 hwnd 到 `DmWindowSession` 的会话缓存。
- `DmWindowSession` 负责：
  - COM 初始化。
  - 注册码调用。
  - `BindWindow`。
  - `FindPic`。
  - `MoveTo + LeftClick`。
  - `UnBindWindow`。
- 提供 `_normalize_roi()` 和 `_unpack_find_pic_result()` 辅助函数。
- `find_templates()` 支持多模板名一次大漠识别，并复用当前 `SetPath`。
- 路径分隔符归一化修复：`str(parent).replace("/", "\\")`。

### `h5bot/automation.py`

- Windows 自动化后端。
- 创建 `DmSoftClicker`。
- `find_template_in_window()` 优先调用大漠识图。
- `find_any_template_in_window()` 支持模板组批量识别，优先把同目录模板合并给大漠一次 `FindPic`。
- 大漠识图成功后按模板尺寸转换为中心点。
- 大漠不可用或识图异常时回退 OpenCV 后台截图识别。
- `background_click()` 优先调用大漠点击，失败时回退 Win32 后台消息。
- `shutdown()` 会释放大漠绑定会话。

### `h5bot/flow.py`

- 任务流程执行层。
- 优先使用后端的 `find_any_template_in_window()` 批量识别模板组；没有批量接口时再使用 `find_template_in_window()`。
- 不支持直接窗口识图的后端会回退 `capture_window()` + `find_template()`。
- 负责步骤动作、跳转、暂停、停止、失败返回。
- 流程结束后直接返回完成，不再追加执行旧全局单双倍状态判断。

### `h5bot/config.py`

- 配置数据结构层。
- 核心类型：
  - `FlowStep`
  - `TaskBranch`
  - `TaskPlan`
  - `AppConfig`
- 保存/读取 `config/app_config.json`。
- 默认任务仍是 `方案1 / 神界中枢刷怪`。
- 已移除旧全局单双倍模板配置字段，新配置只保留任务流程需要的数据。

### `h5bot/importer.py`

- 熊猫精灵脚本导入器。
- 只导入/导出模板图，不自动生成完整可运行任务流程。

### `h5bot/template_probe.py`

- 单步骤识别测试逻辑。
- 用于 UI 的"测试当前步骤识别"。

### `README.md`

- 已更新为 32 位 Python 启动和安装说明。
- 已说明大漠 COM 直连和 OpenCV 回退机制。
- Git 冲突已解决（保留 HEAD 版本）。

### `PROJECT_HANDOFF.md`

- 本文件。
- 下次新会话建议第一时间加载。

### `CURRENT_WORK_SUMMARY.md`

- 新增文件，用于跨工具/跨会话跟踪当前工作进度。
- 包含当前修复内容、已完成/未完成事项、Git 状态、测试状态、UI 状态、下一步建议。

### `tests/`

- `test_core.py`：配置、流程、任务方案、跳转逻辑。
- `test_automation.py`：窗口选择、后台点击、模板缓存、大漠坐标转换。
- `test_dm_clicker.py`：大漠辅助函数和会话复用。
- `test_ui_helpers.py`：模板文件名规范化、鼠标事件兼容（无 PyQt5 时跳过）。
- `test_importer.py`：熊猫脚本解析和模板导出。
- `test_template_probe.py`：单步骤模板探测。
- `test_entrypoint.py`：入口模块导入安全。

## 5. 整体架构思路

项目分为六层：

### 入口层

`main.py`

职责：

- 管理管理员权限启动。
- 延迟导入 UI。
- 捕获依赖错误。

### UI 层

`h5bot/ui.py`

职责：

- 展示桌面控制台。
- 读取和写入配置。
- 管理窗口列表。
- 管理任务方案和流程表。
- 发起后台执行线程。
- 接收运行日志并刷新界面。

### 配置层

`h5bot/config.py`

职责：

- 定义任务、步骤、方案数据结构。
- 提供默认任务。
- 序列化到 JSON。

数据流：

```text
config/app_config.json
  -> AppConfig
  -> UI 编辑
  -> save_config()
  -> config/app_config.json
```

### 执行层

`h5bot/flow.py`

职责：

- 根据当前任务拿到步骤列表。
- 对每一步执行识图、点击、跳转或停止。
- 处理暂停/停止。
- 防止跳转死循环。

流程模型：

```text
FlowStep
  -> template_group()
  -> backend.find_any_template_in_window(hwnd, template_paths, threshold, roi)
  -> backend.background_click(hwnd, x, y)
  -> next / jump / skip / stop / fail
```

### 自动化后端层

`h5bot/automation.py`

职责：

- 窗口枚举。
- hwnd 点选。
- 后台截图。
- 前台截图裁剪。
- 模板缓存。
- 大漠优先识图和点击。
- OpenCV/Win32 回退。

### 大漠接口层

`h5bot/dm_clicker.py`

职责：

- 进程内创建 `dm.dmsoft` COM 对象。
- 注册大漠。
- 绑定窗口。
- 调用 `FindPic`。
- 调用 `MoveTo + LeftClick`。
- 解绑窗口。

### 导入层

`h5bot/importer.py`

职责：

- 解析熊猫精灵导出脚本。
- 提取模板资源。

## 6. 待办事项

### 高优先级

- 解决 Git index.lock 问题，完成 git add/commit（当前沙箱权限限制）。
- 实测 32 位 Python + 大漠直连后的多窗口运行速度和稳定性。
- 实测大漠 `BindWindow` 的最佳参数组合，必要时参考 `BindWindowEx.htm`。
- 实测多窗口并发时是否需要限制同时启动数量，避免瞬时卡顿。
- 实测准星绑定、截图裁剪、模板组弹窗、测试识别、开始全部完整链路。
- 确认桌面快捷方式双击后确实使用 32 位 `pythonw.exe`。

### 中优先级

- 给运行日志增加节流或分级，避免多窗口高频日志拖慢 UI。
- 增加模板预览。
- 增加导入熊猫脚本后自动生成任务流程配置。
- 梳理默认任务里的模板文件名，处理 `按钮2.bmp`、`2.bmp` 这类语义不清的同名模板。
- 补齐缺失模板（等待用户手动补充或截图裁剪）。

### 低优先级

- 支持多配置档：
  - `4K 100%`
  - `2K 100%`
  - `1080P 100%`
  - `小窗口`
- 支持模板缩放匹配。
- 支持导入/导出完整项目配置包。
- 支持自定义应用图标。
- 支持托盘图标和最小化到托盘。
- 支持更细粒度的并发控制和运行统计。

## 7. 已知风险与注意事项

- 当前依赖 32 位 Python 和 32 位大漠插件；不要再用 64 位 Python 直接启动主程序。
- `PySide6` 已不再是运行依赖；不要重新安装或回退到 PySide6。
- 大漠后台绑定是否稳定取决于目标游戏窗口实现和绑定参数。
- 多个游戏窗口标题完全相同时，按标题保存任务绑定可能无法区分不同窗口。
- ROI 坐标来自旧脚本和用户手动配置，不同分辨率/缩放下可能需要重调。
- 窗口最小化时，后台截图或大漠后台图色可能失败。
- 右键移除窗口只从软件列表移除，不关闭真实游戏窗口。
- 不要批量删除项目文件或缓存，遵守用户指令"禁止批量删除文件"。
- `.git/index.lock` 被沙箱锁定，无法删除，当前 Git 所有写操作不可用。

## 8. 跨工具交接规则

后续可能在 Codex 和其他开发工具之间切换继续开发。每个阶段完成后必须同步项目文档，不要只在聊天里说明。

每次阶段完成后必须更新：

- `PROJECT_HANDOFF.md`
- `TODO_NEXT.md`

如果本轮修改了代码，必须记录：

- 修改了哪些文件。
- 新增了哪些文件。
- 删除或移动了哪些文件。
- 本轮完成了什么。
- 本轮没完成什么。
- 下一步应该做什么。

每次阶段完成后必须写清楚当前状态：

- 测试是否通过。
- 编译检查是否通过。
- 打包是否通过。
- 最终 EXE 路径。
- 是否存在阻塞问题。

可选但建议维护：

- `CHANGELOG_CURRENT.md`：记录当前未发布阶段变更。
- `KNOWN_ISSUES.md`：记录当前已知问题和禁止误处理事项。
- `CURRENT_WORK_SUMMARY.md`：记录跨会话的当前工作进度。

长期约束：

- 不要做无关重构。
- 不要批量删除文件。
- 不要改回 PySide6。
- 不要使用 64 位 Python。
- 不要破坏现有普通流程任务。
- 不要因为模板缺失删除配置引用。

## 9. 最近阶段状态（2026-05-07 本轮修复）

最近完成阶段：Git 工作区修复、测试修复、UI 重构、文档更新。

### 本轮修改文件

- `README.md` — 解决 Git 冲突（保留 HEAD 版本内容）。
- `h5bot/dm_clicker.py` — 路径分隔符归一化修复。
- `tests/test_ui_helpers.py` — PyQt5 不存在时跳过测试。
- `h5bot/ui.py` — 移除方案控件、QTabWidget 拆分、标题和标签格式调整。

### 本轮新增文件

- `CURRENT_WORK_SUMMARY.md` — 跨会话工作进度跟踪。
- `H5_current_check.zip` — 当前项目检查包（31 个文件，257.5 KB）。
- `git_status_current.txt` — Git 状态快照。
- `git_diff_stat_current.txt` — Git 差异统计。
- `git_diff_name_status_current.txt` — Git 差异名称状态。
- `test_result_current.txt` — 测试结果（70 测试通过，6 skipped）。
- `compile_result_current.txt` — 编译结果（全部通过）。
- `ui_normal_flow_current.png` — 普通流程 UI 截图。
- `ui_auction_current.png` — 自动抢拍 UI 截图。

### 本轮删除或移动文件

- 无。

### 本轮完成

- README.md 冲突已解决（保留 HEAD 版本内容）。
- docs/dm_chm/ 已恢复为 origin/main 版本。
- dm_clicker.py 路径分隔符归一化，7 个测试全部通过。
- test_ui_helpers.py 跳过 PyQt5 依赖测试（无 PyQt5 时跳过）。
- 70 个测试全部通过，6 个 skipped 属正常。
- compileall 全部通过。
- 方案/plan 管理控件已从中心面板布局中移除。
- 中心面板标题改为"任务模板库 + 当前窗口任务队列"。
- 新增 QTabWidget 分离"普通流程配置"和"自动抢拍配置"。
- 自动抢拍 Tab 只显示抢拍配置，不显示流程路径和步骤表。
- 任务模板列表显示格式改为"任务名（任务类型）"。
- CURRENT_WORK_SUMMARY.md 已创建。
- H5_current_check.zip 已创建（31 个文件）。
- 4 份正式文档已更新（本文件、TODO_NEXT.md、CHANGELOG_CURRENT.md、KNOWN_ISSUES.md）。

### 本轮没完成

- `.git/index.lock` 无法删除（沙箱权限限制），git add/commit 不可用。
- docs/dm_chm/ 在 git status 中仍显示为 modified（index 未更新）。
- GitHub 未上传。
- EXE 打包未重新执行。
- UI 截图已生成（旧 UI 截图），新的 QTabWidget UI 尚未在 Windows 上实际验证。
- 默认任务模板仍缺失，不能认为默认任务已经可完整运行。

### 最近验证状态

- 单元测试：`py -3.14-32 -m unittest discover -s tests`，`Ran 70 tests`，`OK (skipped=6)`。
- 编译检查：`py -3.14-32 -m compileall h5bot main.py tests`，退出码 `0`。
- 打包：`D:\Ai\codex\H5\build_exe.bat`，退出码 `0`（最近一次通过，本轮未重新打包）。
- 最终 EXE：`D:\Ai\codex\H5\dist\全自动辅助助手\全自动辅助助手.exe`。

### 当前阻塞

- Git index.lock 阻塞：沙箱权限限制，无法删除 `.git/index.lock`，无法 git add/commit/push。
- GitHub 上传阻塞：定时器未设置或沙箱网络限制。
- 默认任务模板不完整（32 个引用模板中只有 2 个存在）。
- UI 重构效果未在 Windows 上实际验证（运行在 Linux 沙箱，无法运行 Windows GUI）。

## 10. 下次新会话建议加载顺序

建议先读取：

1. `CURRENT_WORK_SUMMARY.md`
2. `PROJECT_HANDOFF.md`
3. `TODO_NEXT.md`
4. `README.md`
5. `config/app_config.json`
6. `KNOWN_ISSUES.md`
7. `CHANGELOG_CURRENT.md`
8. `h5bot/ui.py`
9. `h5bot/recognition.py`
10. `h5bot/preflight.py`
11. `h5bot/flow.py`
12. `h5bot/automation.py`
13. `h5bot/dm_clicker.py`
14. `h5bot/config.py`
15. `tests/test_recognition.py`
16. `tests/test_preflight.py`

建议先运行：

```powershell
py -3.14-32 -m unittest discover -s tests
py -3.14-32 -m compileall h5bot main.py tests
```

依赖检查：

```powershell
py -3.14-32 -c "import PyQt5, cv2, numpy, win32gui, win32com.client; print('ok')"
py -3.14-32 -c "import win32com.client; dm=win32com.client.Dispatch('dm.dmsoft'); print(dm.Ver())"
```

启动：

```powershell
py -3.14-32 D:\Ai\codex\H5\main.py
```

或双击：

```text
C:\Users\Administrator\Desktop\全自动辅助助手.lnk
```
