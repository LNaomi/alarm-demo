# alarm-fde-demo · 网元告警采集与自动校验

[![CI](https://github.com/LNaomi/alarm-fde-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/LNaomi/alarm-fde-demo/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![Runtime deps](https://img.shields.io/badge/runtime%20deps-0-brightgreen)

一条可复现的端到端流水线：**模拟网元上报 → 采集/解析 → 规则校验 → HTML 报告**。

用电信领域（基站/OAM）的真实问题做壳，验证的是工程能力：可复现的数据构造、
声明式规则引擎、自动化测试、CI 质量门禁、面向客户的报告产出。

```
网元(模拟)            采集层            解析层           校验层            报告层
AlarmSimulator  →  JSONL 记录  →  Alarm 对象  →  Violation 列表  →  report.html
  (含脏数据注入)      read_jsonl      宽容解析         9 条规则         单文件 HTML
```

## 快速开始

```bash
python3 -m pip install -r requirements.txt   # 只有 pytest，运行期零依赖

make test      # 或 python3 -m pytest
make report    # 生成 reports/report.html
make demo      # 测试 + 出报告
```

直接跑 CLI：

```bash
python3 -m alarm_monitor --count 200 --output reports/report.html
python3 -m alarm_monitor --data data/sample_alarms.jsonl --strict   # 有 error 就退出码 1
```

`--seed` 固定随机种子，**同一个种子永远产出同一批数据**，报告可复现、可对比。

## 目录结构

```
src/alarm_monitor/
├── models.py      告警数据模型、严重等级、码段映射
├── inventory.py   网元台账（内置 + JSON 加载）
├── collector.py   模拟采集器，按比例注入脏数据
├── parser.py      宽容解析，脏数据不丢
├── validator.py   9 条校验规则 + 结果聚合
├── report.py      HTML 报告渲染（零依赖）
├── pipeline.py    一键串起全流程
└── __main__.py    CLI
tests/             33 个用例，覆盖每条规则与整条流水线
data/              网元台账 + 样例采集数据（JSONL）
.github/workflows/ CI：3 个 Python 版本跑测试 + 出报告
```

## 校验规则

| 规则 | 说明 | 级别 |
|---|---|---|
| R001 | 必填字段缺失或非法 | error |
| R002 | 严重等级取值非法 | error |
| R003 | 时间戳无法解析 | error |
| R004 | 上报时间为未来时刻 | error |
| R005 | 告警时间超出 7 天统计窗口 | warning |
| R006 | 告警号重复上报 | error |
| R007 | 网元不在台账内 | error |
| R008 | 告警码段与严重等级不匹配 | error |
| R009 | 告警号格式不合规 | warning |

规则在 `validator.py: RULES` 里**声明式注册**，加一条规则只需注册 id + 实现检查分支，
报告的统计表和测试覆盖率会自动跟上（`test_validator.py::test_every_declared_rule_is_exercised`
会强制新规则必须有用例，防止规则悄悄失效）。

## 几个设计取舍

- **运行期零第三方依赖**：只报告层不引 Jinja2，产出的单文件 HTML 可直接发出去，
  也能当 CI 构建产物下载。依赖越少，交付给客户时踩坑越少。
- **解析层宽容、校验层严格**：解析不抛异常，字段缺失保留为空值交给规则判定，
  这样脏数据能进报告而不是被静默丢弃——运维真正需要看到的正是这些异常。
- **主动注入脏数据**：干净数据下所有规则的命中数都是 0，demo 没有说服力。
  采集器按 12% 比例注入缺字段、等级非法、时间戳穿越、重复上报等异常。
- **阈值参数化**：`--anomaly-rate 0 --strict` 可作为 CI 质量门禁——
  一旦校验逻辑把正常告警误判为错误，流水线立刻失败。

## 简历上怎么写（FDE 版）

- 设计并实现网元告警采集校验流水线（Python，运行期零第三方依赖），
  覆盖采集、解析、9 条业务规则校验与 HTML 报告输出，单次运行处理 200+ 条告警；
- 以固定随机种子 + 脏数据注入构造可复现测试数据，测试覆盖率覆盖全部校验规则，
  通过 GitHub Actions 在 Python 3.11–3.13 上做多版本回归与质量门禁；
- 面向运维场景输出单文件 HTML 报告（等级分布、规则命中统计、违规 TOP 网元、明细），
  可直接作为巡检与故障复盘材料交付。

## 下一步

- [ ] 接入真实数据源：SNMP Trap / Kafka 消费，替换 `collector.py`
- [ ] 告警收敛与抑制：同源告警在时间窗内合并，减少告警风暴
- [ ] 报告加趋势对比：与上一次运行 diff，突出新增/恢复的告警
- [ ] 输出 CSV / JSON 供下游系统消费（`report.iter_alarm_rows` 已预留）
