"""告警校验规则引擎。

规则是**声明式**的：每条规则一个 id + 中文名 + 严重级别，新增规则只需
在 RULES 里注册并实现对应的检查分支，报告会自动出现新的统计列。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping

from .inventory import NetworkElement, load_inventory
from .models import (
    REQUIRED_FIELDS,
    VALID_SEVERITIES,
    Alarm,
    expected_severity,
    parse_timestamp,
)

#: 告警号格式：ALM-<码>-<网元>-<序号>
ALARM_ID_RE = re.compile(r"^ALM-\d{4}-[A-Z0-9-]+-\d{6}$")

#: 容忍的时钟漂移，超过才算「未来时间戳」
FUTURE_TOLERANCE = timedelta(seconds=60)
#: 超过该窗口视为陈旧告警（历史数据回补）
STALE_WINDOW = timedelta(days=7)

#: 规则注册表：id -> (中文名, 级别)
RULES: dict[str, tuple[str, str]] = {
    "R001": ("必填字段缺失或非法", "error"),
    "R002": ("严重等级取值非法", "error"),
    "R003": ("时间戳无法解析", "error"),
    "R004": ("上报时间为未来时刻", "error"),
    "R005": ("告警时间超出统计窗口", "warning"),
    "R006": ("告警号重复上报", "error"),
    "R007": ("网元不在台账内", "error"),
    "R008": ("告警码与严重等级不匹配", "error"),
    "R009": ("告警号格式不合规", "warning"),
}


@dataclass(frozen=True)
class Violation:
    """一条规则命中记录。"""

    rule: str
    rule_name: str
    level: str  # error | warning
    alarm_id: str
    ne_id: str
    message: str


@dataclass
class ValidationResult:
    alarms: list[Alarm] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    @property
    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.level == "error"]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.level == "warning"]

    @property
    def failed_alarm_ids(self) -> set[str]:
        return {v.alarm_id for v in self.violations if v.alarm_id}

    @property
    def passed_count(self) -> int:
        """完全无命中的告警条数。"""
        return len(self.alarms) - len(self.failed_alarm_ids)

    @property
    def pass_rate(self) -> float:
        if not self.alarms:
            return 1.0
        return self.passed_count / len(self.alarms)

    def severity_distribution(self) -> dict[str, int]:
        counter = Counter(alarm.severity_key for alarm in self.alarms)
        return {key: counter.get(key, 0) for key in (*VALID_SEVERITIES, "unknown")}

    def rule_distribution(self) -> list[dict]:
        counter = Counter((v.rule, v.rule_name, v.level) for v in self.violations)
        return [
            {"rule": rule, "name": name, "level": level, "count": count}
            for (rule, name, level), count in sorted(counter.items())
        ]

    def top_offenders(self, limit: int = 5) -> list[dict]:
        """违规最多的网元 TOP N（解析层丢失 alarm_id 时也能按 ne_id 聚合）。"""
        counter = Counter(v.ne_id or "(未知网元)" for v in self.violations if v.ne_id)
        return [{"ne_id": ne, "count": count} for ne, count in counter.most_common(limit)]

    def summary(self) -> dict:
        return {
            "total_alarms": len(self.alarms),
            "violations": len(self.violations),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "passed": self.passed_count,
            "pass_rate": round(self.pass_rate * 100, 2),
        }


def _violation(rule: str, alarm: Alarm, message: str) -> Violation:
    name, level = RULES[rule]
    return Violation(
        rule=rule,
        rule_name=name,
        level=level,
        alarm_id=alarm.alarm_id,
        ne_id=alarm.ne_id,
        message=message,
    )


def validate_alarm(
    alarm: Alarm,
    now: datetime,
    inventory: Mapping[str, NetworkElement] | None = None,
    seen: set[str] | None = None,
) -> list[Violation]:
    """对单条告警跑全部规则。"""
    found: list[Violation] = []

    # R001 必填字段缺失或非法
    missing: list[str] = []
    for name in REQUIRED_FIELDS:
        value = getattr(alarm, name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    if missing:
        found.append(_violation("R001", alarm, f"缺失或为空的字段：{', '.join(missing)}"))

    # R009 告警号格式
    if alarm.alarm_id and not ALARM_ID_RE.match(alarm.alarm_id):
        found.append(_violation("R009", alarm, f"告警号 {alarm.alarm_id!r} 不符合 ALM-<码>-<网元>-<序号>"))

    # R002 严重等级取值
    key = alarm.severity_key
    if alarm.severity and key == "unknown":
        found.append(_violation("R002", alarm, f"严重等级 {alarm.severity!r} 不在 {sorted(VALID_SEVERITIES)} 内"))

    # R007 网元台账
    if inventory is not None and alarm.ne_id and alarm.ne_id not in inventory:
        found.append(_violation("R007", alarm, f"网元 {alarm.ne_id} 不在台账中"))

    # R003 / R004 / R005 时间戳
    if alarm.raised_at:
        ts = parse_timestamp(alarm.raised_at)
        if ts is None:
            found.append(_violation("R003", alarm, f"时间戳 {alarm.raised_at!r} 无法解析为 ISO8601"))
        elif ts > now + FUTURE_TOLERANCE:
            found.append(_violation("R004", alarm, f"上报时间 {alarm.raised_at} 晚于当前时间 {now.isoformat()}"))
        elif ts < now - STALE_WINDOW:
            found.append(
                _violation("R005", alarm, f"上报时间 {alarm.raised_at} 早于 {STALE_WINDOW.days} 天统计窗口")
            )

    # R008 码段与等级一致性
    expect = expected_severity(alarm.code)
    if expect and key in VALID_SEVERITIES and key != expect:
        found.append(
            _violation("R008", alarm, f"告警码 {alarm.code} 应为 {expect}，实际为 {key}")
        )

    # R006 重复上报
    if alarm.alarm_id and seen is not None:
        if alarm.alarm_id in seen:
            found.append(_violation("R006", alarm, f"告警号 {alarm.alarm_id} 重复"))
        else:
            seen.add(alarm.alarm_id)

    return found


def validate(
    alarms: Iterable[Alarm],
    now: datetime | None = None,
    inventory: Mapping[str, NetworkElement] | None | bool = True,
) -> ValidationResult:
    """对一批告警跑校验。

    inventory:
        True  -> 使用内置台账
        None  -> 跳过网元台账校验（离线单测常用）
        dict  -> 使用指定台账
    """
    now = now or datetime.now(timezone.utc)
    if inventory is True:
        inventory = load_inventory()

    result = ValidationResult()
    seen: set[str] = set()
    for alarm in alarms:
        result.alarms.append(alarm)
        result.violations.extend(validate_alarm(alarm, now=now, inventory=inventory, seen=seen))
    return result
