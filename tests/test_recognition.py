import tempfile
import unittest
from pathlib import Path

from h5bot.config import AppConfig, FlowStep
from h5bot.recognition import RecognitionResult, recognize_step, resolve_step_runtime_params


class FakeGroupBackend:
    def __init__(self, result=None, backend_name="大漠"):
        self.result = result
        self.last_recognition_backend = backend_name
        self.calls = []

    def find_any_template_in_window(self, hwnd, template_paths, threshold, roi=None):
        self.calls.append((hwnd, [Path(path).name for path in template_paths], threshold, roi))
        return self.result


class RecognitionTests(unittest.TestCase):
    def test_runtime_params_use_global_threshold_and_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(templates_dir=tmp, default_threshold=0.91, default_retries=4)
            step = FlowStep("旧步骤", templates=["a.png"], threshold=0.2, retries=1, roi=[1, 2, 3, 4])

            params = resolve_step_runtime_params(config, step)

        self.assertEqual(params.threshold, 0.91)
        self.assertEqual(params.retries, 4)
        self.assertEqual(params.roi, [1, 2, 3, 4])

    def test_recognize_step_uses_group_window_entry_with_global_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.png").write_bytes(b"fake")
            Path(tmp, "b.png").write_bytes(b"fake")
            backend = FakeGroupBackend((1, (30, 40, 0.92)))
            config = AppConfig(templates_dir=tmp, default_threshold=0.87, default_retries=5)
            step = FlowStep("测试步骤", templates=["a.png", "b.png"], threshold=0.2, retries=1, roi=[5, 6, 7, 8])

            result = recognize_step(backend, 1001, config, step, mode="test")

        self.assertTrue(result.success)
        self.assertEqual(result.template_name, "b.png")
        self.assertEqual(result.threshold, 0.87)
        self.assertEqual(result.retries, 5)
        self.assertEqual(backend.calls, [(1001, ["a.png", "b.png"], 0.87, [5, 6, 7, 8])])

    def test_log_message_contains_required_fields_for_success_and_failure(self):
        success = RecognitionResult(
            True,
            "大漠",
            Path("a.png"),
            "a.png",
            x=11,
            y=22,
            score=0.93,
            roi=[1, 2, 3, 4],
            threshold=0.88,
            retries=3,
        )
        failure = RecognitionResult(
            False,
            "OpenCV",
            None,
            "",
            roi=None,
            threshold=0.88,
            retries=3,
            error="模板文件不存在",
        )

        success_log = success.log_message("测试识别", 1001, "斗罗大陆H5", "入口", ["a.png"])
        failure_log = failure.log_message("正式运行", 1002, "斗罗大陆H5-2", "入口", ["missing.png"])

        for text in ["操作来源 测试识别", "hwnd 1001", "窗口标题 斗罗大陆H5", "步骤名称 入口", "模板列表 a.png", "ROI 1,2,3,4", "阈值 0.88", "使用后端 大漠", "是否命中 是", "命中模板 a.png", "命中坐标 (11, 22)", "失败原因 -"]:
            self.assertIn(text, success_log)
        for text in ["操作来源 正式运行", "使用后端 OpenCV", "是否命中 否", "命中模板 -", "命中坐标 -", "失败原因 模板文件不存在"]:
            self.assertIn(text, failure_log)


if __name__ == "__main__":
    unittest.main()
