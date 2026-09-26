"""校验层：每条规则都要有对应的命中用例和「干净数据不误报」用例。"""

from __future__ import annotations

from datetime import timedelta

from alarm_monitor.inventory import load_inventory
from alarm_monitor.validator import RULES, validate, validate_alarm

from conftest import NOW, make_alarm


def rules_of(violations) -> set[str]:
    return {v.rule for v in violations}


def check(alarm, **kwargs):
    """对单条告警跑校验，默认跳过网元台账、不查重。"""
    kwargs.setdefault("inventory", None)
    return validate_alarm(alarm, now=NOW, **kwargs)


def test_clean_alarm_has_no_violation():
    assert check(make_alarm()) == []


def test_every_declared_rule_is_exercised():
    """RULES 里注册的规则必须都在本文件有用例覆盖，防止规则悄悄失效。"""
    covered = {"R001", "R002", "R003", "R004", "R005", "R006", "R007", "R008", "R009"}
    assert covered == set(RULES)


def test_r001_missing_required_field():
    violations = check(make_alarm(severity=""))

    assert "R001" in rules_of(violations)
    assert "severity" in violations[0].message


def test_r002_invalid_severity():
    violations = check(make_alarm(severity="fatal"))

    assert "R002" in rules_of(violations)


def test_r003_unparsable_timestamp():
    violations = check(make_alarm(raised_at="昨天下午三点"))

    assert "R003" in rules_of(violations)


def test_r004_future_timestamp():
    violations = check(make_alarm(raised_at=(NOW + timedelta(hours=2)).isoformat()))

    assert "R004" in rules_of(violations)


def test_r005_stale_timestamp_is_warning():
    violations = check(make_alarm(raised_at=(NOW - timedelta(days=20)).isoformat()))
    stale = [v for v in violations if v.rule == "R005"]

    assert stale and stale[0].level == "warning"


def test_r006_duplicate_alarm_id():
    alarm = make_alarm()
    seen = {alarm.alarm_id}

    violations = validate_alarm(alarm, now=NOW, inventory=None, seen=seen)

    assert "R006" in rules_of(violations)


def test_r007_unknown_network_element():
    inventory = load_inventory()

    violations = validate_alarm(make_alarm(ne_id="GNB-HZ-9999"), now=NOW, inventory=inventory, seen=set())

    assert "R007" in rules_of(violations)


def test_r008_code_severity_mismatch():
    violations = check(make_alarm(code=1001, severity="minor"))

    assert "R008" in rules_of(violations)
    assert "critical" in violations[0].message


def test_r009_malformed_alarm_id():
    violations = check(make_alarm(alarm_id="X-1001"))

    assert "R009" in rules_of(violations)


def test_batch_validate_aggregates_duplicates_and_summary():
    alarm = make_alarm()
    result = validate([alarm, alarm, make_alarm(alarm_id="ALM-2001-BTS-HZ-0101-000002",
                                                ne_id="BTS-HZ-0101", ne_type="BTS",
                                                code=2001, severity="major",
                                                title="小区退服")],
                      now=NOW)

    assert result.passed_count == 2          # 3 条里第 2 条是重复的
    assert len(result.errors) == 1           # 一条 R006
    assert result.summary()["total_alarms"] == 3
    assert 0 < result.pass_rate < 1


def test_empty_input_has_full_pass_rate():
    result = validate([], now=NOW)

    assert result.pass_rate == 1.0
    assert result.violations == []


def test_severity_distribution_counts_unknown():
    result = validate([make_alarm(), make_alarm(alarm_id="ALM-4001-TN-HZ-0201-00000X",
                                                ne_id="TN-HZ-0201", ne_type="Transport",
                                                code=4001, severity="fatal",
                                                title="配置变更未同步")],
                      now=NOW, inventory=None)

    distribution = result.severity_distribution()

    assert distribution["critical"] == 1
    assert distribution["unknown"] == 1
