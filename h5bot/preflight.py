from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from h5bot.automation import GameWindow
from h5bot.auction_config import AUCTION_TASK_TYPE, FLOW_TASK_TYPE
from h5bot.config import AppConfig, FlowStep, resolve_templates_dir
from h5bot.roi import parse_roi
from h5bot.window_tasks import WindowQueuedTask, WindowTaskBinding, enabled_queue, find_task_for_binding, task_type_label


@dataclass(slots=True)
class PreflightIssue:
    severity: str
    message: str


@dataclass(slots=True)
class PreflightReport:
    issues: list[PreflightIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[PreflightIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[PreflightIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, message: str) -> None:
        self.issues.append(PreflightIssue("error", message))

    def add_warning(self, message: str) -> None:
        self.issues.append(PreflightIssue("warning", message))

    def summary(self) -> str:
        if not self.issues:
            return "运行前配置检查通过"
        return "\n".join(f"[{issue.severity}] {issue.message}" for issue in self.issues)


def run_preflight_checks(config: AppConfig, hwnds: list[int], windows: list[GameWindow], backend) -> PreflightReport:
    report = PreflightReport()
    _check_windows(report, hwnds, windows, backend)
    task = config.active_task()
    if task is None:
        report.add_error(f"当前任务不存在: {config.selected_plan} / {config.selected_task}")
        _check_dm(report, backend)
        return report
    enabled_steps = [step for step in task.flow if step.enabled]
    if not enabled_steps:
        report.add_error(f"当前任务没有启用步骤: {config.selected_plan} / {config.selected_task}")
    _check_steps(report, config, enabled_steps)
    _check_dm(report, backend)
    return report


def run_window_task_preflight_checks(
    config: AppConfig,
    hwnds: list[int],
    windows: list[GameWindow],
    backend,
    queues: dict[int, list[WindowQueuedTask]] | dict[int, WindowTaskBinding],
) -> PreflightReport:
    report = PreflightReport()
    _check_windows(report, hwnds, windows, backend)
    for hwnd in hwnds:
        raw_queue = queues.get(int(hwnd), [WindowQueuedTask(config.selected_plan, config.selected_task, FLOW_TASK_TYPE)])
        if isinstance(raw_queue, WindowTaskBinding):
            raw_queue = [WindowQueuedTask(raw_queue.plan_name, raw_queue.task_name, raw_queue.task_type)]
        queue = enabled_queue(raw_queue)
        if not queue:
            report.add_error(f"窗口 {hwnd} 没有启用的任务队列")
            continue
        for queue_item in queue:
            binding = queue_item.to_binding()
            task = find_task_for_binding(config, binding)
            if task is None:
                report.add_error(f"窗口 {hwnd} 队列任务不存在: {binding.plan_name} / {binding.task_name} / {task_type_label(binding.task_type)}")
                continue
            if binding.task_type == AUCTION_TASK_TYPE:
                if task.auction_config is None:
                    report.add_error(f"窗口 {hwnd} 自动抢拍配置不存在: {binding.plan_name} / {binding.task_name}")
                continue
            enabled_steps = [step for step in task.flow if step.enabled]
            if not enabled_steps:
                report.add_error(f"窗口 {hwnd} 普通流程任务没有启用步骤: {binding.plan_name} / {binding.task_name}")
                continue
            _check_steps(report, config.for_task(binding.plan_name, binding.task_name), enabled_steps)
    _check_dm(report, backend)
    return report


def _check_windows(report: PreflightReport, hwnds: list[int], windows: list[GameWindow], backend) -> None:
    known = {int(window.hwnd) for window in windows}
    is_window = getattr(getattr(backend, "win32gui", None), "IsWindow", None)
    for hwnd in hwnds:
        valid = int(hwnd) in known
        if valid and is_window:
            try:
                valid = bool(is_window(int(hwnd)))
            except Exception:
                valid = False
        if not valid:
            report.add_error(f"当前窗口无效: hwnd {hwnd}，请重新扫描或使用准星绑定")


def _check_steps(report: PreflightReport, config: AppConfig, steps: list[FlowStep]) -> None:
    names = {step.name for step in steps if step.name}
    templates_dir = resolve_templates_dir(config)
    for step in steps:
        _check_roi(report, step)
        _check_jumps(report, step, names)
        _check_templates(report, step, templates_dir)


def _check_roi(report: PreflightReport, step: FlowStep) -> None:
    try:
        roi = parse_roi(step.roi)
    except Exception:
        report.add_error(f"ROI 非法: 步骤 {step.name}，ROI {step.roi}")
        return
    if roi is None:
        return
    x1, y1, x2, y2 = roi
    if x1 == x2 or y1 == y2:
        report.add_error(f"ROI 非法: 步骤 {step.name}，ROI {step.roi}")


def _check_jumps(report: PreflightReport, step: FlowStep, names: set[str]) -> None:
    if step.on_found in {"jump", "click_jump"} and step.found_next and step.found_next not in names:
        report.add_error(f"跳转目标不存在: 步骤 {step.name}，找到后跳转 {step.found_next}")
    if step.on_not_found in {"jump", "restart"} and step.not_found_next and step.not_found_next not in names:
        report.add_error(f"跳转目标不存在: 步骤 {step.name}，找不到后跳转 {step.not_found_next}")


def _check_templates(report: PreflightReport, step: FlowStep, templates_dir: Path) -> None:
    for template in step.template_group():
        path = Path(template)
        if not path.is_absolute():
            path = templates_dir / path
        if not path.exists():
            report.add_warning(f"模板文件不存在: 步骤 {step.name}，模板 {template}")


def _check_dm(report: PreflightReport, backend) -> None:
    dm_clicker = getattr(backend, "dm_clicker", None)
    available = False
    if dm_clicker:
        try:
            available = bool(dm_clicker.available())
        except Exception:
            available = False
    if not available:
        report.add_warning("大漠不可用: 将按当前逻辑回退 OpenCV；如果后台识别失败，请检查大漠注册和绑定环境")
