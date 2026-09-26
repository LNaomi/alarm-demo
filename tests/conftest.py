"""测试公用夹具。

所有测试都用固定的 NOW，不依赖真实时钟，保证任何一天跑结果一致。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from alarm_monitor.models import Alarm

#: 固定「当前时间」
NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def now() -> datetime:
    return NOW


def make_alarm(**overrides) -> Alarm:
    """构造一条**干净**的告警（网元在台账内、码段与等级一致）。"""
    base = {
        "alarm_id": "ALM-1001-GNB-HZ-0001-000001",
        "ne_id": "GNB-HZ-0001",
        "ne_type": "gNodeB",
        "code": 1001,
        "title": "射频单元链路中断",
        "severity": "critical",
        "raised_at": (NOW - timedelta(minutes=10)).isoformat(),
    }
    base.update(overrides)
    return Alarm(**base)
