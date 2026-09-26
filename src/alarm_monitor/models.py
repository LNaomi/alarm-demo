"""告警数据模型与领域常量。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

#: 严重等级（从高到低），与运营商告警惯例一致
SEVERITY_ORDER: tuple[str, ...] = ("critical", "major", "minor", "warning")
VALID_SEVERITIES: frozenset[str] = frozenset(SEVERITY_ORDER)

SEVERITY_LABEL_CN: dict[str, str] = {
    "critical": "紧急",
    "major": "重要",
    "minor": "次要",
    "warning": "提示",
    "unknown": "未知",
}

#: 告警码段 -> 期望严重等级，用于「码段与等级一致性」校验
CODE_SEVERITY_HINT: dict[tuple[int, int], str] = {
    (1000, 1999): "critical",  # 硬件故障 / 链路中断
    (2000, 2999): "major",     # 业务受损
    (3000, 3999): "minor",     # 性能劣化
    (4000, 4999): "warning",   # 配置 /  license 类提示
}

#: 上报记录必须携带的字段
REQUIRED_FIELDS: tuple[str, ...] = (
    "alarm_id",
    "ne_id",
    "ne_type",
    "code",
    "title",
    "severity",
    "raised_at",
)


def expected_severity(code: int | None) -> str | None:
    """根据告警码段返回期望的严重等级；未知码段返回 None。"""
    if code is None:
        return None
    for (low, high), severity in CODE_SEVERITY_HINT.items():
        if low <= code <= high:
            return severity
    return None


def parse_timestamp(value: str) -> datetime | None:
    """解析 ISO8601 时间串，兼容 `Z` 后缀与无时区写法。

    解析失败返回 None，由校验层判定为非法时间戳。
    """
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class Alarm:
    """一条网元告警记录。

    字段可能为 None / 空串 —— 采集侧不做清洗，脏数据原样带入，
    由 validator 统一判定，这样校验规则才有真实的命中样本。
    """

    alarm_id: str = ""
    ne_id: str = ""
    ne_type: str = ""
    code: int | None = None
    title: str = ""
    severity: str = ""
    raised_at: str = ""
    cleared: bool = False
    source: str = "unknown"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def severity_key(self) -> str:
        """归一化后的严重等级键；非法或缺失时为 unknown。"""
        key = (self.severity or "").strip().lower()
        return key if key in VALID_SEVERITIES else "unknown"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        return data
