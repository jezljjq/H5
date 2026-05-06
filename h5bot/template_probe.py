from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from h5bot.config import AppConfig, FlowStep
from h5bot.recognition import RecognitionResult, recognize_step


@dataclass(slots=True)
class TemplateProbeResult:
    ok: bool
    message: str
    template: str = ""
    template_path: Path | None = None
    match: tuple[int, int, float] | None = None
    recognition: RecognitionResult | None = None


def probe_step_templates(_backend, _image, config: AppConfig, step: FlowStep) -> TemplateProbeResult:
    return TemplateProbeResult(False, f"{step.name} 请使用窗口测试识别入口", recognition=None)


def probe_step_templates_in_window(backend, hwnd: int, config: AppConfig, step: FlowStep) -> TemplateProbeResult:
    recognition = recognize_step(backend, hwnd, config, step, mode="test")
    if recognition.success:
        match = (recognition.x, recognition.y, recognition.score)
        return TemplateProbeResult(
            True,
            f"{step.name} 命中 {recognition.template_name}，坐标 ({recognition.x}, {recognition.y})，相似度 {recognition.score:.3f}，后端 {recognition.backend}",
            template=recognition.template_name,
            template_path=recognition.template_path,
            match=match,
            recognition=recognition,
        )
    return TemplateProbeResult(False, f"{step.name} 未命中，阈值 {recognition.threshold:.2f}，后端 {recognition.backend}，原因: {recognition.error}", recognition=recognition)
