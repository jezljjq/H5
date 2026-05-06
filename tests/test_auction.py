import tempfile
import unittest
from pathlib import Path

from h5bot.auction import AuctionRunner, compute_button_roi
from h5bot.auction_config import AuctionTaskConfig
from h5bot.config import AppConfig, FlowStep, TaskBranch, TaskPlan, load_config, save_config
from h5bot.flow import FlowRunner


class FakeAuctionBackend:
    def __init__(self, matches=None, client_size=(800, 600), bind_ok=True):
        self.matches = matches or {}
        self.client_size = client_size
        self.bind_ok = bind_ok
        self.find_calls = []
        self.clicks = []
        self.scrolls = []
        self.last_recognition_backend = "大漠"

    def bind_window(self, hwnd):
        return self.bind_ok

    def client_size_for_window(self, hwnd):
        return self.client_size

    def find_any_template_in_window(self, hwnd, template_paths, threshold, roi=None):
        names = [Path(path).name for path in template_paths]
        self.find_calls.append((hwnd, names, roi))
        for index, name in enumerate(names):
            values = self.matches.get(name, [])
            if values:
                match = values.pop(0)
                if match:
                    return index, match
        return None

    def background_click(self, hwnd, x, y):
        self.clicks.append((hwnd, x, y))
        return True

    def scroll_window(self, hwnd, delta):
        self.scrolls.append((hwnd, delta))
        return True


class AuctionConfigTests(unittest.TestCase):
    def test_auction_task_config_defaults_match_first_stage_requirements(self):
        config = AuctionTaskConfig(task_name="抢拍")

        self.assertTrue(config.enabled)
        self.assertEqual(config.auction_entry_templates, [])
        self.assertEqual(config.auction_page_templates, [])
        self.assertIsNone(config.auction_entry_roi)
        self.assertIsNone(config.auction_page_roi)
        self.assertEqual(config.pre_scan_interval_ms, 300)
        self.assertEqual(config.button_check_interval_ms, 50)
        self.assertEqual(config.confirm_check_interval_ms, 50)
        self.assertEqual(config.scroll_wait_ms, 500)
        self.assertEqual(config.max_scroll_count, 10)
        self.assertEqual(config.scroll_delta, -3)
        self.assertEqual(config.buy_button_offset_x, 400)
        self.assertEqual(config.buy_button_offset_y, 0)
        self.assertEqual(config.buy_button_roi_width, 120)
        self.assertEqual(config.buy_button_roi_height, 50)
        self.assertTrue(config.lock_target_before_start)
        self.assertTrue(config.stop_scroll_after_target_found)
        self.assertTrue(config.click_only_when_button_active)
        self.assertTrue(config.success_continue_scan)
        self.assertFalse(config.stop_after_success)
        self.assertTrue(config.no_target_after_full_scan_end)

    def test_auction_task_config_round_trip_preserves_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = AppConfig(
                selected_plan="方案1",
                selected_task="自动抢拍",
                task_plans=[
                    TaskPlan(
                        "方案1",
                        [
                            TaskBranch(
                                "自动抢拍",
                                task_type="auction",
                                auction_config=AuctionTaskConfig(
                                    task_name="自动抢拍",
                                    auction_entry_templates=["entry.bmp"],
                                    auction_page_templates=["page.bmp"],
                                    auction_entry_roi=[5, 6, 70, 80],
                                    auction_page_roi=[7, 8, 90, 100],
                                    target_templates=["target.bmp"],
                                    buy_button_active_templates=["active.bmp"],
                                    auction_list_roi=[1, 2, 300, 400],
                                    confirm_roi=[10, 20, 200, 220],
                                    max_scroll_count=3,
                                ),
                            )
                        ],
                    )
                ],
            )

            save_config(path, config)
            loaded = load_config(path)

        task = loaded.active_task()
        self.assertEqual(task.task_type, "auction")
        self.assertEqual(task.auction_config.auction_entry_templates, ["entry.bmp"])
        self.assertEqual(task.auction_config.auction_page_templates, ["page.bmp"])
        self.assertEqual(task.auction_config.auction_entry_roi, [5, 6, 70, 80])
        self.assertEqual(task.auction_config.auction_page_roi, [7, 8, 90, 100])
        self.assertEqual(task.auction_config.target_templates, ["target.bmp"])
        self.assertEqual(task.auction_config.buy_button_active_templates, ["active.bmp"])
        self.assertEqual(task.auction_config.auction_list_roi, [1, 2, 300, 400])
        self.assertEqual(task.auction_config.max_scroll_count, 3)

    def test_normal_flow_task_stays_flow_type_and_flow_runner_still_uses_steps(self):
        backend = FakeAuctionBackend({"a.png": [(10, 20, 0.95)]})
        config = AppConfig(flow=[FlowStep("普通步骤", "a.png", retries=1)])

        result = FlowRunner(backend, config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001)

        self.assertTrue(result.ok)
        self.assertEqual(backend.clicks, [(1001, 10, 20)])


class AuctionRunnerTests(unittest.TestCase):
    def test_compute_button_roi_from_target_coordinate_and_clamps_to_window(self):
        config = AuctionTaskConfig(
            task_name="抢拍",
            buy_button_offset_x=400,
            buy_button_offset_y=0,
            buy_button_roi_width=120,
            buy_button_roi_height=50,
        )

        self.assertEqual(compute_button_roi(100, 200, config, (800, 600)), [500, 200, 620, 250])
        self.assertEqual(compute_button_roi(760, 580, config, (800, 600)), [799, 580, 800, 600])

    def test_gray_button_hit_does_not_click(self):
        auction_config = AuctionTaskConfig(
            task_name="抢拍",
            auction_entry_templates=["entry.bmp"],
            auction_page_templates=["page.bmp"],
            target_templates=["target.bmp"],
            buy_button_gray_templates=["gray.bmp"],
            buy_button_active_templates=["active.bmp"],
            confirm_templates=["confirm.bmp"],
            max_scroll_count=0,
        )
        backend = FakeAuctionBackend({"page.bmp": [(20, 30, 0.95)], "target.bmp": [(100, 100, 0.94)], "gray.bmp": [(500, 100, 0.91)]})

        result = AuctionRunner(backend, AppConfig(), auction_config, lambda _message: None, sleep=lambda _seconds: None, button_wait_attempts=1).run_window(1001, "斗罗大陆H5")

        self.assertFalse(result.success)
        self.assertEqual(backend.clicks, [])
        self.assertIn("按钮未激活", result.message)

    def test_active_button_hit_clicks_buy_and_confirm(self):
        auction_config = AuctionTaskConfig(
            task_name="抢拍",
            auction_entry_templates=["entry.bmp"],
            auction_page_templates=["page.bmp"],
            target_templates=["target.bmp"],
            buy_button_gray_templates=["gray.bmp"],
            buy_button_active_templates=["active.bmp"],
            confirm_templates=["confirm.bmp"],
            confirm_roi=[1, 2, 300, 300],
            stop_after_success=True,
        )
        backend = FakeAuctionBackend(
            {
                "target.bmp": [(100, 100, 0.94)],
                "page.bmp": [(20, 30, 0.95)],
                "active.bmp": [(520, 120, 0.92)],
                "confirm.bmp": [(150, 160, 0.93)],
            }
        )

        result = AuctionRunner(backend, AppConfig(), auction_config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001, "斗罗大陆H5")

        self.assertTrue(result.success)
        self.assertEqual(backend.clicks, [(1001, 560, 125), (1001, 150, 160)])

    def test_already_on_auction_page_skips_entry_click(self):
        auction_config = AuctionTaskConfig(
            task_name="抢拍",
            auction_entry_templates=["entry.bmp"],
            auction_page_templates=["page.bmp"],
            target_templates=["target.bmp"],
            buy_button_active_templates=["active.bmp"],
            confirm_templates=["confirm.bmp"],
            stop_after_success=True,
        )
        events = []
        backend = FakeAuctionBackend(
            {
                "page.bmp": [(20, 30, 0.95)],
                "target.bmp": [(100, 100, 0.94)],
                "active.bmp": [(520, 120, 0.92)],
                "confirm.bmp": [(150, 160, 0.93)],
            }
        )

        result = AuctionRunner(backend, AppConfig(), auction_config, events.append, sleep=lambda _seconds: None).run_window(1001, "斗罗大陆H5")

        self.assertTrue(result.success)
        self.assertNotIn((1001, 20, 30), backend.clicks)
        self.assertIn("已在拍卖界面，跳过入口点击", "\n".join(events))

    def test_clicks_entry_then_confirms_auction_page_when_not_already_inside(self):
        auction_config = AuctionTaskConfig(
            task_name="抢拍",
            auction_entry_templates=["entry.bmp"],
            auction_page_templates=["page.bmp"],
            auction_entry_roi=[1, 2, 200, 200],
            auction_page_roi=[3, 4, 300, 300],
            target_templates=["target.bmp"],
            buy_button_active_templates=["active.bmp"],
            confirm_templates=["confirm.bmp"],
            stop_after_success=True,
        )
        backend = FakeAuctionBackend(
            {
                "page.bmp": [None, (20, 30, 0.95)],
                "entry.bmp": [(40, 50, 0.96)],
                "target.bmp": [(100, 100, 0.94)],
                "active.bmp": [(520, 120, 0.92)],
                "confirm.bmp": [(150, 160, 0.93)],
            }
        )

        result = AuctionRunner(backend, AppConfig(), auction_config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001, "斗罗大陆H5")

        self.assertTrue(result.success)
        self.assertEqual(backend.clicks[0], (1001, 40, 50))
        self.assertEqual(backend.find_calls[0], (1001, ["page.bmp"], [3, 4, 300, 300]))
        self.assertEqual(backend.find_calls[1], (1001, ["entry.bmp"], [1, 2, 200, 200]))

    def test_no_target_scrolls_until_max_count_then_ends(self):
        auction_config = AuctionTaskConfig(
            task_name="抢拍",
            auction_entry_templates=["entry.bmp"],
            auction_page_templates=["page.bmp"],
            target_templates=["target.bmp"],
            buy_button_active_templates=["active.bmp"],
            confirm_templates=["confirm.bmp"],
            max_scroll_count=2,
        )
        backend = FakeAuctionBackend({"page.bmp": [(20, 30, 0.95)]})

        result = AuctionRunner(backend, AppConfig(), auction_config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001, "斗罗大陆H5")

        self.assertFalse(result.success)
        self.assertEqual(backend.scrolls, [(1001, -3), (1001, -3)])
        self.assertIn("完整扫描未找到目标", result.message)

    def test_missing_templates_do_not_crash_and_report_incomplete_config(self):
        auction_config = AuctionTaskConfig(task_name="抢拍")
        backend = FakeAuctionBackend({})

        result = AuctionRunner(backend, AppConfig(), auction_config, lambda _message: None, sleep=lambda _seconds: None).run_window(1001, "斗罗大陆H5")

        self.assertFalse(result.success)
        self.assertIn("配置不完整", result.message)


if __name__ == "__main__":
    unittest.main()
