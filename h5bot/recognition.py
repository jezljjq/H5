from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from h5bot.config import AppConfig, FlowStep, resolve_templates_dir
from h5bot.roi import format_roi, parse_roi


@dataclass(slots=True)
class StepRuntimeParams:
    step_name: str
    templates: list[str]
    template_paths: list[Path]
    roi: list[int] | None
    threshold: float
    retries: int
    click_wait: float
    found_action: str
    found_jump: str
    not_found_action: str
    not_found_jump: str


@dataclass(slots=True)
class RecognitionResult:
    success: bool
    backend: str
    template_path: Path | None
    template_name: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    score: float = 0.0
    roi: list[int] | None = None
    threshold: float = 0.0
    retries: int = 1
    message: str = ""
    error: str = ""
    checked_paths: list[Path] | None = None

    def log_message(self, source: str, hwnd: int, window_title: str, step_name: str, templates: list[str]) -> str:
        status = "命中" if self.success else "未命中"
        roi_text = format_roi(self.roi) or "全窗口"
        checked = " | ".join(str(path) for path in (self.checked_paths or []))
        detail = f"模板 {self.template_name}，坐标 ({self.x}, {self.y})，相似度 {self.score:.3f}" if self.success else (self.error or self.message or "无匹配")
        return (
            f"{source}: hwnd {hwnd}，窗口 {window_title or '-'}，步骤 {step_name}，"
            f"模板组 {' | '.join(templates) or '-'}，ROI {roi_text}，阈值 {self.threshold:.2f}，"
            f"重试 {self.retries}，后端 {self.backend or '-'}，结果 {status}，{detail}"
            + (f"，已检查 {checked}" if checked and not self.success else "")
        )


def resolve_template_path(config: AppConfig, template: str) -> Path:
    path = Path(template)
    if path.is_absolute():
        return path
    return resolve_templates_dir(config) / path


def resolve_step_runtime_params(config: AppConfig, step: FlowStep) -> StepRuntimeParams:
    templates = step.template_group()
    roi = parse_roi(step.roi)
    threshold = step.threshold if step.threshold is not None else config.default_threshold
    retries = step.retries if step.retries is not None else config.default_retries
    return StepRuntimeParams(
        step_name=step.name,
        templates=templates,
        template_paths=[resolve_template_path(config, template) for template in templates],
        roi=roi,
        threshold=float(threshold),
        retries=int(retries),
        click_wait=float(step.delay_after_click if step.delay_after_click is not None else config.default_delay_after_click),
        found_action=step.on_found or "click",
        found_jump=step.found_next,
        not_found_action=step.on_not_found or "fail",
        not_found_jump=step.not_found_next,
    )


def recognize_step(backend, hwnd: int, config: AppConfig, step: FlowStep, mode: str = "test", params: StepRuntimeParams | None = None) -> RecognitionResult:
    params = params or resolve_step_runtime_params(config, step)
    if not params.templates:
        return RecognitionResult(False, "none", None, "", roi=params.roi, threshold=params.threshold, retries=params.retries, error="未配置模板", checked_paths=[])

    group_find = getattr(backend, "find_any_template_in_window", None)
    if group_find:
        grouped_match = group_find(int(hwnd), params.template_paths, params.threshold, params.roi)
        backend_name = _backend_name(backend)
        if grouped_match:
            index, match = grouped_match
            return _success_result(backend, backend_name, params, index, match)
        return RecognitionResult(False, backend_name, None, "", roi=params.roi, threshold=params.threshold, retries=params.retries, error=_failure_reason(params), checked_paths=params.template_paths)

    direct_find = getattr(backend, "find_template_in_window", None)
    image = None
    for index, template_path in enumerate(params.template_paths):
        if direct_find:
            match = direct_find(int(hwnd), template_path, params.threshold, params.roi)
        else:
            if image is None:
                image = backend.capture_window(int(hwnd))
            match = backend.find_template(image, template_path, params.threshold, params.roi)
        if match:
            return _success_result(backend, _backend_name(backend), params, index, match)
    return RecognitionResult(False, _backend_name(backend), None, "", roi=params.roi, threshold=params.threshold, retries=params.retries, error=_failure_reason(params), checked_paths=params.template_paths)


def _success_result(backend, backend_name: str, params: StepRuntimeParams, index: int, match) -> RecognitionResult:
    x, y, score = match
    template_path = params.template_paths[index] if 0 <= index < len(params.template_paths) else None
    template_name = params.templates[index] if 0 <= index < len(params.templates) else ""
    width, height = _template_size(backend, template_path)
    return RecognitionResult(
        True,
        backend_name,
        template_path,
        template_name,
        int(x),
        int(y),
        width,
        height,
        float(score),
        params.roi,
        params.threshold,
        params.retries,
        checked_paths=params.template_paths,
    )


def _template_size(backend, template_path: Path | None) -> tuple[int, int]:
    if not template_path:
        return 0, 0
    read_template = getattr(backend, "_read_template", None)
    image = read_template(template_path) if read_template else None
    if image is None and hasattr(backend, "cv2"):
        image = backend.cv2.imread(str(template_path), backend.cv2.IMREAD_COLOR)
    if image is None or not hasattr(image, "shape"):
        return 0, 0
    return int(image.shape[1]), int(image.shape[0])


def _backend_name(backend) -> str:
    name = getattr(backend, "last_recognition_backend", "")
    if name:
        return name
    dm_clicker = getattr(backend, "dm_clicker", None)
    if dm_clicker and dm_clicker.available():
        return "大漠"
    return "OpenCV"


def _failure_reason(params: StepRuntimeParams) -> str:
    missing = [path for path in params.template_paths if not path.exists()]
    if missing and len(missing) == len(params.template_paths):
        return f"模板文件不存在: {' | '.join(str(path) for path in missing)}"
    return "未识别到匹配模板"
