"""解析层：宽容解析，脏数据不丢。"""

from __future__ import annotations

from alarm_monitor.parser import alarm_from_dict, parse_records


def test_parses_complete_record():
    record = {
        "alarm_id": "ALM-1001-GNB-HZ-0001-000001",
        "ne_id": "GNB-HZ-0001",
        "ne_type": "gNodeB",
        "code": 1001,
        "title": "射频单元链路中断",
        "severity": "critical",
        "raised_at": "2026-09-26T11:50:00+00:00",
        "cleared": False,
        "site": "杭州滨江",
    }
    alarm = alarm_from_dict(record)

    assert alarm.alarm_id == "ALM-1001-GNB-HZ-0001-000001"
    assert alarm.code == 1001
    assert alarm.cleared is False
    assert alarm.extra == {"site": "杭州滨江"}  # 未知字段不丢


def test_code_is_coerced_from_string():
    assert alarm_from_dict({"code": "2001"}).code == 2001
    assert alarm_from_dict({"code": "abc"}).code is None
    assert alarm_from_dict({}).code is None


def test_missing_fields_become_empty_values():
    alarm = alarm_from_dict({"alarm_id": "ALM-1001-GNB-HZ-0001-000001"})

    assert alarm.ne_id == ""
    assert alarm.severity == ""
    assert alarm.raised_at == ""
    assert alarm.code is None


def test_non_dict_record_is_reported_as_parse_error():
    result = parse_records([{"alarm_id": "ALM-1001-GNB-HZ-0001-000001"}, "oops", 42])

    assert len(result.alarms) == 1
    assert len(result.errors) == 2
    assert result.total == 3


def test_severity_key_normalizes_unknown_values():
    assert alarm_from_dict({"severity": "CRITICAL"}).severity_key == "critical"
    assert alarm_from_dict({"severity": "fatal"}).severity_key == "unknown"
    assert alarm_from_dict({}).severity_key == "unknown"
