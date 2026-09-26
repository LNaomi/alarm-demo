"""一键流水线：把「采集 -> 解析 -> 校验 -> 报告」串成一个可复用函数。

测试和外部调用都走这里，CLI 只是薄薄一层参数解析。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from .collector import AlarmSimulator
from .inventory import load_inventory
from .parser import ParseResult, parse_records, read_jsonl
from .report import write_report
from .validator import ValidationResult, validate


@dataclass
class RunResult:
    """一次完整运行的产物。"""

    records: list[dict]
    parsed: ParseResult
    validation: ValidationResult
    report_path: Path | None = None


def run(
    count: int = 200,
    seed: int = 20260926,
    anomaly_rate: float = 0.12,
    duplicate_rate: float = 0.03,
    data: str | Path | None = None,
    inventory: str | Path | None = None,
    output: str | Path | None = None,
    now: datetime | None = None,
) -> RunResult:
    """跑完整流水线。

    data 为空时使用模拟器；output 非空时额外产出 HTML 报告。
    """
    now = now or datetime.now(timezone.utc)

    if data is not None:
        records = read_jsonl(data)
    else:
        records = AlarmSimulator(
            seed=seed, anomaly_rate=anomaly_rate, duplicate_rate=duplicate_rate
        ).generate(count=count, now=now)

    parsed = parse_records(records)
    validation = validate(parsed.alarms, now=now, inventory=load_inventory(inventory))

    report_path = None
    if output is not None:
        report_path = write_report(validation, output, generated_at=now)

    return RunResult(records=records, parsed=parsed, validation=validation, report_path=report_path)


def fixed_now() -> datetime:
    """测试用的固定「当前时间」，避免依赖真实时钟。"""
    return datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def within_window(now: datetime, minutes: int = 30) -> str:
    """相对 now 生成一个落在统计窗口内的 ISO 时间戳。"""
    return (now - timedelta(minutes=minutes)).isoformat()
