from __future__ import annotations


def parse_roi(value: str | list[int] | tuple[int, int, int, int] | None) -> list[int] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        if not parts:
            return None
        if len(parts) != 4:
            raise ValueError("ROI 格式应为 x1,y1,x2,y2")
        return [int(part) for part in parts]
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [int(part) for part in value]
    raise ValueError("ROI 格式应为 x1,y1,x2,y2")


def format_roi(roi: list[int] | tuple[int, int, int, int] | None) -> str:
    if not roi:
        return ""
    return ",".join(str(int(part)) for part in roi)


def clamp_roi(roi: list[int] | tuple[int, int, int, int] | None, width: int, height: int) -> list[int] | None:
    parsed = parse_roi(roi)
    if not parsed:
        return None
    x1, y1, x2, y2 = parsed
    left, right = sorted((max(0, x1), max(0, x2)))
    top, bottom = sorted((max(0, y1), max(0, y2)))
    right = min(int(width), right)
    bottom = min(int(height), bottom)
    if right <= left or bottom <= top:
        raise ValueError("ROI 区域无效")
    return [left, top, right, bottom]


def auto_roi_from_match(x: int, y: int, width: int, height: int, window_width: int, window_height: int) -> list[int]:
    margin_x = int(max(30, width * 1.5))
    margin_y = int(max(30, height * 1.5))
    return [
        max(0, int(x) - margin_x),
        max(0, int(y) - margin_y),
        min(int(window_width), int(x) + int(width) + margin_x),
        min(int(window_height), int(y) + int(height) + margin_y),
    ]
