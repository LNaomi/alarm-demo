"""模拟网元告警采集器。

真实链路里这一层是 SNMP Trap / Kafka / 北向接口订阅；这里用一个
**可复现**的模拟器替代：固定随机种子 -> 固定数据，测试才能稳定断言。

模拟器会按比例注入脏数据（缺字段、等级非法、时间戳穿越、重复上报、
码段与等级不一致、未知网元），否则校验规则永远命中 0 条，演示没有说服力。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .inventory import DEFAULT_INVENTORY, NetworkElement
from .models import SEVERITY_ORDER

#: 告警码 -> (标题, 严重等级) 目录，码段与 models.CODE_SEVERITY_HINT 对应
ALARM_CATALOG: tuple[tuple[int, str, str], ...] = (
    (1001, "射频单元链路中断", "critical"),
    (1002, "主控板心跳丢失", "critical"),
    (1003, "电源模块故障", "critical"),
    (2001, "小区退服", "major"),
    (2002, "传输误码率超阈值", "major"),
    (2003, "S1 链路拥塞", "major"),
    (3001, "风扇转速异常", "minor"),
    (3002, "光模块收光功率偏低", "minor"),
    (3003, "CPU 使用率持续偏高", "minor"),
    (4001, "配置变更未同步", "warning"),
    (4002, "License 即将到期", "warning"),
    (4003, "时钟同步偏移告警", "warning"),
)

_CORRUPTIONS = (
    "missing_field",
    "empty_field",
    "bad_severity",
    "future_ts",
    "stale_ts",
    "severity_mismatch",
    "unknown_ne",
    "bad_id",
)


class AlarmSimulator:
    """生成一批带脏数据的模拟告警上报记录。"""

    def __init__(
        self,
        seed: int = 20260926,
        inventory: Sequence[NetworkElement] | None = None,
        anomaly_rate: float = 0.12,
        duplicate_rate: float = 0.03,
    ) -> None:
        self._rng = random.Random(seed)
        self.inventory: tuple[NetworkElement, ...] = tuple(inventory or DEFAULT_INVENTORY)
        self.anomaly_rate = anomaly_rate
        self.duplicate_rate = duplicate_rate
        self._seq = 0

    def _next_alarm_id(self, code: int, ne_id: str) -> str:
        self._seq += 1
        return f"ALM-{code}-{ne_id}-{self._seq:06d}"

    def generate(self, count: int = 200, now: datetime | None = None) -> list[dict]:
        """生成 count 条原始上报记录（dict 形式，尚未解析）。"""
        now = now or datetime.now(timezone.utc)
        records: list[dict] = []
        for _ in range(count):
            ne = self._rng.choice(self.inventory)
            code, title, severity = self._rng.choice(ALARM_CATALOG)
            raised_at = now - timedelta(minutes=self._rng.randint(0, 60 * 24 * 6))
            record = {
                "alarm_id": self._next_alarm_id(code, ne.ne_id),
                "ne_id": ne.ne_id,
                "ne_type": ne.ne_type,
                "site": ne.site,
                "code": code,
                "title": title,
                "severity": severity,
                "raised_at": raised_at.isoformat(),
                "cleared": self._rng.random() < 0.2,
                "source": "simulator",
            }
            record = self._corrupt(record, now)
            # 模拟网元重传导致的重复上报
            if records and self._rng.random() < self.duplicate_rate:
                record["alarm_id"] = records[-1]["alarm_id"]
            records.append(record)
        return records

    def _corrupt(self, record: dict, now: datetime) -> dict:
        """按 anomaly_rate 注入一类脏数据。"""
        if self._rng.random() >= self.anomaly_rate:
            return record

        kind = self._rng.choice(_CORRUPTIONS)
        if kind == "missing_field":
            record.pop(self._rng.choice(["ne_type", "title", "severity", "raised_at"]), None)
        elif kind == "empty_field":
            record[self._rng.choice(["title", "ne_id", "alarm_id"])] = ""
        elif kind == "bad_severity":
            record["severity"] = self._rng.choice(["fatal", "warn", "severe", ""])
        elif kind == "future_ts":
            offset = timedelta(minutes=self._rng.randint(5, 600))
            record["raised_at"] = (now + offset).isoformat()
        elif kind == "stale_ts":
            record["raised_at"] = (now - timedelta(days=self._rng.randint(8, 40))).isoformat()
        elif kind == "severity_mismatch":
            record["severity"] = self._rng.choice(
                [s for s in SEVERITY_ORDER if s != record["severity"]]
            )
        elif kind == "unknown_ne":
            record["ne_id"] = "GNB-HZ-9999"  # 台账里不存在的网元
        elif kind == "bad_id":
            record["alarm_id"] = f"X-{record['code']}"
        return record


def collect(
    count: int = 200,
    seed: int = 20260926,
    now: datetime | None = None,
    anomaly_rate: float = 0.12,
    duplicate_rate: float = 0.03,
) -> list[dict]:
    """便捷入口：直接拿到一批模拟上报记录。"""
    return AlarmSimulator(
        seed=seed, anomaly_rate=anomaly_rate, duplicate_rate=duplicate_rate
    ).generate(count=count, now=now)
