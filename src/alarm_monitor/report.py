"""把校验结果渲染成 HTML 报告。

不引入 Jinja2 —— 运行期保持零第三方依赖，直接拼字符串 + 内联 CSS，
产出的单文件 HTML 可以直接邮件/IM 发出去，也能在 CI 里当构建产物下载。
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from .models import SEVERITY_LABEL_CN
from .validator import ValidationResult, Violation

DEFAULT_TITLE = "网元告警采集与校验报告"

_CSS = """
:root {
  --bg: #f5f6f8;
  --card: #ffffff;
  --border: #e3e6ea;
  --text: #1c1f23;
  --muted: #6b7280;
  --critical: #c62828;
  --major: #ef6c00;
  --minor: #f9a825;
  --warning: #0277bd;
  --unknown: #9e9e9e;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 24px 56px;
  background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 14px; line-height: 1.6;
}
.wrap { max-width: 1080px; margin: 0 auto; }
h1 { font-size: 24px; margin: 0 0 4px; }
.sub { color: var(--muted); font-size: 13px; margin-bottom: 24px; }
h2 { font-size: 16px; margin: 32px 0 12px; padding-left: 10px; border-left: 3px solid var(--warning); }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 20px; margin-bottom: 16px;
}
.cards { display: flex; gap: 12px; flex-wrap: wrap; }
.cards .card { flex: 1 1 150px; margin-bottom: 0; }
.metric { font-size: 28px; font-weight: 600; letter-spacing: -0.5px; }
.metric-label { color: var(--muted); font-size: 12px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.bar-name { width: 96px; color: var(--muted); }
.bar-track { flex: 1; background: #eef0f3; border-radius: 4px; height: 10px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; }
.bar-value { width: 56px; text-align: right; font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 13px; }
th { color: var(--muted); font-weight: 500; background: #fafbfc; }
td.num { font-variant-numeric: tabular-nums; }
.tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; color: #fff; }
.tag.error { background: var(--critical); }
.tag.warning { background: var(--major); }
.tag.ok { background: #2e7d32; }
.empty { color: var(--muted); padding: 12px 0; }
code { background: #f2f4f7; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
footer { margin-top: 32px; color: var(--muted); font-size: 12px; text-align: center; }
"""

_SEVERITY_COLOR = {
    "critical": "var(--critical)",
    "major": "var(--major)",
    "minor": "var(--minor)",
    "warning": "var(--warning)",
    "unknown": "var(--unknown)",
}


def _violation_rows(violations: Sequence[Violation], limit: int) -> str:
    if not violations:
        return '<p class="empty">本次采集未发现任何违规项。</p>'
    rows = []
    for item in violations[:limit]:
        level_cls = "error" if item.level == "error" else "warning"
        rows.append(
            "<tr>"
            f"<td><code>{escape(item.rule)}</code></td>"
            f"<td>{escape(item.rule_name)}</td>"
            f'<td><span class="tag {level_cls}">{escape(item.level)}</span></td>'
            f"<td><code>{escape(item.alarm_id or '-')}</code></td>"
            f"<td>{escape(item.ne_id or '-')}</td>"
            f"<td>{escape(item.message)}</td>"
            "</tr>"
        )
    extra = ""
    if len(violations) > limit:
        extra = f'<p class="empty">另有 {len(violations) - limit} 条未展示（超出单页上限 {limit}）。</p>'
    return (
        "<table><thead><tr><th>规则</th><th>规则说明</th><th>级别</th>"
        "<th>告警号</th><th>网元</th><th>详情</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>{extra}"
    )


def render_html(
    result: ValidationResult,
    title: str = DEFAULT_TITLE,
    generated_at: datetime | None = None,
    max_rows: int = 200,
) -> str:
    """渲染完整 HTML 报告字符串。"""
    generated_at = generated_at or datetime.now(timezone.utc)
    summary = result.summary()
    severity = result.severity_distribution()
    max_sev = max(severity.values()) or 1

    bars = []
    for key, count in severity.items():
        width = int(count / max_sev * 100)
        label = SEVERITY_LABEL_CN.get(key, key)
        bars.append(
            '<div class="bar-row">'
            f'<span class="bar-name">{escape(key)} · {escape(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{width}%;'
            f'background:{_SEVERITY_COLOR.get(key, "var(--unknown)")}"></span></span>'
            f'<span class="bar-value">{count}</span>'
            "</div>"
        )

    rule_rows = []
    for item in result.rule_distribution():
        level_cls = "error" if item["level"] == "error" else "warning"
        rule_rows.append(
            "<tr>"
            f"<td><code>{escape(item['rule'])}</code></td>"
            f"<td>{escape(item['name'])}</td>"
            f'<td><span class="tag {level_cls}">{escape(item["level"])}</span></td>'
            f'<td class="num">{item["count"]}</td>'
            "</tr>"
        )
    if not rule_rows:
        rule_rows.append('<tr><td colspan="4" class="empty">无命中</td></tr>')

    top_rows = []
    for item in result.top_offenders():
        top_rows.append(
            f"<tr><td><code>{escape(item['ne_id'])}</code></td>"
            f'<td class="num">{item["count"]}</td></tr>'
        )
    if not top_rows:
        top_rows.append('<tr><td colspan="2" class="empty">无</td></tr>')

    verdict_cls = "ok" if not result.errors else "error"
    verdict = "通过" if not result.errors else f"发现 {len(result.errors)} 项错误"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>{escape(title)}</h1>
  <div class="sub">生成时间：{escape(generated_at.strftime('%Y-%m-%d %H:%M:%S %Z') or generated_at.isoformat())}</div>

  <div class="cards">
    <div class="card"><div class="metric">{summary['total_alarms']}</div><div class="metric-label">采集告警总数</div></div>
    <div class="card"><div class="metric">{summary['passed']}</div><div class="metric-label">校验通过</div></div>
    <div class="card"><div class="metric">{summary['errors']}</div><div class="metric-label">错误（阻断）</div></div>
    <div class="card"><div class="metric">{summary['warnings']}</div><div class="metric-label">警告（提示）</div></div>
    <div class="card"><div class="metric">{summary['pass_rate']}%</div><div class="metric-label">通过率</div></div>
  </div>

  <h2>结论</h2>
  <div class="card">
    <span class="tag {verdict_cls}">{escape(verdict)}</span>
    &nbsp;共 {summary['total_alarms']} 条告警，命中 {summary['violations']} 条规则，
    涉及 {len(result.failed_alarm_ids)} 条异常告警。
  </div>

  <h2>严重等级分布</h2>
  <div class="card">{''.join(bars)}</div>

  <h2>规则命中统计</h2>
  <div class="card">
    <table><thead><tr><th>规则</th><th>说明</th><th>级别</th><th>命中数</th></tr></thead>
    <tbody>{''.join(rule_rows)}</tbody></table>
  </div>

  <h2>违规最多网元 TOP 5</h2>
  <div class="card">
    <table><thead><tr><th>网元</th><th>违规数</th></tr></thead>
    <tbody>{''.join(top_rows)}</tbody></table>
  </div>

  <h2>违规明细</h2>
  <div class="card">{_violation_rows(result.violations, max_rows)}</div>

  <footer>由 alarm-fde-demo 自动生成 · 采集→解析→校验→报告 全链路可复现</footer>
</div>
</body>
</html>
"""


def write_report(
    result: ValidationResult,
    path: str | Path,
    title: str = DEFAULT_TITLE,
    generated_at: datetime | None = None,
    max_rows: int = 200,
) -> Path:
    """渲染并写入 HTML 文件，返回路径。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_html(result, title=title, generated_at=generated_at, max_rows=max_rows),
        encoding="utf-8",
    )
    return target


def iter_alarm_rows(alarms: Iterable) -> list[dict]:
    """导出告警明细（供 CSV / 其他消费方使用）。"""
    return [alarm.to_dict() for alarm in alarms]
