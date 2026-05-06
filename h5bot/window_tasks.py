from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from h5bot.auction import AuctionRunner
from h5bot.auction_config import AUCTION_TASK_TYPE, FLOW_TASK_TYPE, AuctionTaskConfig
from h5bot.config import AppConfig, TaskBranch
from h5bot.flow import FlowRunner


TASK_TYPE_LABELS = {
    FLOW_TASK_TYPE: "普通流程任务",
    AUCTION_TASK_TYPE: "自动抢拍任务",
}


@dataclass(frozen=True, slots=True)
class WindowTaskBinding:
    plan_name: str
    task_name: str
    task_type: str = FLOW_TASK_TYPE

    def to_list(self) -> list[str]:
        return [self.plan_name, self.task_name, normalize_task_type(self.task_type)]


@dataclass(frozen=True, slots=True)
class WindowQueuedTask:
    plan_name: str
    task_name: str
    task_type: str = FLOW_TASK_TYPE
    enabled: bool = True
    continue_on_failure: bool = False
    continue_on_success: bool = True
    stop_window_after_queue: bool = True

    def to_binding(self) -> WindowTaskBinding:
        return WindowTaskBinding(self.plan_name, self.task_name, self.task_type)

    def to_dict(self, order: int = 1) -> dict[str, object]:
        return {
            "plan_name": self.plan_name,
            "task_name": self.task_name,
            "task_type": normalize_task_type(self.task_type),
            "enabled": bool(self.enabled),
            "order": int(order),
            "config_mode": "template_ref",
            "continue_on_failure": bool(self.continue_on_failure),
            "continue_on_success": bool(self.continue_on_success),
            "stop_window_after_queue": bool(self.stop_window_after_queue),
        }


def normalize_task_type(task_type: str | None) -> str:
    return AUCTION_TASK_TYPE if task_type == AUCTION_TASK_TYPE else FLOW_TASK_TYPE


def task_type_label(task_type: str | None) -> str:
    return TASK_TYPE_LABELS[normalize_task_type(task_type)]


def normalize_window_task_binding(value) -> WindowTaskBinding | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    return WindowTaskBinding(str(value[0]), str(value[1]), normalize_task_type(str(value[2]) if len(value) > 2 else FLOW_TASK_TYPE))


def normalize_window_task_queue(value, legacy_binding=None) -> list[WindowQueuedTask]:
    items = value if isinstance(value, list) else []
    queue: list[WindowQueuedTask] = []
    for item in items:
        queued = _normalize_queue_item(item)
        if queued:
            queue.append(queued)
    if not queue:
        binding = normalize_window_task_binding(legacy_binding)
        if binding:
            queue.append(WindowQueuedTask(binding.plan_name, binding.task_name, binding.task_type, True))
    return queue


def queue_to_config(queue: list[WindowQueuedTask]) -> list[dict[str, object]]:
    return [item.to_dict(index + 1) for index, item in enumerate(queue)]


def enabled_queue(queue: list[WindowQueuedTask]) -> list[WindowQueuedTask]:
    return [item for item in queue if item.enabled]


def _normalize_queue_item(item) -> WindowQueuedTask | None:
    if isinstance(item, WindowQueuedTask):
        return item
    if isinstance(item, dict):
        plan_name = str(item.get("plan_name") or item.get("plan") or "")
        task_name = str(item.get("task_name") or item.get("task") or item.get("name") or "")
        if not plan_name or not task_name:
            return None
        return WindowQueuedTask(
            plan_name,
            task_name,
            normalize_task_type(str(item.get("task_type", FLOW_TASK_TYPE))),
            bool(item.get("enabled", True)),
            bool(item.get("continue_on_failure", False)),
            bool(item.get("continue_on_success", True)),
            bool(item.get("stop_window_after_queue", True)),
        )
    binding = normalize_window_task_binding(item)
    if binding:
        return WindowQueuedTask(binding.plan_name, binding.task_name, binding.task_type, True)
    return None


def binding_for_task(plan_name: str, task: TaskBranch) -> WindowTaskBinding:
    return WindowTaskBinding(plan_name, task.name, normalize_task_type(task.task_type))


def find_task_for_binding(config: AppConfig, binding: WindowTaskBinding) -> TaskBranch | None:
    scoped = config.for_task(binding.plan_name, binding.task_name)
    task = scoped.active_task()
    if task is None:
        return None
    if normalize_task_type(task.task_type) != normalize_task_type(binding.task_type):
        task.task_type = normalize_task_type(binding.task_type)
    return task


def create_runner_for_binding(
    backend,
    config: AppConfig,
    binding: WindowTaskBinding,
    log: Callable[[str], None],
    should_stop: Callable[[], bool],
    should_pause: Callable[[], bool] | None = None,
):
    task = find_task_for_binding(config, binding)
    if task is None:
        raise ValueError(f"任务不存在: {binding.plan_name} / {binding.task_name}")
    scoped = config.for_task(binding.plan_name, binding.task_name)
    if normalize_task_type(binding.task_type) == AUCTION_TASK_TYPE:
        auction_config = task.auction_config or AuctionTaskConfig(task_name=task.name)
        return AuctionRunner(backend, scoped, auction_config, log, should_stop=should_stop), task
    return FlowRunner(backend, scoped, log, should_stop=should_stop, should_pause=should_pause), task
