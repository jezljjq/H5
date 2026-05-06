# 全自动辅助助手

这是一个 Python 桌面工具骨架，用于官方允许范围内的界面级图像识别和后台点击辅助。它不读取或修改游戏内存，不拦截网络，不修改客户端文件。

## 安装

```powershell
py -3.14-32 -m pip install -r D:\Ai\codex\H5\requirements.txt
```

## 启动

```powershell
py -3.14-32 D:\Ai\codex\H5\main.py
```

本项目现在统一使用 32 位 Python 运行，方便直接调用 32 位大漠插件。推荐依赖安装命令：

```powershell
py -3.14-32 -m pip install -r D:\Ai\codex\H5\requirements.txt
```

## 打包 Windows exe

打包必须使用项目指定的 32 位 Python：

```powershell
C:\Users\Administrator\AppData\Local\Programs\Python\Python314-32\python.exe
```

推荐直接运行一键脚本：

```powershell
D:\Ai\codex\H5\build_exe.bat
```

脚本会依次执行：

```powershell
py -3.14-32 -m unittest discover -s tests
py -3.14-32 -m compileall h5bot main.py tests
py -3.14-32 -m pip install pyinstaller
```

然后使用 PyInstaller onedir 模式打包。实际打包命令等价于：

```powershell
py -3.14-32 -m PyInstaller `
  --noconfirm `
  --windowed `
  --name "全自动辅助助手" `
  --distpath "D:\Ai\codex\H5\dist" `
  --workpath "D:\Ai\codex\H5\build\pyinstaller" `
  --specpath "D:\Ai\codex\H5\build" `
  --hidden-import win32timezone `
  --add-data "D:\Ai\codex\H5\assets;assets" `
  --add-data "D:\Ai\codex\H5\config;config" `
  --add-data "D:\Ai\codex\H5\docs;docs" `
  main.py
```

为避免 Windows `cmd` 对中文程序名的编码问题，`build_exe.bat` 会调用同目录下的 `build_exe.py` 来传递 PyInstaller 参数。

打包产物位置：

```text
D:\Ai\codex\H5\dist\全自动辅助助手\全自动辅助助手.exe
```

`dist\全自动辅助助手\config`、`dist\全自动辅助助手\assets`、`dist\全自动辅助助手\docs` 会保留为 exe 同级目录，方便打包后继续修改配置、模板和文档资源。当前先使用 onedir，不建议直接改成 onefile。

## 第一版任务分支

当前默认内置一个任务分支，后续可以在界面里自己新增、重命名、删除方案和任务：

`方案1 / 神界中枢刷怪`

执行路线已按旧熊猫精灵脚本优化：

`误碰城池处理` -> `奖励界面检测` -> `是否中枢界面` -> `神界大陆` -> `神界中枢` -> `加入战场` -> `Boss按钮` -> `无Boss检测` -> `一键挑战` -> `一键选择` -> `全部挑战` -> `挑战提示确认` -> `等待奖励界面` -> `单双倍选择` -> `单倍/双倍按钮`

界面已经按任务控制台重新整理：左侧扫描多开窗口、准星绑定窗口、移除窗口、为窗口分配任务；中间选择方案和任务，支持新增/删除/上移/下移步骤，并通过“编辑模板组”弹窗维护步骤模板、截图添加模板、配置 ROI 和分支动作；右侧查看运行状态和日志。
运行日志支持双击清空。

## 已支持的脚本能力

- 一个步骤可配置多张模板图，流程表显示模板摘要，双击模板组或点击“编辑模板组”可在弹窗里添加图片、截图添加或移除模板。
- 每个步骤可配置 ROI 查找区域，格式是 `x1,y1,x2,y2`。
- 支持找到/找不到后的跳转动作。
- 支持 `无Boss检测` 找到后停止任务。
- 模板图片默认放在项目目录下的 `assets/templates/`，支持 `.bmp`、`.png`、`.jpg` 等 OpenCV 可读取的格式；也可以通过“截图裁剪模板”从选中窗口裁剪保存。截图流程是先截图和框选区域，确认裁剪后再输入文件名保存。
- 自动运行时每个窗口会缓存已读取的模板图片，避免多次循环反复从磁盘读取同一张图；如果本机大漠插件可用，流程识图会优先走 32 位 Python 直连大漠 `FindPic` 的后台窗口识别。同一步骤的多张模板会合并为 `a.bmp|b.bmp` 一次识别，并按模板中心点点击。

## 使用流程

1. 打开多个《斗罗大陆H5》微端/客户端窗口。
2. 在软件里确认窗口标题关键词，默认是 `斗罗大陆H5`。
3. 软件启动后不会自动添加窗口；需要时点击“扫描窗口”，或按住准星按钮拖到游戏窗口上松开绑定。
4. 如果扫描不到某个窗口，优先使用准星按钮直接绑定该窗口。
5. 如果不想运行某些窗口，可以多选后点击“移除选中窗口”。
6. 如果不同窗口要跑不同任务，先在中间选择任务，再多选窗口点击“批量分配当前任务”。
7. 选择一个窗口，点击“截图裁剪模板”，先截图框选区域，确认后输入文件名保存；也可以在某一步的“编辑模板组”弹窗里用“截图添加”直接保存并加入该步骤。
8. 在流程表格中选中某一步，点击“测试当前步骤识别”可只测试模板命中，不执行点击。
9. 在 `方案1 / 神界中枢刷怪` 或自定义任务的流程表格里确认模板组、ROI 和分支动作；单双倍逻辑统一放在步骤表中的 `单双倍选择`、`单倍按钮`、`双倍按钮` 等步骤里配置。
10. 点击“测试选中”验证单个窗口，再点击“开始全部”并发运行多开流程；日志会显示“并发启动 N 个窗口”。

## 兼容性说明

自动运行时会使用后台截图或大漠后台识图，窗口不会主动置前。每个窗口会优先在当前 32 位 Python 进程内创建大漠 COM 会话，完成 `BindWindow` 后复用它执行 `FindPic + MoveTo + LeftClick`；大漠不可用时，再回退到 OpenCV 后台截图识别和 Win32 后台消息。只有点击“截图裁剪模板”时会临时前台截图，方便人工裁剪模板。如果窗口最小化、后台截图不可用、或不响应后台鼠标消息，软件会在日志里提示失败原因。
