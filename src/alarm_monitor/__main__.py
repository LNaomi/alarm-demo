"""命令行入口：采集 -> 解析 -> 校验 -> 出报告。

    python -m alarm_monitor --count 200 --output reports/report.html
    python -m alarm_monitor --data data/sample_alarms.jsonl --strict
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .collector import AlarmSimulator
from .inventory import load_inventory
from .parser import parse_records, read_jsonl, write_jsonl
from .report import DEFAULT_TITLE, write_report
from .validator import validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alarm-monitor",
        description="网元告警采集与自动校验 Demo",
    )
    parser.add_argument("--count", type=int, default=200, help="模拟采集的告警条数（默认 200）")
    parser.add_argument("--seed", type=int, default=20260926, help="随机种子，保证可复现")
    parser.add_argument("--anomaly-rate", type=float, default=0.12, help="脏数据注入比例")
    parser.add_argument(
        "--duplicate-rate", type=float, default=0.03, help="重复上报注入比例（模拟网元重传）"
    )
    parser.add_argument("--data", type=Path, default=None, help="从 JSONL 文件读取真实采集数据")
    parser.add_argument("--inventory", type=Path, default=None, help="网元台账 JSON 文件路径")
    parser.add_argument("--dump-raw", type=Path, default=None, help="把采集到的原始数据存成 JSONL")
    parser.add_argument("--output", type=Path, default=Path("reports/report.html"), help="HTML 报告输出路径")
    parser.add_argument("--max-rows", type=int, default=200, help="报告中违规明细最大展示条数")
    parser.add_argument("--strict", action="store_true", help="存在 error 级违规时以退出码 1 结束")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)

    # 1) 采集
    if args.data is not None:
        records = read_jsonl(args.data)
        origin = f"文件 {args.data}"
    else:
        records = AlarmSimulator(
            seed=args.seed,
            anomaly_rate=args.anomaly_rate,
            duplicate_rate=args.duplicate_rate,
        ).generate(count=args.count, now=now)
        origin = f"模拟器 seed={args.seed}"
    if args.dump_raw is not None:
        write_jsonl(records, args.dump_raw)

    # 2) 解析
    parsed = parse_records(records)

    # 3) 校验
    inventory = load_inventory(args.inventory)
    result = validate(parsed.alarms, now=now, inventory=inventory)

    # 4) 报告
    output = write_report(result, args.output, generated_at=now, max_rows=args.max_rows)

    summary = result.summary()
    print(f"采集来源：{origin}")
    print(f"原始记录：{len(records)} 条，成功解析 {len(parsed.alarms)} 条，解析失败 {len(parsed.errors)} 条")
    print(
        f"校验结果：通过 {summary['passed']} / {summary['total_alarms']} "
        f"（通过率 {summary['pass_rate']}%），error {summary['errors']} 条，warning {summary['warnings']} 条"
    )
    for item in result.rule_distribution():
        print(f"  - {item['rule']} {item['name']} [{item['level']}] x{item['count']}")
    print(f"HTML 报告：{output}")

    if args.strict and result.errors:
        print("strict 模式：存在 error 级违规，返回退出码 1", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
