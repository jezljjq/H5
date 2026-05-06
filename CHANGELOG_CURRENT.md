# CHANGELOG_CURRENT

更新时间：2026-05-07

## 当前未发布阶段变更（2026-05-07 修复轮次）

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
-