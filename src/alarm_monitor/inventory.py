"""网元（Network Element）台账。

真实环境里这份台账来自 CMDB / 网管系统导出，这里内置一份杭州区域的
模拟清单，同时支持从 JSON 文件加载，方便对接外部数据源。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class NetworkElement:
    """一个被管网元。"""

    ne_id: str
    ne_type: str
    site: str


DEFAULT_INVENTORY: tuple[NetworkElement, ...] = (
    NetworkElement("GNB-HZ-0001", "gNodeB", "杭州滨江"),
    NetworkElement("GNB-HZ-0002", "gNodeB", "杭州西湖"),
    NetworkElement("GNB-HZ-0003", "gNodeB", "杭州未来科技城"),
    NetworkElement("BTS-HZ-0101", "BTS", "杭州萧山"),
    NetworkElement("BTS-HZ-0102", "BTS", "杭州余杭"),
    NetworkElement("TN-HZ-0201", "Transport", "杭州城域网核心"),
    NetworkElement("TN-HZ-0202", "Transport", "杭州城域网汇聚"),
    NetworkElement("OAM-HZ-9001", "OAM", "杭州网管中心"),
)


def _from_dict(raw: dict) -> NetworkElement:
    return NetworkElement(
        ne_id=str(raw["ne_id"]),
        ne_type=str(raw.get("ne_type", "unknown")),
        site=str(raw.get("site", "unknown")),
    )


def load_inventory(path: str | Path | None = None) -> dict[str, NetworkElement]:
    """返回 {ne_id: NetworkElement}。

    path 为空时使用内置台账；传入 JSON 文件则从外部加载（覆盖内置清单）。
    """
    items: Iterable[NetworkElement] = DEFAULT_INVENTORY
    if path is not None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(raw, dict):  # 兼容 {"elements": [...]} 形式
            raw = raw.get("elements", [])
        items = [_from_dict(item) for item in raw]
    return {item.ne_id: item for item in items}
