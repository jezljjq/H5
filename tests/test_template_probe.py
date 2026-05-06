import tempfile
import unittest
from pathlib import Path

from h5bot.config import AppConfig, FlowStep
from h5bot.template_probe import probe_step_templates, probe_step_templates_in_window


class FakeProbeBackend:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    def find_template(self, image, template_path, threshold, roi=None):
        self.calls.append((image, Path(template_path).name, threshold, roi))
        return self.matches.get(Path(template_path).name)


class FakeWindowProbeBackend:
    def __init__(self, grouped_match):
        self.grouped_match = grouped_match
        self.calls = []

    def find_any_template_in_window(self, hwnd, template_paths, threshold, roi=None):
        self.calls.append((hwnd, [Path(path).name for path in template_paths], threshold, roi))
        return self.grouped_match


class TemplateProbeTests(unittest.TestCase):
    def test_image_probe_directs_callers_to_window_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = FakeProbeBackend({})
            config = AppConfig(templates_dir=tmp, default_threshold=0.86)
            step = FlowStep("测试步骤", templates=["a.png", "b.png"], roi=[1, 2, 3, 4])

            result = probe_step_templates(backend, "image", config, step)

        self.assertFalse(result.ok)
        self.assertIn("窗口测试识别入口", result.message)
        self.assertEqual(backend.calls, [])

    def test_window_probe_uses_runtime_window_matching_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.png").write_bytes(b"fake")
            Path(tmp, "b.png").write_bytes(b"fake")
            backend = FakeWindowProbeBackend((1, (30, 40, 0.92)))
            config = AppConfig(templates_dir=tmp, default_threshold=0.86)
            step = FlowStep("测试步骤", templates=["a.png", "b.png"], roi=[1, 2, 3, 4])

            result = probe_step_templates_in_window(backend, 1001, config, step)

        self.assertTrue(result.ok)
        self.assertEqual(result.template, "b.png")
        self.assertEqual(result.match, (30, 40, 0.92))
        self.assertEqual(backend.calls, [(1001, ["a.png", "b.png"], 0.86, [1, 2, 3, 4])])


if __name__ == "__main__":
    unittest.main()
