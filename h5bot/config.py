from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from copy import deepcopy
from pathlib import Path
from typing import Any

from h5bot.auction_config import AUCTION_TASK_TYPE, FLOW_TASK_TYPE, AuctionTaskConfig
from h5bot.paths import app_root, resource_path


ROOT = app_root()


DEFAULT_FLOW_NAMES = [
    "入口图标",
    "刷怪场景",
    "BOSS图标",
    "一定挑战",
    "全选",
    "挑战",
    "确定",
]

SHENJIE_BRANCH_STEPS = [
    ("神界大陆", "01_神界大陆.png"),
    ("神界中枢", "02_神界中枢.png"),
    ("加入战场", "03_加入战场.png"),
    ("一键挑战图标", "04_一键挑战图标.png"),
    ("一键挑战", "05_一键挑战.png"),
    ("挑战确定", "06_挑战确定.png"),
]

@dataclass(slots=True)
class FlowStep:
    name: str
    template: str = ""
    templates: list[str] = field(default_factory=list)
    roi: list[int] | None = None
    threshold: float | None = None
    retries: int | None = None
    timeout_seconds: float = 8.0
    delay_after_click: float = 0.5
    enabled: bool = True
    on_found: str = "click"
    found_next: str = ""
    on_not_found: str = "fail"
    not_found_next: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowStep":
        return cls(
            name=str(data.get("name", "")),
            template=str(data.get("template", "")),
            templates=[str(item) for item in data.get("templates", [])],
            roi=_optional_roi(data.get("roi")),
            threshold=_optional_float(data.get("threshold")),
            retries=_optional_int(data.get("retries")),
            timeout_seconds=float(data.get("timeout_seconds", 8.0)),
            delay_after_click=float(data.get("delay_after_click", 0.5)),
            enabled=bool(data.get("enabled", True)),
            on_found=str(data.get("on_found", "click")),
            found_next=str(data.get("found_next", "")),
            on_not_found=str(data.get("on_not_found", "fail")),
            not_found_next=str(data.get("not_found_next", "")),
        )

    def template_group(self) -> list[str]:
        if self.templates:
            return [item for item in self.templates if item]
        if "|" in self.template:
            return [item.strip() for item in self.template.split("|") if item.strip()]
        return [self.template] if self.template else []


SHENJIE_BRANCH_FLOW = [
    FlowStep("误碰城池处理", templates=["误碰城池1.bmp", "按钮2.bmp"], roi=[119, 125, 637, 883], on_not_found="skip"),
    FlowStep("奖励界面检测", templates=["奖励界面按钮1.bmp", "奖励界面按钮2.bmp"], roi=[233, 261, 528, 309], on_found="jump", found_next="单双倍选择", on_not_found="skip"),
    FlowStep("是否中枢界面", templates=["是否中枢界面1.bmp"], roi=[624, 132, 751, 196], on_found="jump", found_next="Boss按钮", on_not_found="skip"),
    FlowStep("神界大陆", templates=["神界按钮1.bmp", "神界按钮2.bmp", "神界按钮3.bmp", "神界按钮4.bmp"], roi=[15, 602, 57, 638], on_not_found="skip"),
    FlowStep("神界中枢", templates=["中枢按钮1.bmp", "中枢按钮2.bmp"], on_not_found="jump", not_found_next="神界大陆"),
    FlowStep("加入战场", templates=["加入战场按钮1.bmp"], roi=[379, 783, 603, 859], on_not_found="jump", not_found_next="神界中枢"),
    FlowStep("Boss按钮", templates=["Boss按钮1.bmp", "按钮2.bmp"], roi=[9, 234, 58, 624], on_not_found="skip"),
    FlowStep("无Boss检测", templates=["无boss按钮1.bmp"], on_found="stop", on_not_found="jump", not_found_next="一键挑战"),
    FlowStep("一键挑战", templates=["一键挑战按钮1.bmp", "一键挑战按钮2.bmp"], retries=10, on_not_found="jump", not_found_next="Boss按钮"),
    FlowStep("一键选择", templates=["一键选择按钮1.bmp", "一键选择按钮2.bmp"], on_not_found="skip"),
    FlowStep("全部挑战", templates=["全部挑战按钮1.bmp", "全部挑战按钮2.bmp"], on_not_found="skip"),
    FlowStep("挑战提示确认", templates=["提示按钮1.bmp", "提示按钮2.bmp"], on_not_found="skip"),
    FlowStep("等待奖励界面", templates=["奖励界面按钮1.bmp", "奖励界面按钮2.bmp"], roi=[233, 261, 528, 309], on_found="jump", found_next="单双倍选择", on_not_found="jump", not_found_next="Boss按钮"),
    FlowStep("单双倍选择", templates=["单倍选择1.bmp", "2.bmp", "3.bmp", "4.bmp"], roi=[90, 284, 652, 648], on_found="jump", found_next="单倍按钮", on_not_found="jump", not_found_next="双倍按钮"),
    FlowStep("单倍按钮", templates=["单倍按钮1.bmp", "2.bmp"], roi=[87, 289, 657, 581], on_not_found="skip"),
    FlowStep("双倍按钮", templates=["双倍按钮1.bmp"], roi=[93, 288, 665, 565], on_not_found="skip"),
]


@dataclass(slots=True)
class TaskBranch:
    name: str
    description: str = ""
    flow: list[FlowStep] = field(default_factory=list)
    enabled: bool = True
    task_type: str = FLOW_TASK_TYPE
    auction_config: AuctionTaskConfig | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskBranch":
        task_type = str(data.get("task_type", FLOW_TASK_TYPE)) or FLOW_TASK_TYPE
        auction_config = None
        if task_type == AUCTION_TASK_TYPE or data.get("auction_config"):
            auction_config = AuctionTaskConfig.from_dict(data.get("auction_config"), str(data.get("name", "")))
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            flow=[FlowStep.from_dict(item) for item in data.get("flow", [])],
            enabled=bool(data.get("enabled", True)),
            task_type=task_type,
            auction_config=auction_config,
        )


@dataclass(slots=True)
class TaskPlan:
    name: str
    tasks: list[TaskBranch] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskPlan":
        return cls(
            name=str(data.get("name", "")),
            tasks=[TaskBranch.from_dict(item) for item in data.get("tasks", [])],
        )


@dataclass(slots=True)
class AppConfig:
    window_keyword: str = "斗罗大陆H5"
    templates_dir: str = "assets/templates"
    default_threshold: float = 0.88
    default_retries: int = 3
    default_delay_after_click: float = 0.5
    selected_plan: str = "方案1"
    selected_task: str = "神界中枢刷怪"
    window_task_bindings: dict[str, list[str]] = field(default_factory=dict)
    window_task_queues: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    task_plans: list[TaskPlan] = field(default_factory=list)
    flow: list[FlowStep] = field(default_factory=list)

    def normalized_flow(self) -> list[FlowStep]:
        task = self.active_task()
        if task:
            return task.flow
        return self.flow

    def active_task(self) -> TaskBranch | None:
        for plan in self.task_plans:
            if plan.name != self.selected_plan:
                continue
            for task in plan.tasks:
                if task.name == self.selected_task and task.enabled:
                    return task
        return None

    def for_task(self, plan_name: str, task_name: str) -> "AppConfig":
        cloned = deepcopy(self)
        cloned.selected_plan = plan_name
        cloned.selected_task = task_name
        return cloned

    def add_task_plan(self, name: str) -> TaskPlan:
        plan = TaskPlan(name=_unique_name(name.strip() or "新方案", [item.name for item in self.task_plans]))
        self.task_plans.append(plan)
        self.selected_plan = plan.name
        self.selected_task = ""
        return plan

    def rename_task_plan(self, old_name: str, new_name: str) -> TaskPlan | None:
        plan = next((item for item in self.task_plans if item.name == old_name), None)
        if not plan:
            return None
        names = [item.name for item in self.task_plans if item is not plan]
        renamed = _unique_name(new_name.strip() or old_name, names)
        for title, binding in self.window_task_bindings.items():
            if binding and binding[0] == old_name:
                self.window_task_bindings[title] = [renamed, binding[1] if len(binding) > 1 else "", binding[2] if len(binding) > 2 else FLOW_TASK_TYPE]
        for queue in self.window_task_queues.values():
            for item in queue:
                if item.get("plan_name") == old_name:
                    item["plan_name"] = renamed
        plan.name = renamed
        if self.selected_plan == old_name:
            self.selected_plan = renamed
        return plan

    def remove_task_plan(self, name: str) -> TaskPlan | None:
        if len(self.task_plans) <= 1:
            return None
        removed = next((item for item in self.task_plans if item.name == name), None)
        if not removed:
            return None
        self.task_plans = [item for item in self.task_plans if item.name != name]
        self.window_task_bindings = {
            title: binding for title, binding in self.window_task_bindings.items() if not binding or binding[0] != name
        }
        self.window_task_queues = {
            title: [item for item in queue if item.get("plan_name") != name]
            for title, queue in self.window_task_queues.items()
        }
        if self.selected_plan == name:
            self.selected_plan = self.task_plans[0].name
            self.selected_task = self.task_plans[0].tasks[0].name if self.task_plans[0].tasks else ""
        return removed

    def add_task(self, plan_name: str, name: str, task_type: str = FLOW_TASK_TYPE) -> TaskBranch:
        plan = self._find_plan(plan_name)
        if not plan:
            plan = self.add_task_plan(plan_name)
        unique = _unique_name(name.strip() or "新任务", [item.name for item in plan.tasks])
        auction_config = AuctionTaskConfig(task_name=unique) if task_type == AUCTION_TASK_TYPE else None
        task = TaskBranch(name=unique, task_type=task_type, auction_config=auction_config)
        plan.tasks.append(task)
        self.selected_plan = plan.name
        self.selected_task = task.name
        return task

    def copy_task(self, plan_name: str, source_task_name: str, name: str) -> TaskBranch:
        plan = self._find_plan(plan_name)
        if not plan:
            raise ValueError(f"方案不存在: {plan_name}")
        source = next((item for item in plan.tasks if item.name == source_task_name), None)
        if not source:
            raise ValueError(f"任务不存在: {source_task_name}")
        copied = deepcopy(source)
        copied.name = _unique_name(name.strip() or f"{source.name} 副本", [item.name for item in plan.tasks])
        plan.tasks.append(copied)
        self.selected_plan = plan.name
        self.selected_task = copied.name
        return copied

    def remove_task(self, plan_name: str, task_name: str) -> TaskBranch | None:
        plan = self._find_plan(plan_name)
        if not plan or len(plan.tasks) <= 1:
            return None
        removed = next((item for item in plan.tasks if item.name == task_name), None)
        if not removed:
            return None
        plan.tasks = [item for item in plan.tasks if item.name != task_name]
        self.window_task_bindings = {
            title: binding
            for title, binding in self.window_task_bindings.items()
            if not binding or binding[:2] != [plan_name, task_name]
        }
        self.window_task_queues = {
            title: [item for item in queue if [item.get("plan_name"), item.get("task_name")] != [plan_name, task_name]]
            for title, queue in self.window_task_queues.items()
        }
        if self.selected_plan == plan_name and self.selected_task == task_name:
            self.selected_task = plan.tasks[0].name if plan.tasks else ""
        return removed

    def _find_plan(self, name: str) -> TaskPlan | None:
        return next((plan for plan in self.task_plans if plan.name == name), None)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        flow = [FlowStep.from_dict(item) for item in data.get("flow", [])]
        task_plans = [TaskPlan.from_dict(item) for item in data.get("task_plans", [])] or default_task_plans()
        bindings = _bindings(data.get("window_task_bindings", {}))
        queues = _queues(data.get("window_task_queues", {}), bindings)
        return cls(
            window_keyword=str(data.get("window_keyword", "斗罗大陆H5")),
            templates_dir=str(data.get("templates_dir", "assets/templates")),
            default_threshold=float(data.get("default_threshold", 0.88)),
            default_retries=int(data.get("default_retries", 3)),
            default_delay_after_click=float(data.get("default_delay_after_click", 0.5)),
            selected_plan=str(data.get("selected_plan", "方案1")),
            selected_task=str(data.get("selected_task", "神界中枢刷怪")),
            window_task_bindings=bindings,
            window_task_queues=queues,
            task_plans=task_plans,
            flow=flow,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["flow"] = [asdict(step) for step in self.flow]
        return data


def default_config() -> AppConfig:
    return AppConfig(
        selected_plan="方案1",
        selected_task="神界中枢刷怪",
        task_plans=default_task_plans(),
        flow=[FlowStep(name=name, template=f"{index + 1:02d}_{name}.png") for index, name in enumerate(DEFAULT_FLOW_NAMES)],
    )


def default_task_plans() -> list[TaskPlan]:
    shenjie_task = TaskBranch(
        name="神界中枢刷怪",
        description="神界大陆 -> 神界中枢 -> 加入战场 -> 刷怪界面一键挑战 -> 掉落单双倍处理",
        flow=SHENJIE_BRANCH_FLOW,
    )
    return [TaskPlan(name="方案1", tasks=[shenjie_task])]


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        return default_config()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return AppConfig.from_dict(data)


def save_config(path: Path, config: AppConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def resolve_project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return resource_path(resolved)


def resolve_templates_dir(config: AppConfig) -> Path:
    return resolve_project_path(config.templates_dir)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_roi(value: Any) -> list[int] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        return [int(part) for part in parts] if parts else None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [int(part) for part in value]
    return None


def _bindings(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for title, binding in value.items():
        if isinstance(binding, (list, tuple)) and len(binding) >= 2:
            task_type = str(binding[2]) if len(binding) > 2 else FLOW_TASK_TYPE
            if task_type not in {FLOW_TASK_TYPE, AUCTION_TASK_TYPE}:
                task_type = FLOW_TASK_TYPE
            result[str(title)] = [str(binding[0]), str(binding[1]), task_type]
    return result


def _queues(value: Any, legacy_bindings: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    if isinstance(value, dict):
        for title, queue in value.items():
            normalized = [_queue_item(item, index + 1) for index, item in enumerate(queue if isinstance(queue, list) else [])]
            normalized = [item for item in normalized if item]
            if normalized:
                result[str(title)] = normalized
    for title, binding in legacy_bindings.items():
        if title not in result and binding:
            result[title] = [
                {
                    "plan_name": binding[0],
                    "task_name": binding[1],
                    "task_type": binding[2] if len(binding) > 2 else FLOW_TASK_TYPE,
                    "enabled": True,
                    "order": 1,
                    "config_mode": "template_ref",
                    "continue_on_failure": False,
                    "continue_on_success": True,
                    "stop_window_after_queue": True,
                }
            ]
    return result


def _queue_item(value: Any, order: int) -> dict[str, Any] | None:
    if isinstance(value, dict):
        plan_name = str(value.get("plan_name") or value.get("plan") or "")
        task_name = str(value.get("task_name") or value.get("task") or value.get("name") or "")
        task_type = str(value.get("task_type", FLOW_TASK_TYPE))
        enabled = bool(value.get("enabled", True))
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        plan_name = str(value[0])
        task_name = str(value[1])
        task_type = str(value[2]) if len(value) > 2 else FLOW_TASK_TYPE
        enabled = bool(value[3]) if len(value) > 3 else True
    else:
        return None
    if not plan_name or not task_name:
        return None
    if task_type not in {FLOW_TASK_TYPE, AUCTION_TASK_TYPE}:
        task_type = FLOW_TASK_TYPE
    return {
        "plan_name": plan_name,
        "task_name": task_name,
        "task_type": task_type,
        "enabled": enabled,
        "order": int(value.get("order", order)) if isinstance(value, dict) else order,
        "config_mode": "template_ref",
        "continue_on_failure": bool(value.get("continue_on_failure", False)) if isinstance(value, dict) else False,
        "continue_on_success": bool(value.get("continue_on_success", True)) if isinstance(value, dict) else True,
        "stop_window_after_queue": bool(value.get("stop_window_after_queue", True)) if isinstance(value, dict) else True,
    }


def _unique_name(base: str, existing: list[str]) -> str:
    if base not in existing:
        return base
    index = 2
    while f"{base} {index}" in existing:
        index += 1
    return f"{base} {index}"
