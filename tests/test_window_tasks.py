import unittest

from h5bot.auction import AuctionRunner
from h5bot.auction_config import AUCTION_TASK_TYPE, FLOW_TASK_TYPE, AuctionTaskConfig
from h5bot.config import AppConfig, FlowStep, TaskBranch, TaskPlan
from h5bot.flow import FlowRunner
from h5bot.window_tasks import (
    WindowQueuedTask,
    WindowTaskBinding,
    binding_for_task,
    create_runner_for_binding,
    normalize_window_task_binding,
    normalize_window_task_queue,
    task_type_label,
)


class WindowTaskBindingTests(unittest.TestCase):
    def test_legacy_two_field_binding_is_normalized_as_flow_task(self):
        binding = normalize_window_task_binding(["方案1", "神界中枢刷怪"])

        self.assertEqual(binding, WindowTaskBinding("方案1", "神界中枢刷怪", FLOW_TASK_TYPE))
        self.assertEqual(binding.to_list(), ["方案1", "神界中枢刷怪", FLOW_TASK_TYPE])

    def test_three_field_binding_preserves_auction_task_type(self):
        binding = normalize_window_task_binding(["方案1", "自动抢拍", AUCTION_TASK_TYPE])

        self.assertEqual(binding.plan_name, "方案1")
        self.assertEqual(binding.task_name, "自动抢拍")
        self.assertEqual(binding.task_type, AUCTION_TASK_TYPE)
        self.assertEqual(task_type_label(binding.task_type), "自动抢拍任务")

    def test_binding_for_task_uses_the_selected_task_type(self):
        task = TaskBranch("自动抢拍", task_type=AUCTION_TASK_TYPE, auction_config=AuctionTaskConfig("自动抢拍"))

        binding = binding_for_task("方案1", task)

        self.assertEqual(binding.to_list(), ["方案1", "自动抢拍", AUCTION_TASK_TYPE])

    def test_create_runner_for_binding_uses_flow_runner_for_flow_task(self):
        config = AppConfig(
            task_plans=[
                TaskPlan(
                    "方案1",
                    [TaskBranch("普通任务", task_type=FLOW_TASK_TYPE, flow=[FlowStep("入口", "entry.png")])],
                )
            ]
        )

        runner, task = create_runner_for_binding(
            object(),
            config,
            WindowTaskBinding("方案1", "普通任务", FLOW_TASK_TYPE),
            lambda _message: None,
            should_stop=lambda: False,
            should_pause=lambda: False,
        )

        self.assertIsInstance(runner, FlowRunner)
        self.assertEqual(task.name, "普通任务")

    def test_create_runner_for_binding_uses_auction_runner_for_auction_task(self):
        auction_config = AuctionTaskConfig("自动抢拍")
        config = AppConfig(
            task_plans=[
                TaskPlan(
                    "方案1",
                    [TaskBranch("自动抢拍", task_type=AUCTION_TASK_TYPE, auction_config=auction_config)],
                )
            ]
        )

        runner, task = create_runner_for_binding(
            object(),
            config,
            WindowTaskBinding("方案1", "自动抢拍", AUCTION_TASK_TYPE),
            lambda _message: None,
            should_stop=lambda: False,
            should_pause=lambda: False,
        )

        self.assertIsInstance(runner, AuctionRunner)
        self.assertEqual(task.name, "自动抢拍")

    def test_window_task_queue_can_contain_multiple_task_types_in_order(self):
        queue = normalize_window_task_queue(
            [
                {"plan_name": "方案1", "task_name": "神界中枢刷怪", "task_type": FLOW_TASK_TYPE, "enabled": True},
                {"plan_name": "方案1", "task_name": "自动抢拍", "task_type": AUCTION_TASK_TYPE, "enabled": True},
                {"plan_name": "方案2", "task_name": "每日任务", "task_type": FLOW_TASK_TYPE, "enabled": False},
            ]
        )

        self.assertEqual([item.task_name for item in queue], ["神界中枢刷怪", "自动抢拍", "每日任务"])
        self.assertEqual([item.task_type for item in queue], [FLOW_TASK_TYPE, AUCTION_TASK_TYPE, FLOW_TASK_TYPE])
        self.assertEqual([item.enabled for item in queue], [True, True, False])

    def test_legacy_binding_migrates_to_single_queue_item(self):
        queue = normalize_window_task_queue(None, legacy_binding=["方案1", "神界中枢刷怪", FLOW_TASK_TYPE])

        self.assertEqual(queue, [WindowQueuedTask("方案1", "神界中枢刷怪", FLOW_TASK_TYPE, True)])
        self.assertEqual(queue[0].to_dict()["order"], 1)


if __name__ == "__main__":
    unittest.main()
