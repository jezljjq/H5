from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from h5bot.auction_config import AuctionTaskConfig
from h5bot.config import AppConfig, FlowStep
from h5bot.recognition import RecognitionResult, recognize_step
from h5bot.roi import format_roi


@dataclass(slots=True)
class AuctionRunResult:
    ok: bool
    success: bool
    message: str
    state: str


def compute_button_roi(target_x: int, target_y: int, config: AuctionTaskConfig, window_size: tuple[int, int] | None = None) -> list[int]:
    x1 = int(target_x) + int(config.buy_button_offset_x)
    y1 = int(target_y) + int(config.buy_button_offset_y)
    x2 = x1 + max(1, int(config.buy_button_roi_width))
    y2 = y1 + max(1, int(config.buy_button_roi_height))
    return clamp_roi([x1, y1, x2, y2], window_size)


def clamp_roi(roi: list[int], window_size: tuple[int, int] | None = None) -> list[int]:
    if not window_size:
        return [int(part) for part in roi]
    width, height = max(1, int(window_size[0])), max(1, int(window_size[1]))
    x1 = min(max(0, int(roi[0])), width - 1)
    y1 = min(max(0, int(roi[1])), height - 1)
    x2 = min(max(x1 + 1, int(roi[2])), width)
    y2 = min(max(y1 + 1, int(roi[3])), height)
    return [x1, y1, x2, y2]


class AuctionRunner:
    def __init__(
        self,
        backend,
        app_config: AppConfig,
        auction_config: AuctionTaskConfig,
        log: Callable[[str], None],
        should_stop: Callable[[], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        button_wait_attempts: int = 20,
        confirm_wait_attempts: int = 20,
        max_success_cycles: int = 1,
    ) -> None:
        self.backend = backend
        self.app_config = app_config
        self.config = auction_config
        self.log = log
        self.should_stop = should_stop or (lambda: False)
        self.sleep = sleep
        self.button_wait_attempts = max(1, int(button_wait_attempts))
        self.confirm_wait_attempts = max(1, int(confirm_wait_attempts))
        self.max_success_cycles = max(1, int(max_success_cycles))

    def run_window(self, hwnd: int, window_title: str = "") -> AuctionRunResult:
        missing = self.config.missing_required_groups()
        if missing:
            message = f"配置不完整: {', '.join(missing)}"
            self._log_failure("S0", hwnd, window_title, "-", None, message)
            return AuctionRunResult(False, False, message, "S0")

        if not self._bind_window(hwnd):
            message = "绑定窗口失败"
            self._log_failure("S0", hwnd, window_title, "-", None, message)
            return AuctionRunResult(False, False, message, "S0")
        self._log(window_title, "S0", "绑定窗口成功")

        page_ready = self._enter_auction_page(hwnd, window_title)
        if not page_ready.success:
            return AuctionRunResult(False, False, page_ready.error or "拍卖入口未找到，任务结束", "S1")

        cycles = 0
        while cycles < self.max_success_cycles and not self.should_stop():
            target = self._scan_target(hwnd, window_title)
            if not target.success:
                return AuctionRunResult(True, False, target.error or target.message or "完整扫描未找到目标", "S2")

            button_roi = compute_button_roi(target.x, target.y, self.config, self._window_size(hwnd))
            self.config.button_roi = button_roi
            self._log(window_title, "S3", f"已锁定按钮 ROI: {format_roi(button_roi)}")

            button_state = self._wait_button_active(hwnd, window_title, button_roi)
            if not button_state.success:
                return AuctionRunResult(False, False, button_state.error or "按钮未激活", "S4")

            click_x = (button_roi[0] + button_roi[2]) // 2
            click_y = (button_roi[1] + button_roi[3]) // 2
            if not self.backend.background_click(hwnd, click_x, click_y):
                message = "点击一口价失败"
                self._log_failure("S5", hwnd, window_title, "可点击按钮模板组", button_roi, message)
                return AuctionRunResult(False, False, message, "S5")
            self._log(window_title, "S5", f"点击一口价: {click_x},{click_y}")

            confirmed = self._click_confirm(hwnd, window_title)
            if not confirmed.success:
                return AuctionRunResult(False, False, confirmed.error or "确认按钮未命中", "S6")

            cycles += 1
            self._log(window_title, "S7", "本轮抢拍流程完成")
            if self.config.stop_after_success:
                return AuctionRunResult(True, True, "本轮抢拍流程完成，按策略停止", "S7")
            if not self.config.success_continue_scan:
                return AuctionRunResult(True, True, "本轮抢拍流程完成", "S7")
        return AuctionRunResult(True, True, "本轮抢拍流程完成", "S7")

    def _enter_auction_page(self, hwnd: int, window_title: str) -> RecognitionResult:
        self._log(window_title, "S1", "检查是否已在拍卖界面")
        page = self._recognize_group(hwnd, "拍卖界面确认", self.config.auction_page_templates, self.config.auction_page_roi)
        if page.success:
            self._log(window_title, "S1", "已在拍卖界面，跳过入口点击")
            return page

        entry = self._recognize_group(hwnd, "拍卖入口图标", self.config.auction_entry_templates, self.config.auction_entry_roi)
        if not entry.success:
            message = "拍卖入口未找到，任务结束"
            self._log_failure("S1", hwnd, window_title, "拍卖入口图标模板组", self.config.auction_entry_roi, message)
            entry.error = message
            return entry

        if not self.backend.background_click(hwnd, entry.x, entry.y):
            message = "点击拍卖入口失败"
            self._log_failure("S1", hwnd, window_title, "拍卖入口图标模板组", self.config.auction_entry_roi, message)
            entry.error = message
            return entry
        self._log(window_title, "S1", "识别拍卖入口图标成功，点击入口")
        self._log(window_title, "S1", "等待拍卖界面加载")
        self.sleep(max(0, self.config.pre_scan_interval_ms) / 1000)

        for _attempt in range(max(1, int(self.app_config.default_retries))):
            page = self._recognize_group(hwnd, "拍卖界面确认", self.config.auction_page_templates, self.config.auction_page_roi)
            if page.success:
                self._log(window_title, "S1", "拍卖界面确认成功")
                return page
            self.sleep(max(0, self.config.pre_scan_interval_ms) / 1000)
        message = "拍卖界面确认失败"
        self._log_failure("S1", hwnd, window_title, "拍卖界面确认模板组", self.config.auction_page_roi, message)
        page.error = message
        return page

    def _scan_target(self, hwnd: int, window_title: str) -> RecognitionResult:
        self._log(window_title, "S2", "开始预扫描目标物品")
        scroll_count = 0
        while not self.should_stop():
            step = FlowStep("自动抢拍目标物品", templates=self.config.target_templates, roi=self.config.auction_list_roi)
            result = recognize_step(self.backend, hwnd, self.app_config, step, mode="auction")
            if result.success:
                self._log(window_title, "S2", f"目标命中: {result.template_name}, 坐标: {result.x},{result.y}")
                return result
            if scroll_count >= max(0, int(self.config.max_scroll_count)):
                message = "完整扫描未找到目标"
                self._log_failure("S2", hwnd, window_title, "目标物品模板组", self.config.auction_list_roi, message)
                result.error = message
                return result
            self._scroll(hwnd)
            scroll_count += 1
            self.sleep(max(0, self.config.scroll_wait_ms) / 1000)
        return RecognitionResult(False, "none", None, "", roi=self.config.auction_list_roi, threshold=self.app_config.default_threshold, retries=self.app_config.default_retries, error="已停止")

    def _wait_button_active(self, hwnd: int, window_title: str, button_roi: list[int]) -> RecognitionResult:
        for _attempt in range(self.button_wait_attempts):
            if self.should_stop():
                break
            if self.config.buy_button_gray_templates:
                gray = self._recognize_group(hwnd, "一口价灰色按钮", self.config.buy_button_gray_templates, button_roi)
                if gray.success:
                    self._log(window_title, "S4", "按钮状态: 灰色，等待开抢")
                    self.sleep(max(0, self.config.button_check_interval_ms) / 1000)
                    continue
            active = self._recognize_group(hwnd, "一口价可点击按钮", self.config.buy_button_active_templates, button_roi)
            if active.success:
                self._log(window_title, "S4", "按钮状态: 可点击，准备点击")
                return active
            self.sleep(max(0, self.config.button_check_interval_ms) / 1000)
        message = "按钮未激活"
        self._log_failure("S4", hwnd, window_title, "灰色/可点击按钮模板组", button_roi, message)
        return RecognitionResult(False, "none", None, "", roi=button_roi, threshold=self.app_config.default_threshold, retries=self.app_config.default_retries, error=message)

    def _click_confirm(self, hwnd: int, window_title: str) -> RecognitionResult:
        for _attempt in range(self.confirm_wait_attempts):
            if self.should_stop():
                break
            result = self._recognize_group(hwnd, "确认按钮", self.config.confirm_templates, self.config.confirm_roi)
            if result.success:
                if not self.backend.background_click(hwnd, result.x, result.y):
                    result.error = "点击确认失败"
                    self._log_failure("S6", hwnd, window_title, "确认按钮模板组", self.config.confirm_roi, result.error)
                    return result
                self._log(window_title, "S6", "确认按钮命中，点击确认")
                return result
            self.sleep(max(0, self.config.confirm_check_interval_ms) / 1000)
        message = "确认按钮未命中"
        self._log_failure("S6", hwnd, window_title, "确认按钮模板组", self.config.confirm_roi, message)
        return RecognitionResult(False, "none", None, "", roi=self.config.confirm_roi, threshold=self.app_config.default_threshold, retries=self.app_config.default_retries, error=message)

    def _recognize_group(self, hwnd: int, step_name: str, templates: list[str], roi: list[int] | None) -> RecognitionResult:
        step = FlowStep(step_name, templates=templates, roi=roi)
        return recognize_step(self.backend, hwnd, self.app_config, step, mode="auction")

    def _bind_window(self, hwnd: int) -> bool:
        bind = getattr(self.backend, "bind_window", None)
        if bind:
            return bool(bind(hwnd))
        return True

    def _window_size(self, hwnd: int) -> tuple[int, int] | None:
        for name in ("client_size_for_window", "window_client_size", "get_client_size"):
            method = getattr(self.backend, name, None)
            if method:
                size = method(hwnd)
                if size and len(size) == 2:
                    return int(size[0]), int(size[1])
        return None

    def _scroll(self, hwnd: int) -> None:
        for name in ("scroll_window", "scroll_auction_list", "mouse_wheel"):
            method = getattr(self.backend, name, None)
            if method:
                method(hwnd, self.config.scroll_delta)
                return

    def _log(self, window_title: str, state: str, message: str) -> None:
        self.log(f"[{window_title or '-'}][自动抢拍任务][{state}] {message}")

    def _log_failure(self, state: str, hwnd: int, window_title: str, template_group: str, roi: list[int] | None, reason: str) -> None:
        self._log(
            window_title,
            state,
            f"失败: hwnd={hwnd}, 窗口标题={window_title or '-'}, 模板组={template_group}, ROI={format_roi(roi) or '全窗口'}, 阈值={self.app_config.default_threshold:.2f}, 失败原因={reason}",
        )
