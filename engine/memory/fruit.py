"""果摘要生成（B4，ADR-0021 B4.0：枝完结时把枝叶压成结论摘要，树导航优先展示）。

- 触发：DecayMaintenance 判定枝完结后调用（后台，不占对话 TTFT）
- 幂等：枝已有 summary 则跳过；同摘要重复写返回 True 不重写
- 后端链：复用 B3 蒸馏链（role=distill -> extract -> 压缩器免费 -> 主模型兜底），
  runtime 装配注入 backends；全失败记 decision_log，次日 decay 重试
- 预算：摘要 <=150 token（超限截断，标注截断）
"""

from __future__ import annotations

from collections.abc import Callable

from core.backend import Backend
from memory.extract import extract_json_object
from memory.store import MemoryStore

__all__ = ["FruitSummarizer", "FruitSummaryError"]

FRUIT_PROMPT = (
    "你是事件枝的「果」总结器。把一段事件枝的叶子记录压成一段结论摘要，只输出 JSON：\n"
    '{"summary": "不超过 150 token 的第三人称结论摘要（这件事是什么、最终结果/当前结论、关键决策）"}\n'
    "要求：\n"
    "- 只写这枝事件的结论与关键事实，不写过程流水账\n"
    "- 摘要自包含、可独立理解（脱离原文也能读懂）\n"
    "- 只输出 JSON，不要其他文字"
)


class FruitSummaryError(Exception):
    """果摘要生成失败（通道不可用 / 解析失败 / 空摘要）。"""


def _truncate_to_tokens(
    text: str, count_tokens: Callable[[str], int], budget: int
) -> tuple[str, bool]:
    """把摘要截断到预算内（启发式字符窗口收缩）；返回 (text, truncated)。"""
    truncated = False
    while count_tokens(text) > budget and len(text) > 50:
        text = text[: int(len(text) * 0.8)]
        truncated = True
    return text.strip(), truncated


class FruitSummarizer:
    """一轮果摘要：收集枝的叶子 -> LLM（后端链）-> 写入链卡 summary。"""

    def __init__(
        self,
        store: MemoryStore,
        backends: list[Backend],
        *,
        count_tokens: Callable[[str], int] | None = None,
        summary_budget_tokens: int = 150,
        max_children: int = 20,
        max_child_chars: int = 160,
    ) -> None:
        self.store = store
        self.backends = list(backends)
        self.count_tokens = count_tokens or (lambda text: len(text))
        self.summary_budget_tokens = summary_budget_tokens
        self.max_children = max_children
        self.max_child_chars = max_child_chars

    def summarize(self, chain_id: str) -> bool:
        """为指定枝生成果摘要；返回是否已写入（含幂等跳过）。"""
        chain = self.store.read_card(chain_id)
        if chain is None or chain.kind != "chain":
            return False
        if chain.summary.strip():
            return True  # 已有果：幂等跳过
        kids = self.store.all_children_of(chain_id)[: self.max_children]
        if not kids:
            return False  # 空枝无可总结
        lines = [f"事件枝：{chain.title}"]
        for kid in kids:
            snippet = kid.content.replace("\n", " ").strip()[: self.max_child_chars]
            lines.append(f"- [{kid.created_at[:10]}] {kid.title}：{snippet}")
        payload = self._call_llm(lines)
        summary = str(payload.get("summary", "") or "").strip()
        if not summary:
            self.store.log_decision("fruit_failed", f"{chain_id}: 空摘要")
            return False
        summary, truncated = _truncate_to_tokens(
            summary, self.count_tokens, self.summary_budget_tokens
        )
        if truncated:
            summary = f"{summary}（摘要超长已截断）"
        return self.store.set_chain_summary(chain_id, summary)

    def _call_llm(self, lines: list[str]) -> dict:
        """后端链逐个调用并解析 JSON；单后端失败重试一次；全失败记决策日志并抛错。"""
        last: Exception | None = None
        last_raw = ""
        backends = self.backends or []
        for backend in backends:
            for attempt in (0, 1):
                system = FRUIT_PROMPT
                if attempt == 1:
                    system += " 只输出 JSON 对象，不要 markdown 代码块，不要任何解释。"
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": "\n".join(lines)},
                ]
                try:
                    resp = backend.complete(messages, temperature=0.0, max_tokens=256)
                except Exception as exc:  # noqa: BLE001 - 端点不可用（含云端失败）
                    last = exc
                    last_raw = ""
                    continue
                try:
                    return extract_json_object(resp.text)
                except (ValueError, TypeError) as exc:
                    last = exc
                    last_raw = resp.text
                    continue
        self.store.log_decision(
            "fruit_failed",
            f"{lines[0] if lines else '?'}: 全后端失败 {last} | 原始: {last_raw[:120]}",
        )
        raise FruitSummaryError(f"果摘要失败: {last}")
