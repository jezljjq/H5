import importlib
import unittest


class EntrypointTests(unittest.TestCase):
    def test_main_module_imports_without_gui_dependencies(self):
        module = importlib.import_module("main")

        self.assertTrue(callable(module.main))

    def test_build_elevation_parameters_include_script_and_args(self):
        module = importlib.import_module("main")

        executable, params = module._build_elevation_command(
            "D:/Python/pythonw.exe",
            ["D:/Ai/codex/H5/main.py", "--flag"],
        )

        self.assertEqual(executable, "D:/Python/pythonw.exe")
        self.assertIn('"D:/Ai/codex/H5/main.py"', params)
        self.assertIn('"--flag"', params)


if __name__ == "__main__":
    unittest.main()
