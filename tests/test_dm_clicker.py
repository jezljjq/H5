import unittest
from pathlib import Path

from h5bot.dm_clicker import (
    DmSoftClicker,
    DmWindowSession,
    _explain_reg_return,
    _normalize_roi,
    _reg_return_message,
    _unpack_find_pic_result,
)


class RecordingDm:
    def __init__(self):
        self.path = ""
        self.set_path_calls = []
        self.find_pic_calls = []

    def SetPath(self, path):
        self.path = path
        self.set_path_calls.append(path)

    def FindPic(self, *args):
        self.find_pic_calls.append(args)
        return 1, 34, 56


class DmClickerTests(unittest.TestCase):
    def test_reg_return_message_explains_admin_required(self):
        self.assertIn("管理员", _reg_return_message("-2"))

    def test_explain_reg_return_appends_human_message(self):
        explained = _explain_reg_return("DM_CLICK_FAIL RegRet -2")

        self.assertIn("DM_CLICK_FAIL RegRet -2", explained)
        self.assertIn("管理员", explained)

    def test_normalize_roi_defaults_to_large_window_area(self):
        self.assertEqual(_normalize_roi(None), (0, 0, 9999, 9999))
        self.assertEqual(_normalize_roi([10, 20, 1, 2]), (1, 2, 10, 20))

    def test_unpack_find_pic_result_accepts_tuple_or_index(self):
        self.assertEqual(_unpack_find_pic_result((0, 34, 620)), (0, 34, 620))
        self.assertEqual(_unpack_find_pic_result(-1), (-1, -1, -1))

    def test_session_find_templates_joins_picture_names_for_single_com_call(self):
        session = DmWindowSession(hwnd=1001, modes=["windows3"])
        session.dm = RecordingDm()
        session.mode = "windows3"
        session.alive = True

        result = session.find_templates([Path("D:/tpl/a.bmp"), Path("D:/tpl/b.bmp")], 0.86, [1, 2, 3, 4])

        self.assertTrue(result.ok)
        self.assertEqual(result.index, 1)
        self.assertEqual((result.x, result.y), (34, 56))
        self.assertEqual(session.dm.path, "D:\\tpl")
        self.assertEqual(session.dm.find_pic_calls[0][4], "a.bmp|b.bmp")

    def test_session_find_templates_reuses_current_path(self):
        session = DmWindowSession(hwnd=1001, modes=["windows3"])
        session.dm = RecordingDm()
        session.mode = "windows3"
        session.alive = True

        session.find_templates([Path("D:/tpl/a.bmp")], 0.86)
        session.find_templates([Path("D:/tpl/b.bmp")], 0.86)

        self.assertEqual(session.dm.set_path_calls, ["D:\\tpl"])

    def test_clicker_reuses_alive_session_for_same_window(self):
        clicker = DmSoftClicker()
        first = DmWindowSession(hwnd=1001, modes=["windows3"])
        first.alive = True
        clicker._sessions[1001] = first

        self.assertIs(clicker._session(1001), first)


if __name__ == "__main__":
    unittest.main()
