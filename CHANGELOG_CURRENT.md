# CHANGELOG_CURRENT

更新时间：2026-05-07

## 当前未发布阶段变更（2026-05-07 UI 修正轮次）

### 左侧准星绑定控件修复

- 从大号文字按钮"绑定目标窗口"恢复为小型准星图标按钮 `◎`。
- `WindowPickerButton` 改为固定尺寸 36×34px，不再设置 `setMinimumWidth(54)`。
- 准星按钮样式从 `font-size: 22px; min-width: 48px` 改为 `font-size: 16px; min-width: 28px; max-width: 36px`。
- Tooltip 改为"拖动准星绑定窗口"。

### 关键 Bug 修复：auction_workspace 初始化顺序

- `_build_ui()` 中 `self.config_tabs.addTab(self.auction_workspace, "自动抢拍配置")`（第 580 行）引用 `self.auction_workspace` 时该属性尚未初始化（实际在 773 行才创建），导致 AttributeError。
- 修复：在 config_tabs 创建前提前初始化 `auction_workspace` 为占位 QScrollArea，后续再 `setWidget(auction_panel)` 填充实际内容。

### 左侧窗口管理区

- 移除顶部工具栏中重复的"窗口操作"分组（扫描窗口和准星按钮只在左侧面板保留，不在工具栏重复出现）。
- 移除窗口列表表头标签 `"窗口标题 | 任务数 | 当前运行任务 | 状态"`。
- 窗口列表项格式从 `"title | n | current | status"` 改为 `"title │ 任务 n │ current │ status"`。

### UI 预览模式

- 新增 `--ui-preview` 启动参数，支持在不初始化大漠、不扫描窗口的情况下预览 UI。
- `main.py`：识别 `--ui-preview` 参数，传递给 `run_app(preview_mode=True)`。
- `MainWindow.__init__`：新增 `preview_mode` 参数，`_init_backend` 在预览模式下降跳过后端初始化，调用 `_load_preview_data()` 加载 3 个模拟窗口和任务队列。
- 模拟数据包括：3 个窗口（斗罗大陆H5-1 ~ H5-3），混合普通流程/自动抢拍任务队列。

### 修改文件

- `h5bot/ui.py` — 准星按钮修复、auction_workspace 初始化顺序修复、左侧面板优化、预览模式
- `main.py` — 新增 `--ui-preview` 参数支持

### 新增文件

- 无。

### 删除或移动文件

- 无。

## 之前阶段（2026-05-07 修复轮次）

### Git 工作区修复

- README.md 冲突已解决（保留 HEAD 版本内容，删除冲突标记）。
- docs/dm_chm/ 已通过 git worktree 恢复为 origin/main 版本。
- 残留问题：`.git/index.lock` 被沙箱锁定，无法 git add/commit，docs/dm_chm 在 git status 中仍显示 modified。

### 测试修复

- `h5bot/dm_clicker.py`：`find_templates()` 中路径分隔符归一化（`str(parent).replace("/", "\\")`），修复 Linux 沙箱下 `test_dm_clicker.py` 路径断言失败（第 58、70 行）。
- `tests/test_ui_helpers.py`：重构为 PyQt5 安全导入模式。
  - 模块级 try/except ImportError 捕获 PyQt5 缺失。
  - 所有 h5bot.ui 导入推迟到测试方法体内。
  - 类级别 `@unittest.skipIf(not _HAS_PYQT5, ...)`。
  - 结果：6 个测试在无 PyQt5 环境优雅跳过，不再崩溃。

### UI 重构（QTabWidget + 方案层级移除）

- 删除中心面板中隐藏的"方案"管理控件（`plan_combo`、`task_combo`、`task_type_combo`、`add_plan_button`、`rename_plan_button`、`delete_plan_button`、`add_task_button`、`copy_task_button`、`delete_task_button` 不再加入布局）。
- 中心面板标题从"任务模板与窗口任务队列"改为"任务模板库 + 当前窗口任务队列"。
- 添加 QTabWidget `config_tabs`，两个 Tab：
  - Tab 0「普通流程配置」：`flow_workspace`（流程路径 + 步骤表 + 步骤按钮 + 当前步骤详情）。
  - Tab 1「自动抢拍配置」：`auction_workspace`（抢拍配置面板，无流程路径和步骤表）。
- `_sync_workspace_to_task_type()` 和 `_refresh_task_type_visibility()` 改为使用 `config_tabs.setCurrentIndex()`。
- 任务模板列表显示格式从 `"[方案名] | [任务名]"` 改为 `"任务名（任务类型）"`。

### 文档更新

- 新增 `CURRENT_WORK_SUMMARY.md`：跨工具/跨会话工作进度跟踪，包含 10 个必填状态区段。
- 新增 `H5_current_check.zip`：当前项目检查包（31 个文件，257.5 KB）。
- 更新 `PROJECT_HANDOFF.md`：新增 2026-05-07 修复轮次记录。
- 更新 `TODO_NEXT.md`：调整待办优先级，添加 Git 阻塞和 UI 验证任务。
- 更新 `CHANGELOG_CURRENT.md`：本文件。
- 更新 `KNOWN_ISSUES.md`：添加 Git index.lock 阻塞和沙箱权限问题。

### 新增文件

- `CURRENT_WORK_SUMMARY.md`
- `H5_current_check.zip`
- `git_status_current.txt`
- `git_diff_stat_current.txt`
- `git_diff_name_status_current.txt`
- `test_result_current.txt`
- `compile_result_current.txt`
- `ui_normal_flow_current.png`
- `ui_auction_current.png`

### 修改文件

- `README.md` — 解决 Git 冲突（保留 HEAD）
- `h5bot/dm_clicker.py` — 路径分隔符归一化
- `tests/test_ui_helpers.py` — PyQt5 跳过测试
- `h5bot/ui.py` — 方案控件移除、QTabWidget 拆分、标题和标签格式调整
- `PROJECT_HANDOFF.md` — 新增修复轮次记录
- `TODO_NEXT.md` — 待办优先级调整
- `KNOWN_ISSUES.md` — 添加 Git 阻塞

### 删除或移动文件

- 无。

### 当前修复完成

- README.md 冲突已解决。
- docs/dm_chm/ 已恢复。
- dm_clicker.py 路径修复，7 个测试通过。
- test_ui_helpers.py 跳过 PyQt5，6 个 skipped 属正常。
- 70 个测试全部通过（6 skipped）。
- 方案控件已从布局移除。
- 标题改为"任务模板库 + 当前窗口任务队列"。
- QTabWidget 分离普通流程 / 自动抢拍配置。
- 任务模板列表格式改为"任务名（任务类型）"。
- 4 份正式交接文档已更新。

### 当前修复未完成

- `.git/index.lock` 无法删除（沙箱权限限制）。
- GitHub 未上传。
- EXE 未重新打包。
- UI 未在 Windows 实际验证。

## 之前阶段（2026-05-06 自动抢拍 UI 工作台 + 窗口任务队列）

### 目录与交接

- 完成项目目录整理，构建产物和缓存已转入 `_cleanup_backup`，后续不再继续清理目录。
- 新增/更新 `.gitignore`，避免上传构建产物、缓存、授权文件和 EXE。
- Git 本地初始化和提交已完成，但 GitHub 上传因本机无法连接 `github.com:443` 暂时跳过。
- 建立跨工具交接规则：每阶段完成后必须更新 `PROJECT_HANDOFF.md` 和 `TODO_NEXT.md`。

### 识别链路一致性

- 测试识别和正式运行统一走 `h5bot.recognition.recognize_step()`。
- 统一使用右侧"全局识别参数"中的默认识别阈值和默认重试次数。
- 保留 `FlowStep.threshold` / `FlowStep.retries` 兼容旧配置，但当前 UI 不显示、不编辑，当前识别不使用它们覆盖全局参数。
- 识别日志统一输出操作来源、hwnd、窗口标题、步骤名称、模板列表、ROI、阈值、后端、命中状态、命中模板、命中坐标和失败原因。

### ROI 可视化

- 右侧当前步骤详情支持选择 ROI、自动生成 ROI、清空 ROI。
- ROI 使用窗口客户区坐标 `x1,y1,x2,y2`。
- 自动生成 ROI 失败时只提示原因，不修改原 ROI。
- ROI 保存后同步流程表、右侧详情、配置对象和 `config/app_config.json`。

### 运行前配置检查

- 新增 `h5bot/preflight.py`。
- 开始运行前检查窗口、任务、启用步骤、ROI、跳转目标、模板文件和大漠可用性。
- 模板缺失只提示，不删除引用，不自动修改配置。

### 自动抢拍任务框架

- 自动抢拍需求已正式下发；本阶段只实现框架，不做多窗口并发、OCR 或真实抢拍压测。
- 新增 `h5bot/auction_config.py`，定义 `AuctionTaskConfig` 和任务类型常量。
- 新增 `h5bot/auction.py`，提供单窗口 `AuctionRunner` 状态机框架和按钮 ROI 计算。
- `TaskBranch` 新增 `task_type` 和 `auction_config`，普通流程任务默认仍为 `flow`。
- 普通流程任务继续由 `FlowRunner` 执行，自动抢拍任务独立使用 `AuctionRunner`。
- UI 增加任务类型入口和自动抢拍配置面板。
- 新增 `tests/test_auction.py`，覆盖自动抢拍配置、序列化、按钮 ROI、状态机关键分支和普通流程兼容。

### 自动抢拍 UI 工作台优化

- 自动抢拍配置新增拍卖入口图标模板组、拍卖界面确认模板组、拍卖入口识别区域、拍卖界面确认区域。
- 自动抢拍状态机调整为 S0-S7，新增 S1"进入拍卖界面"。
- UI 按任务类型拆分工作台。
- 自动抢拍配置从右侧移到中间主工作区。
- 用户可见文案已中文化。

### 窗口任务队列与混合调度

- 新增 `h5bot/window_tasks.py`，统一管理窗口任务队列。
- 新增 `window_task_queues`，运行模型调整为 `窗口 -> 任务队列 -> 队列任务`。
- 旧 `window_task_bindings` 会兼容迁移为该窗口任务队列中的第一个任务。
- 方案不再作为窗口运行时强制层级。
- 中间主区域增加当前窗口任务队列的完整管理。
- 主界面移除方案层级入口。
- 任务模板库可见项只显示任务名和任务类型。
- 开始全部改为遍历窗口自己的启用队列。

## 最近验证（2026-05-07）

- 单元测试：`py -3.14-32 -m unittest discover -s tests`，`Ran 70 tests`，`OK (skipped=6)`。
- 编译检查：`py -3.14-32 -m compileall h5bot main.py tests`，通过。
- 打包：最近一次通过（2026-05-06），本轮未重新打包。
- 最终 EXE：`D:\Ai\codex\H5\dist\全自动辅助助手\全自动辅助助手.exe`。
