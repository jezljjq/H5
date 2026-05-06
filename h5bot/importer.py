from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PandaImage:
    code: str
    name: str
    data: str


@dataclass(slots=True)
class PandaStep:
    step_no: str
    name: str
    operation: str
    similarity: float
    roi: list[int] | None = None
    found_action: str = ""
    not_found_action: str = ""
    found_next: str = ""
    not_found_next: str = ""
    images: list[PandaImage] = field(default_factory=list)


@dataclass(slots=True)
class PandaScript:
    steps: list[PandaStep] = field(default_factory=list)


def parse_panda_script(text: str) -> PandaScript:
    script = PandaScript()
    current: PandaStep | None = None
    for line in text.splitlines():
        if line.startswith("INSERT INTO 步骤 "):
            row = _parse_insert(line, "步骤")
            if not row:
                continue
            current = PandaStep(
                step_no=row.get("步骤号", ""),
                name=row.get("类型", "") or row.get("图片识别_名称", "") or row.get("操作", ""),
                operation=row.get("操作", ""),
                similarity=_similarity(row.get("图片识别_相似度", "")),
                roi=_roi(row),
                found_action=row.get("图片识别_找到后", ""),
                not_found_action=row.get("图片识别_找不到", ""),
                found_next=row.get("图片识别_找到跳步骤", ""),
                not_found_next=row.get("图片识别_找不到跳步骤", ""),
            )
            script.steps.append(current)
        elif line.startswith("INSERT INTO 图片组") and current is not None:
            image = _parse_image_insert(line)
            if image:
                current.images.append(image)
    return script


def export_panda_templates(source: Path, output_dir: Path) -> list[Path]:
    text = source.read_text(encoding="gb18030", errors="replace")
    parsed = parse_panda_script(text)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    used: set[str] = set()
    for step in parsed.steps:
        for image in step.images:
            name = _safe_filename(image.name or image.code)
            filename = f"{name}.bmp"
            counter = 2
            while filename.lower() in used:
                filename = f"{name}_{counter}.bmp"
                counter += 1
            used.add(filename.lower())
            path = output_dir / filename
            path.write_bytes(base64.b64decode(image.data))
            written.append(path)
    return written


def _parse_insert(line: str, table: str) -> dict[str, str] | None:
    match = re.search(rf"INSERT INTO {table} \((.*?)\) values\((.*)\)$", line)
    if not match:
        return None
    keys = _split_csv_like(match.group(1))
    values = _split_csv_like(match.group(2))
    return {key: value for key, value in zip(keys, values)}


def _parse_image_insert(line: str) -> PandaImage | None:
    match = re.search(r'values\(\[任务id\],\[步骤id\],"(.*?)","(.*?)","(.*?)"\)$', line)
    if not match:
        return None
    return PandaImage(code=match.group(1), data=match.group(2), name=match.group(3))


def _split_csv_like(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    for char in value:
        if char == '"':
            in_quote = not in_quote
            continue
        if char == "," and not in_quote:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def _roi(row: dict[str, str]) -> list[int] | None:
    values = [row.get("图片识别_范围左x", ""), row.get("图片识别_范围左y", ""), row.get("图片识别_范围右x", ""), row.get("图片识别_范围右y", "")]
    if not all(values):
        return None
    try:
        return [int(value) for value in values]
    except ValueError:
        return None


def _similarity(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        return 0.0
    return number / 100 if number > 1 else number


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip()
    return cleaned or "template"
