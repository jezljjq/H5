from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from h5bot.config import AppConfig, FlowStep
from h5bot.recognition import recognize_step, resolve_step_runtime_params


class AutomationBackend(Protocol):
    def capture_window(self, hwnd: int):
        ...

    def find_template(self, image, template_path: Path | str, threshold: float, roi: list[int] | None = None):
        ...

    def find_template_in_window(self, hwnd: int, template_path: Path | str, threshold: float, roi: list[int] | None = None):
        ...

    def find_any_template_in_window(self, hwnd: int, template_paths: list[Path | str], threshold: float, roi: list[int] | None = None):
        ...

    def background_click(self, hwnd: int, x: int, y: int) -> bool:
        ...


@dataclass(slots=True)
class RunResult:
    ok: bool
    message: str


class FlowRunner:
    def __init__(
        self,
        backend: AutomationBackend,
        config: AppConfig,
        log: Callable[[str], None],
        should_stop: Callable[[], bool] | None = None,
        should_pause: Callable[[], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.backend = backend
        self.config = config
        self.log = log
        self.should_stop = should_stop or (lambda: False)
        self.should_pause = should_pause or (lambda: False)
        self.sleep = sleep

    def _prefix(self, hwnd: int, window_title: str = "") -> str:
        return f"[{window_title or hwnd}][普通流程任务]"

    def run_window(self, hwnd: int, window_title: str = "") -> RunResult:
        try:
            flow = [step for step in self.config.normalized_flow() if step.enabled]
            index_by_name = {step.name: index for index, step in enumerate(flow)}
            index = 0
            guard = 0
            max_steps = max(len(flow) * 50, 50)
            while index < len(flow):
                guard += 1
                if guard > max_steps:
                    return RunResult(False, "流程跳转次数过多，已停止以避免死循环")
                step = flow[index]
                if not step.enabled:
                    index += 1
                    continue
                if self.should_stop():
                    return RunResult(False, "已停止")
                result = self._run_click_step(hwnd, step, window_title)
                if not result.ok:
                    return result
                next_step = self._next_step_name(result.message)
                if next_step:
                    if next_step not in index_by_name:
                        return RunResult(False, f"{step.name} 跳转目标不存在: {next_step}")
                    index = index_by_name[next_step]
                else:
                    index += 1
            return RunResult(True, "流程完成")
        except Exception as exc:
            message = f"{self._prefix(hwnd, window_title)} 执行异常: {exc}"
            self.log(message)
            return RunResult(False, message)

    def _run_click_step(self, hwnd: int, step: FlowStep, window_title: str = "") -> RunResult:
        params = resolve_step_runtime_params(self.config, step)
        if not params.templates:
            message = f"{step.name} 未配置模板，已跳过点击"
            self.log(f"{self._prefix(hwnd, window_title)} {message}")
            return RunResult(True, message)

        prefix = self._prefix(hwnd, window_title)
        self.log(f"{prefix} 开始识别 {step.name}")

        for attempt in range(1, params.retries + 1):
            self._wait_if_paused()
            if self.should_stop():
                return RunResult(False, "已停止")
            recognition = recognize_step(self.backend, hwnd, self.config, step, mode="run", params=params)
            self.log(recognition.log_message("正式运行", hwnd, window_title, step.name, params.templates))
            if recognition.success:
                if params.found_action == "stop":
                    message = f"{step.name} 已识别，触发停止"
                    self.log(f"{prefix} {message}")
                    return RunResult(False, message)
                if params.found_action in {"click", "click_jump", ""}:
                    clicked = self.backend.background_click(hwnd, recognition.x, recognition.y)
                    if not clicked:
                        detail = getattr(self.backend, "last_click_error", "")
                        suffix = f": {detail}" if detail else ""
                        return RunResult(False, f"{step.name} 后台点击失败{suffix}")
                    target = getattr(self.backend, "last_click_target", 0)
                    method = getattr(self.backend, "last_click_method", "")
                    target_text = f"，目标 {target}" if target and target != hwnd else ""
                    method_text = f"，方式 {method}" if method else ""
                    self.log(f"{prefix} {step.name} 命中 {recognition.template_name} {recognition.score:.3f}，点击 ({recognition.x}, {recognition.y}){target_text}{method_text}，后端 {recognition.backend}")
                    self.sleep(params.click_wait)
                elif params.found_action == "jump":
                    self.log(f"{prefix} {step.name} 命中 {recognition.template_name} {recognition.score:.3f}，跳转，后端 {recognition.backend}")
                else:
                    return RunResult(False, f"{step.name} 不支持的找到后动作: {params.found_action}")
                next_marker = f" NEXT={params.found_jump}" if params.found_action in {"jump", "click_jump"} and params.found_jump else ""
                return RunResult(True, f"{step.name} 完成{next_marker}")
            self.log(f"{prefix} {step.name} 第 {attempt}/{params.retries} 次未命中，后端 {recognition.backend}，原因 {recognition.error}")
            self.sleep(max(step.timeout_seconds / max(params.retries, 1), 0.1))

        if params.not_found_action == "skip":
            return RunResult(True, f"{step.name} 未识别，已跳过")
        if params.not_found_action in {"jump", "restart"} and params.not_found_jump:
            return RunResult(True, f"{step.name} 未识别 NEXT={params.not_found_jump}")
        return RunResult(False, f"{step.name} 未识别到模板 {'|'.join(str(path) for path in params.template_paths)}")

    def _next_step_name(self, message: str) -> str:
        marker = " NEXT="
        if marker not in message:
            return ""
        return message.split(marker, 1)[1].strip()

    def _wait_if_paused(self) -> None:
        while self.should_pause() and not self.should_stop():
            self.sleep(0.2)
