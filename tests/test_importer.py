import base64
import tempfile
import unittest
from pathlib import Path

from h5bot.importer import parse_panda_script, export_panda_templates


BMP_1X1 = base64.b64encode(
    b"BM" + (58).to_bytes(4, "little") + b"\0\0\0\0" + (54).to_bytes(4, "little")
    + (40).to_bytes(4, "little") + (1).to_bytes(4, "little") + (1).to_bytes(4, "little")
    + (1).to_bytes(2, "little") + (24).to_bytes(2, "little") + b"\0" * 24 + b"\xff\0\0\0"
).decode("ascii")


class ImporterTests(unittest.TestCase):
    def test_parse_panda_script_extracts_step_and_image_names(self):
        script = (
            'INSERT INTO 步骤 (步骤号,排序号,操作,任务id,类型,图片识别_相似度,图片识别_找到后,'
            '图片识别_重复间隔,图片识别_重复次数,图片识别_找不到,图片识别_查找范围,'
            '图片识别_范围左x,图片识别_范围左y,图片识别_范围右x,图片识别_范围右y) '
            'values(292,"1","多图识别",[任务id],"Boss按钮1|按钮2",80,"鼠标左键点击",200,5,"跳过",'
            '"指定范围","9","234","58","624")\n'
            f'INSERT INTO 图片组 (任务id,步骤id,编号,图片,名称) values([任务id],[步骤id],"abc","{BMP_1X1}","Boss按钮1")\n'
        )

        parsed = parse_panda_script(script)

        self.assertEqual(len(parsed.steps), 1)
        self.assertEqual(parsed.steps[0].name, "Boss按钮1|按钮2")
        self.assertEqual(parsed.steps[0].roi, [9, 234, 58, 624])
        self.assertEqual(parsed.steps[0].images[0].name, "Boss按钮1")

    def test_export_panda_templates_writes_bmp_files_without_deleting_anything(self):
        script = (
            'INSERT INTO 步骤 (步骤号,排序号,操作,任务id,类型) values(292,"1","多图识别",[任务id],"Boss按钮")\n'
            f'INSERT INTO 图片组 (任务id,步骤id,编号,图片,名称) values([任务id],[步骤id],"abc","{BMP_1X1}","Boss按钮1")\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "script.txt"
            out = Path(tmp) / "templates"
            source.write_text(script, encoding="gb18030")

            written = export_panda_templates(source, out)

            self.assertEqual(len(written), 1)
            self.assertTrue(written[0].exists())
            self.assertEqual(written[0].suffix, ".bmp")


if __name__ == "__main__":
    unittest.main()
