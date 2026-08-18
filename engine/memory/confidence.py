"""置信度校准（证据驱动，零 LLM）：LLM 只输出证据标签，真值由可验证机制裁决（§9.7）。

设计：
- LLM 自评 0-1 无校准依据（"模型觉得它记得对不对"）→ 降级为排序特征；
- 准入改为证据驱动：directive/explicit 自动固化，inferred 需佐证，uncertain 一律待审；
- confidence 成为可复现的计算字段：base(证据) + 修正(来源/佐证/指令)，全程 decision_log 审计；
- 用户反馈是最高真值：纠正 → 证据降级；确认 → 佐证 +1。
"""

EVIDENCE_BASE = {
    "directive": 0.95,   # 用户明确要求记住（"记住：..."）
    "explicit": 0.90,    # 用户亲口明确陈述
    "inferred": 0.60,    # 分身推断 / 从上下文推导
    "uncertain": 0.35,   # 不确定、可能记错
    "approved": 1.00,    # 人工审批固化（promote_lesson）
}

# 确定性指令触发词（与 rules.py 的"直接记忆指令"同源，双保险）
DIRECTIVE_TRIGGERS = ("记住", "记下", "记牢", "别忘了", "别忘")


def base_score(evidence: str) -> float:
    """证据标签 → 基础置信（未知标签一律按 uncertain 处理）。"""
    return EVIDENCE_BASE.get((evidence or "").strip(), 0.35)


def auto_commit(
    evidence: str,
    *,
    source_part: str = "",
    corroborated: bool = False,
    directive_hit: bool = False,
) -> bool:
    """证据驱动的准入阀门：不再用裸 confidence 0.5 切。"""
    evidence = (evidence or "").strip()
    if directive_hit or evidence in ("directive", "explicit", "approved"):
        return True
    if evidence == "inferred":
        return source_part.startswith("tool:") or corroborated
    return False


def compute_confidence(
    evidence: str,
    *,
    source_part: str = "",
    corroborated: bool = False,
    directive_hit: bool = False,
) -> float:
    """可复现置信度：base(证据) + 确定性修正，上限 0.95（人工审批 1.0 除外）。"""
    evidence = (evidence or "").strip()
    score = EVIDENCE_BASE.get(evidence, 0.35)
    if directive_hit:
        score = max(score, 0.90)
    if source_part == "user":
        score += 0.05
    elif source_part and not source_part.startswith("tool:") and not directive_hit:
        score -= 0.05  # assistant 推断折价（用户指令命中时不折价）
    if corroborated:
        score += 0.10
    if evidence == "approved":
        return 1.00
    return round(min(0.95, max(0.10, score)), 2)
