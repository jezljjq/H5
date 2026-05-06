from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


AUCTION_TASK_TYPE = "auction"
FLOW_TASK_TYPE = "flow"


@dataclass(slots=True)
class AuctionTaskConfig:
    task_name: str
    enabled: bool = True
    auction_entry_templates: list[str] = field(default_factory=list)
    auction_page_templates: list[str] = field(default_factory=list)
    target_templates: list[str] = field(default_factory=list)
    buy_button_gray_templates: list[str] = field(default_factory=list)
    buy_button_active_templates: list[str] = field(default_factory=list)
    confirm_templates: list[str] = field(default_factory=list)
    auction_list_roi: list[int] | None = None
    auction_entry_roi: list[int] | None = None
    auction_page_roi: list[int] | None = None
    confirm_roi: list[int] | None = None
    button_roi: list[int] | None = None
    buy_button_offset_x: int = 400
    buy_button_offset_y: int = 0
    buy_button_roi_width: int = 120
    buy_button_roi_height: int = 50
    pre_scan_interval_ms: int = 300
    button_check_interval_ms: int = 50
    confirm_check_interval_ms: int = 50
    scroll_wait_ms: int = 500
    max_scroll_count: int = 10
    scroll_delta: int = -3
    lock_target_before_start: bool = True
    stop_scroll_after_target_found: bool = True
    click_only_when_button_active: bool = True
    success_continue_scan: bool = True
    stop_after_success: bool = False
    no_target_after_full_scan_end: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, task_name: str = "") -> "AuctionTaskConfig":
        data = data or {}
        return cls(
            task_name=str(data.get("task_name") or task_name or "自动抢拍"),
            enabled=bool(data.get("enabled", True)),
            auction_entry_templates=_string_list(data.get("auction_entry_templates")),
            auction_page_templates=_string_list(data.get("auction_page_templates")),
            target_templates=_string_list(data.get("target_templates")),
            buy_button_gray_templates=_string_list(data.get("buy_button_gray_templates")),
            buy_button_active_templates=_string_list(data.get("buy_button_active_templates")),
            confirm_templates=_string_list(data.get("confirm_templates")),
            auction_list_roi=_optional_roi(data.get("auction_list_roi")),
            auction_entry_roi=_optional_roi(data.get("auction_entry_roi")),
            auction_page_roi=_optional_roi(data.get("auction_page_roi")),
            confirm_roi=_optional_roi(data.get("confirm_roi")),
            button_roi=_optional_roi(data.get("button_roi")),
            buy_button_offset_x=int(data.get("buy_button_offset_x", 400)),
            buy_button_offset_y=int(data.get("buy_button_offset_y", 0)),
            buy_button_roi_width=int(data.get("buy_button_roi_width", 120)),
            buy_button_roi_height=int(data.get("buy_button_roi_height", 50)),
            pre_scan_interval_ms=int(data.get("pre_scan_interval_ms", 300)),
            button_check_interval_ms=int(data.get("button_check_interval_ms", 50)),
            confirm_check_interval_ms=int(data.get("confirm_check_interval_ms", 50)),
            scroll_wait_ms=int(data.get("scroll_wait_ms", 500)),
            max_scroll_count=int(data.get("max_scroll_count", 10)),
            scroll_delta=int(data.get("scroll_delta", -3)),
            lock_target_before_start=bool(data.get("lock_target_before_start", True)),
            stop_scroll_after_target_found=bool(data.get("stop_scroll_after_target_found", True)),
            click_only_when_button_active=bool(data.get("click_only_when_button_active", True)),
            success_continue_scan=bool(data.get("success_continue_scan", True)),
            stop_after_success=bool(data.get("stop_after_success", False)),
            no_target_after_full_scan_end=bool(data.get("no_target_after_full_scan_end", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def missing_required_groups(self) -> list[str]:
        missing = []
        if not self.auction_entry_templates:
            missing.append("拍卖入口图标模板组")
        if not self.auction_page_templates:
            missing.append("拍卖界面确认模板组")
        if not self.target_templates:
            missing.append("目标物品模板组")
        if not self.buy_button_active_templates:
            missing.append("可点击一口价按钮模板组")
        if not self.confirm_templates:
            missing.append("确认按钮模板组")
        return missing


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", "|").split("|") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _optional_roi(value: Any) -> list[int] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        return [int(part) for part in parts] if len(parts) == 4 else None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [int(part) for part in value]
    return None
