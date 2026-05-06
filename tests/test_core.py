import tempfile
import unittest
from pathlib import Path

from h5bot.config import AppConfig, FlowStep, TaskBranch, TaskPlan, default_config, load_config, save_config
from h5bot.flow import FlowRunner


class FakeAutomation:
    def __init__(self, matches):
        self.matches = matches
        self.clicks = []
        self.find_calls = []

    def capture_window(self, hwnd):
        return f"image:{hwnd}"

    def find_template(self, image, template_path, threshold, roi=None):
        self.find_calls.append((Path(template_path).name, roi))
        return self.matches.get(Path(template_path).name)

    def background_click(self, hwnd, x, y):
        self.clicks.append((hwnd, x, y))
        return True


class FakeDirectAutomation(FakeAutomation):
    def __init__(self, matches):
        super().__init__(matches)
        self.capture_calls = []

    def capture_window(self, hwnd):
        self.capture_calls.append(hwnd)
        return super().capture_window(hwnd)

    def find_template_in_window(self, hwnd, template_path, threshold, roi=None):
        self.find_calls.append((hwnd, Path(template_path).name, roi))
        return self.matches.get(Path(template_path).name)


class FakeGroupAutomation(FakeAutomation):
    def __init__(self, matches):
        super().__init__(matches)
        self.group_calls = []

    def find_any_template_in_window(self, hwnd, template_paths, threshold, roi=None):
        names = [Path(path).name for path in template_paths]
        self.group_calls.append((hwnd, names, roi))
        for index, name in enumerate(names):
            if name in self.matches:
                return index, self.matches[name]
        return None


class ConfigTests(unittest.TestCase):
    def test_config_round_trip_preserves_window_keyword_and_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = AppConfig(
                window_keyword="斗罗大陆H5",
                default_threshold=0.91,
                default_retries=2,
                window_task_bindings={"斗罗大陆H5-2": ["方案1", "神界中枢刷怪", "flow"]},
                selected_plan="方案1",
                selected_task="神界中枢刷怪",
                task_plans=[
                    TaskPlan(
                        name="方案1",
                        tasks=[
                            TaskBranch(
                                name="神界中枢刷怪",
                                description="进入神界大陆和神界中枢后加入战场",
                                flow=[FlowStep("神界大陆", "shenjie.png")],
                            )
                        ],
                    )
                ],
                flow=[
                    FlowStep(
                        name="入口图标",
                        template="entry.png",
                        threshold=0.88,
                        retries=3,
                        delay_after_click=0.25,
                    )
                ],
            )

            save_config(path, config)
            loaded = load_config(path)

            self.assertEqual(loaded.window_keyword, "斗罗大陆H5")
            self.assertEqual(loaded.default_threshold, 0.91)
            self.assertEqual(loaded.flow[0].template, "entry.png")
            self.assertEqual(loaded.selected_task, "神界中枢刷怪")
            self.assertEqual(loaded.task_plans[0].tasks[0].flow[0].template, "shenjie.png")
            self.assertEqual(loaded.window_task_bindings["斗罗大陆H5-2"], ["方案1", "神界中枢刷怪", "flow"])

    def test_legacy_window_task_binding_loads_with_flow_task_type(self):
        config = AppConfig.from_dict({"window_task_bindings": {"斗罗大陆H5-1": ["方案1", "神界中枢刷怪"]}})

        self.assertEqual(config.window_task_bindings["斗罗大陆H5-1"], ["方案1", "神界中枢刷怪", "flow"])
        self.assertEqual(config.window_task_queues["斗罗大陆H5-1"][0]["task_name"], "神界中枢刷怪")
        self.assertEqual(config.window_task_queues["斗罗大陆H5-1"][0]["task_type"], "flow")

    def test_config_round_trip_preserves_window_task_queue(self):
        config = AppConfig.from_dict(
            {
                "window_task_queues": {
                    "斗罗大陆H5-1": [
                        {"plan_name": "方案1", "task_name": "神界中枢刷怪", "task_type": "flow", "enabled": True},
                        {"plan_name": "方案1", "task_name": "自动抢拍", "task_type": "auction", "enabled": False},
                    ]
                }
            }
        )

        self.assertEqual([item["task_name"] for item in config.window_task_queues["斗罗大陆H5-1"]], ["神界中枢刷怪", "自动抢拍"])
        self.assertFalse(config.window_task_queues["斗罗大陆H5-1"][1]["enabled"])

    def test_default_config_contains_first_shenjie_branch(self):
        config = default_config()

        self.assertEqual(config.selected_plan, "方案1")
        self.assertEqual(config.selected_task, "神界中枢刷怪")
        self.assertEqual([plan.name for plan in config.task_plans], ["方案1"])
        task = config.active_task()
        self.assertIsNotNone(task)
        names = [step.name for step in task.flow]
        self.assertIn("神界大陆", names)
        self.assertIn("无Boss检测", names)
        self.assertIn("单双倍选择", names)
        self.assertIn("双倍按钮", names)

    def test_old_config_without_task_plans_gets_default_shenjie_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"window_keyword": "斗罗大陆H5", "flow": []}', encoding="utf-8")

            loaded = load_config(path)

            self.assertEqual(loaded.selected_task, "神界中枢刷怪")
            self.assertIsNotNone(loaded.active_task())

    def test_config_can_clone_for_a_specific_task_without_mutating_original(self):
        config = default_config()

        cloned = config.for_task("方案2", "日常任务")

        self.assertEqual(config.selected_plan, "方案1")
        self.assertEqual(cloned.selected_plan, "方案2")
        self.assertEqual(cloned.selected_task, "日常任务")

    def test_config_can_add_rename_and_remove_task_plans(self):
        config = default_config()

        added = config.add_task_plan("方案1")
        config.rename_task_plan("方案1", "主线方案")
        config.remove_task_plan(added.name)

        self.assertEqual(config.selected_plan, "主线方案")
        self.assertEqual([plan.name for plan in config.task_plans], ["主线方案"])

    def test_config_can_add_copy_and_remove_tasks(self):
        config = default_config()

        added = config.add_task("方案1", "神界中枢刷怪")
        copied = config.copy_task("方案1", "神界中枢刷怪", "神界中枢刷怪")
        config.remove_task("方案1", added.name)

        plan = config.task_plans[0]
        self.assertNotIn(added.name, [task.name for task in plan.tasks])
        self.assertIn(copied.name, [task.name for task in plan.tasks])
        self.assertIsNot(plan.tasks[0].flow, copied.flow)
        self.assertEqual(config.selected_task, copied.name)


class FlowRunnerTests(unittest.TestCase):
    def test_runner_clicks_each_configured_step_in_order(self):
        automation = FakeAutomation(
            {
                "entry.png": (10, 20, 0.94),
                "scene.png": (30, 40, 0.95),
            }
        )
        config = AppConfig(
            flow=[
                FlowStep("入口图标", "entry.png", retries=1),
                FlowStep("刷怪场景", "scene.png", retries=1),
            ]
        )
        events = []

        result = FlowRunner(automation, config, events.append, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(automation.clicks, [(1001, 10, 20), (1001, 30, 40)])
        self.assertIn("入口图标", "\n".join(events))
        self.assertIn("刷怪场景", "\n".join(events))

    def test_runner_stops_without_clicking_when_required_template_is_missing(self):
        automation = FakeAutomation({})
        config = AppConfig(flow=[FlowStep("BOSS图标", "boss.png", retries=1)])

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertFalse(result.ok)
        self.assertIn("BOSS图标", result.message)
        self.assertEqual(automation.clicks, [])

    def test_runner_uses_selected_task_branch_before_legacy_flow(self):
        automation = FakeAutomation(
            {
                "shenjie.png": (11, 12, 0.94),
                "join.png": (21, 22, 0.95),
                "legacy.png": (31, 32, 0.96),
            }
        )
        config = AppConfig(
            selected_plan="方案1",
            selected_task="神界中枢刷怪",
            task_plans=[
                TaskPlan(
                    name="方案1",
                    tasks=[
                        TaskBranch(
                            name="神界中枢刷怪",
                            flow=[
                                FlowStep("神界大陆", "shenjie.png", retries=1),
                                FlowStep("加入战场", "join.png", retries=1),
                            ],
                        )
                    ],
                )
            ],
            flow=[FlowStep("旧流程", "legacy.png", retries=1)],
        )

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(automation.clicks[:2], [(1001, 11, 12), (1001, 21, 22)])
        self.assertNotIn((1001, 31, 32), automation.clicks)

    def test_runner_matches_multiple_templates_and_passes_roi(self):
        automation = FakeAutomation({"boss_alt.png": (44, 55, 0.93)})
        config = AppConfig(
            flow=[
                FlowStep(
                    name="Boss按钮",
                    templates=["boss_main.png", "boss_alt.png"],
                    roi=[9, 234, 58, 624],
                    retries=1,
                )
            ]
        )

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(automation.clicks, [(1001, 44, 55)])
        self.assertEqual(
            automation.find_calls,
            [("boss_main.png", [9, 234, 58, 624]), ("boss_alt.png", [9, 234, 58, 624])],
        )

    def test_runner_can_stop_when_no_boss_template_is_found(self):
        automation = FakeAutomation({"no_boss.png": (12, 13, 0.91), "challenge.png": (50, 60, 0.94)})
        config = AppConfig(
            flow=[
                FlowStep("无Boss检测", "no_boss.png", retries=1, on_found="stop"),
                FlowStep("一键挑战", "challenge.png", retries=1),
            ]
        )

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertFalse(result.ok)
        self.assertIn("无Boss检测", result.message)
        self.assertEqual(automation.clicks, [])

    def test_runner_jumps_when_template_is_not_found(self):
        automation = FakeAutomation({"challenge.png": (50, 60, 0.94)})
        config = AppConfig(
            flow=[
                FlowStep("无Boss检测", "no_boss.png", retries=1, on_not_found="jump", not_found_next="一键挑战"),
                FlowStep("停止任务", "", enabled=True),
                FlowStep("一键挑战", "challenge.png", retries=1),
            ]
        )

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(automation.clicks, [(1001, 50, 60)])

    def test_runner_uses_direct_window_template_matching_when_available(self):
        automation = FakeDirectAutomation({"entry.png": (10, 20, 0.94)})
        config = AppConfig(flow=[FlowStep("入口图标", "entry.png", retries=1)])

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(automation.clicks, [(1001, 10, 20)])
        self.assertEqual(automation.capture_calls, [])
        self.assertEqual(automation.find_calls, [(1001, "entry.png", None)])

    def test_runner_uses_group_window_template_matching_when_available(self):
        automation = FakeGroupAutomation({"boss_alt.png": (44, 55, 0.93)})
        config = AppConfig(
            flow=[
                FlowStep(
                    name="Boss按钮",
                    templates=["boss_main.png", "boss_alt.png"],
                    roi=[9, 234, 58, 624],
                    retries=1,
                )
            ]
        )

        result = FlowRunner(automation, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(automation.clicks, [(1001, 44, 55)])
        self.assertEqual(automation.find_calls, [])
        self.assertEqual(automation.group_calls, [(1001, ["boss_main.png", "boss_alt.png"], [9, 234, 58, 624])])


if __name__ == "__main__":
    unittest.main()
