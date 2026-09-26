"""采集层：可复现 + 能造出脏数据，否则校验就是摆设。"""

from __future__ import annotations

from alarm_monitor.collector import AlarmSimulator, collect
from alarm_monitor.models import REQUIRED_FIELDS
from alarm_monitor.parser import parse_records
from alarm_monitor.validator import validate

from conftest import NOW


def test_same_seed_is_reproducible():
    assert collect(count=50, seed=7, now=NOW) == collect(count=50, seed=7, now=NOW)


def test_different_seed_differs():
    assert collect(count=50, seed=7, now=NOW) != collect(count=50, seed=8, now=NOW)


def test_generates_requested_count():
    assert len(collect(count=30, now=NOW)) == 30


def test_records_carry_required_fields_when_clean():
    clean = AlarmSimulator(seed=3, anomaly_rate=0.0, duplicate_rate=0.0).generate(20, now=NOW)

    assert all(set(REQUIRED_FIELDS) <= set(record) for record in clean)


def test_zero_anomaly_rate_produces_no_violation():
    clean = AlarmSimulator(seed=3, anomaly_rate=0.0, duplicate_rate=0.0).generate(50, now=NOW)
    result = validate(parse_records(clean).alarms, now=NOW)

    assert result.violations == []
    assert result.pass_rate == 1.0


def test_full_anomaly_rate_produces_violations():
    dirty = AlarmSimulator(seed=3, anomaly_rate=1.0, duplicate_rate=0.5).generate(50, now=NOW)
    result = validate(parse_records(dirty).alarms, now=NOW)

    assert result.violations
    assert len(result.rule_distribution()) >= 3  # 命中多类规则


def test_duplicate_injection_is_detectable():
    records = AlarmSimulator(seed=11, anomaly_rate=0.0, duplicate_rate=1.0).generate(10, now=NOW)
    result = validate(parse_records(records).alarms, now=NOW)

    assert any(v.rule == "R006" for v in result.violations)
