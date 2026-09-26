"""报告层与整条流水线：能出文件、能转义、能跑通。"""

from __future__ import annotations

from alarm_monitor.__main__ import main
from alarm_monitor.pipeline import run
from alarm_monitor.report import render_html, write_report
from alarm_monitor.validator import validate

from conftest import NOW, make_alarm


def test_render_includes_summary_sections():
    result = validate([make_alarm()], now=NOW, inventory=None)
    html = render_html(result, generated_at=NOW)

    assert "<!DOCTYPE html>" in html
    assert "网元告警采集与校验报告" in html
    assert "采集告警总数" in html
    assert "严重等级分布" in html
    assert "本次采集未发现任何违规项" in html


def test_render_escapes_untrusted_values():
    bad = make_alarm(ne_id="<b>GNB</b>")
    result = validate([bad], now=NOW, inventory={"GNB-HZ-0001": object()})
    html = render_html(result, generated_at=NOW)

    assert "&lt;b&gt;GNB&lt;/b&gt;" in html
    assert "<b>GNB</b>" not in html


def test_render_shows_violation_rows():
    result = validate([make_alarm(severity="fatal")], now=NOW, inventory=None)
    html = render_html(result, generated_at=NOW)

    assert "R002" in html
    assert "严重等级取值非法" in html


def test_write_report_creates_file(tmp_path):
    result = validate([make_alarm()], now=NOW, inventory=None)
    path = write_report(result, tmp_path / "nested" / "report.html", generated_at=NOW)

    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_pipeline_runs_end_to_end(tmp_path):
    outcome = run(count=40, seed=42, output=tmp_path / "report.html", now=NOW)

    assert len(outcome.records) == 40
    assert len(outcome.parsed.alarms) == 40
    assert outcome.report_path is not None
    assert outcome.report_path.exists()
    assert outcome.validation.pass_rate < 1.0  # 默认注入脏数据


def test_cli_returns_zero_on_success(tmp_path, capsys):
    code = main(["--count", "20", "--output", str(tmp_path / "r.html"), "--seed", "1"])

    assert code == 0
    assert "HTML 报告" in capsys.readouterr().out


def test_cli_strict_fails_when_errors_exist(tmp_path):
    code = main(
        ["--count", "20", "--anomaly-rate", "1.0", "--strict",
         "--output", str(tmp_path / "r.html"), "--seed", "1"]
    )

    assert code == 1
