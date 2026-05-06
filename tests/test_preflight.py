import tempfile
import unittest
from pathlib import Path

from h5bot.automation import GameWindow
from h5bot.config import AppConfig, FlowStep, TaskBranch, TaskPlan
from h5bot.preflight import run_preflight_checks


class FakeWin32Gui:
    def __init__(self, valid_hwnds):
        self.valid_hwnds = set(valid_hwnds)

    def IsWindow(self, hwnd):
        return hwnd in self.valid_hwnds


class FakeDm:
    def __init__(self, available):
        self._available = available

    def available(self):
        return self._available


class FakeBackend:
    def __init__(self, valid_hwnds=(1001,), dm_available=True):
        self.win32gui = FakeWin32Gui(valid_hwnds)
        self.dm_clicker = FakeDm(dm_available)


class PreflightTests(unittest.TestCase):
    def test_preflight_reports_invalid_roi_jump_missing_template_and_dm_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(
                templates_dir=tmp,
                selected_plan="方案1",
                selected_task="任务1",
                task_plans=[
                    TaskPlan(
                        "方案1",
                        [
                            TaskBranch(
                                "任务1",
                                flow=[
                                    FlowStep("入口", templates=["missing.png"], roi="bad", on_found="jump", found_next="不存在"),
                                    FlowStep("关闭", templates=[], enabled=False),
                                ],
                            )
                        ],
                    )
                ],
            )
            backend = FakeBackend(valid_hwnds=(1001,), dm_available=False)

            report = run_preflight_checks(config, [1001], [GameWindow(1001, "斗罗大陆H5")], backend)

        messages = "\n".join(issue.message for issue in report.issues)
        self.assertFalse(report.ok)
        self.assertIn("ROI 非法", messages)
        self.assertIn("入口", messages)
        self.assertIn("跳转目标不存在", messages)
        self.assertIn("模板文件不存在", messages)
        self.assertIn("大漠不可用", messages)

    def test_preflight_reports_invalid_window_and_missing_task(self):
        config = AppConfig(selected_plan="方案1", selected_task="不存在", task_plans=[TaskPlan("方案1", [TaskBranch("任务1", flow=[FlowStep("入口", templates=[])])])])
        backend = FakeBackend(valid_hwnds=())

        report = run_preflight_checks(config, [2002], [GameWindow(1001, "斗罗大陆H5")], backend)

        messages = "\n".join(issue.message for issue in report.issues)
        self.assertFalse(report.ok)
        self.assertIn("当前窗口无效", messages)
        self.assertIn("当前任务不存在", messages)

    def test_preflight_passes_when_only_existing_template_and_dm_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "ok.png").write_bytes(b"fake")
            config = AppConfig(
                templates_dir=tmp,
                selected_plan="方案1",
                selected_task="任务1",
                task_plans=[TaskPlan("方案1", [TaskBranch("任务1", flow=[FlowStep("入口", templates=["ok.png"], roi=[1, 2, 3, 4])])])],
            )
            backend = FakeBackend(valid_hwnds=(1001,), dm_available=True)

            report = run_preflight_checks(config, [1001], [GameWindow(1001, "斗罗大陆H5")], backend)

        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
