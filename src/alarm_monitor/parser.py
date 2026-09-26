"""把网元上报的原始记录解析成 Alarm 对象。

解析层是**宽容**的：字段缺失、类型不对都不会抛异常，而是原样保留为
空值，交给 validator 判定。这样一条脏记录也能进入报告，而不是被静默丢弃。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import REQUIRED_FIELDS, Alarm


@dataclass(frozen=True)
class ParseError:
    """无法解析成告警对象的原始记录（例如整行不是对象）。"""

    position: int
    message: str
    raw: Any = None


@dataclass
class ParseResult:
    alarms: list[Alarm] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.alarms) + len(self.errors)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def alarm_from_dict(record: dict[str, Any]) -> Alarm:
    """单条原始记录 -> Alarm。未知字段收进 extra，不丢信息。"""
    if not isinstance(record, dict):
        raise TypeError(f"告警记录必须是对象，实际为 {type(record).__name__}")

    known = set(REQUIRED_FIELDS) | {"cleared", "source"}
    return Alarm(
        alarm_id=_as_str(record.get("alarm_id")),
        ne_id=_as_str(record.get("ne_id")),
        ne_type=_as_str(record.get("ne_type")),
        code=_as_int(record.get("code")),
        title=_as_str(record.get("title")),
        severity=_as_str(record.get("severity")),
        raised_at=_as_str(record.get("raised_at")),
        cleared=_as_bool(record.get("cleared", False)),
        source=_as_str(record.get("source")) or "unknown",
        extra={k: v for k, v in record.items() if k not in known},
    )


def parse_records(records: Iterable[Any]) -> ParseResult:
    """解析一批原始记录。"""
    result = ParseResult()
    for position, record in enumerate(records, start=1):
        try:
            result.alarms.append(alarm_from_dict(record))
        except TypeError as exc:
            result.errors.append(ParseError(position=position, message=str(exc), raw=record))
    return result


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """逐行读取 JSONL 采集文件，空行跳过。"""
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def write_jsonl(records: Sequence[dict[str, Any]], path: str | Path) -> Path:
    """把原始记录写成 JSONL，便于复现与回归测试。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    target.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
    return target
