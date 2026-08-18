"""写入管道（V2 memory/extract.py 移植 + V3 增强：事件溯源 / bus 可选）。

runs → LLM 提取 → 事件卡 + 事件链（P0 记忆树）。
- 低置信（<0.5）→ lesson_pending（待人工审批）；高置信 → event 卡；
- 幂等：同一 run 状态机 staged→extracting→done/failed，重复处理由 store 状态保证；
- 失败/禁用：run 留在 runs 表（原文不丢），不崩溃；
- V3 独有：每次提取成功发 MEMORY_EXTRACT 事件（挂事件树，可溯源到 turn）。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import threading
import time
from typing import Protocol

from dataclasses import dataclass, field, replace

from core.backend import Backend
from core.events import Event, EventBus, EventType
from core.types import IntentTier
from memory.confidence import DIRECTIVE_TRIGGERS, auto_commit, base_score, compute_confidence
from memory.guard import extract_priority, should_extract
from memory.models import MemoryCard, MemoryRun, WikiEntry
from memory.strategy import ExtractStrategy
from memory.store import MemoryStore, now_iso
from memory.tokenize import tokenize
from memory.wiki import WikiStore, WikiWritePipeline, wiki_id

__all__ = ["LLMExtractor", "MemoryWritePipeline", "ExtractionResult", "ExtractError"]

_EXTRACT_PROMPT = (
    "你是记忆提取器，不是对话助手。从一段对话中提取值得长期记住的事实，只输出 JSON，不回复用户：\n"
    '{"cards": [{"title": "一句话标题", "content": "事实描述（第三人称、可独立理解）", '
    '"evidence": "explicit|inferred|uncertain|directive", "chain": "事件链标题（无则空串）", "entities": ["实体1", "实体2"], '
    '"supersedes": "（可选）本条事实替代的同主题旧事实一句话标题，无则空串", '
    '"ended": false, "source_part": "assistant"}], '
    '"wiki": [{"kind": "concept|spec|tutorial", "title": "标题", "content": "正文", '
    '"tags": ["标签"], "entities": ["实体"], "aliases": ["同义说法"], '
    '"spec_id": "（kind=spec 必填，如 GB-50137-2011）", '
    '"level": "national|province|city|county|township", '
    '"evidence": "explicit|inferred|uncertain"}]}\n'
    "四类永久事实（先判类，再决定字段）：\n"
    "① 用户偏好（喜欢/不喜欢/习惯）→ evidence=explicit；归属 chain（如\"生活习惯\"）\n"
    "② 硬性规则/约束（账号/端口/截止日/禁用项/安全要求）→ evidence=directive（若用户明确要求记住）"
    "或 explicit；这是永不衰减的关键事实，entities 必填（如端口号/项目名）\n"
    "③ 带时间约定的计划/约定（X月X日体检/下月搬家/下周上线）→ evidence=explicit；"
    "归属 chain（如\"体检安排\"\"搬家\"\"项目X\"）\n"
    "④ 长期需求/目标（正在进行的项目/持续任务/职业背景）→ evidence=explicit；"
    "归属 chain（如\"三区三线划定项目\"）\n"
    "以下一律不输出（不产 cards 也不产 wiki）：寒暄客套（好的/谢谢/天气/情绪/再见）、一次性闲聊、临时问答、"
    "一次性任务（如\"帮我把X列出来/做一下/检查一下\"——除非其结果含稳定事实）、"
    "无长期价值的观察、纯查询（如\"帮我查一下\"，除非查询结果含稳定事实）、"
    "API Key/密码/Token 等凭证明文本身（这类敏感值不记入记忆，只可记录\"已配置某凭证\"这类元信息；"
    "\"记住别泄露\"类保密指令本身也不产卡）\n"
    "- 知识类内容（概念解释/规范条文/教程/文档，如\"什么是三区三线\"的回答）→ 不产 cards，"
    "改产 wiki 条目（见下方 wiki 规则）：知识走知识库，不属个人记忆\n"
    "- 工具标记不是内容：回复中的 \"[tool:工具名]\" 前缀是工具来源标记，不是待提取事实；"
    "从工具结果提取事实时去掉该前缀，且 \"tool:xxx\" 绝不进 entities\n"
    "- evidence 其余枚举：inferred=分身推断/从上下文推导；uncertain=不确定、可能记错。"
    "只输出四个枚举之一。用户表达不确定（\"好像/记不清/可能\"）但提及具体事实 → 仍提取为 uncertain 卡（进待审），"
    "即使分身回复\"先不记/不确定就不记\"也不构成跳过理由\n"
    "- 冲突裁决（对应矛盾识别）：若本条事实与旧记忆矛盾（同一件事的新结果），"
    "supersedes 填被替代的旧事实一句话标题（新覆盖旧，永远成立）；无矛盾填空串\n"
    "- 去重合并：仅对与已有记忆同义的重复内容去重（链合并由系统 resolve_chain 处理）；"
    "同一回合内的多条独立事实必须分别输出多张卡，禁止合并成一条\n"
    "- ended：本条事实表明所属事件已结束（\"搬完了\"\"结项了\"\"搞定了\"）时填 true，否则 false\n"
    "- source_part：事实主要来自用户亲口说填 \"user\"（即使分身回复中复述了它），"
    "来自分身回复填 \"assistant\"，"
    "来自某个工具结果填 \"tool:工具名\"（工具输出的稳定事实如磁盘信息/文件列表值得提取）\n"
    "- chain：同一主题/任务的多条事实归入同一事件链标题；跨会话同主题也用同一标题；"
    "无明确归属为空串\n"
    "- entities：事实中的专有名词（人名/地名/项目/设备/软件/组织），用于跨卡关联；无则空数组\n"
    "- wiki：知识类内容走知识库。kind 三分：spec=规范条文（spec_id/level 必填，如 GB-50137-2011/national，"
    "content 为规范全文）；concept=概念/术语（如\"三区三线\"，单条解释）；tutorial=教程/指南。"
    "content 写完整正文；entities 填专有名词；aliases 填同义说法（吸收措辞漂移，"
    "如\"三条控制线\"是\"三区三线\"的同义说法）；evidence 默认 explicit，"
    "不确定/推断的知识填 inferred 或 uncertain（低置信知识进待审）；无知识类内容时 wiki 输出空数组 []\n"
    "- 只输出 JSON，不要其他文字\n"
    "示例（概念问答 → wiki，不产卡）：\n"
    '{"cards": [], "wiki": [{"kind": "concept", "title": "三区三线", '
    '"content": "三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区，'
    '以及永久基本农田、生态保护红线、城镇开发边界三条控制线。", '
    '"tags": ["国土空间规划"], "entities": ["三区三线", "生态保护红线", "永久基本农田"], '
    '"aliases": ["三条控制线"], "evidence": "explicit"}]}\n'
    "示例（教程问答 → wiki tutorial，不产卡）：\n"
    '{"cards": [], "wiki": [{"kind": "tutorial", "title": "三区三线叠加分析", '
    '"content": "步骤：1.加载三区三线图层；2.用叠加分析工具做空间相交；3.输出冲突区域图层。", '
    '"tags": ["GIS", "教程"], "entities": ["ArcGIS"], "aliases": [], "evidence": "explicit"}]}\n'
    "示例（不确定的知识 → wiki evidence=uncertain，进待审）：\n"
    '{"cards": [], "wiki": [{"kind": "concept", "title": "双评价", '
    '"content": "双评价指资源环境承载力和国土空间开发适宜性评价。", '
    '"tags": ["国土空间规划"], "entities": ["双评价"], "aliases": [], "evidence": "uncertain"}]}'
)

# 本地小模型（qwen3-it-4b-FLM 等 4B 级）专用精简提示词：
# 全量提示词（_EXTRACT_PROMPT）的字段/分支过多，4B 级模型服从度会随长度衰减
# （v4 验收：schema 骨架示例不够，必须给填好的 few-shot 示例）。本变体只保留
# 判类必需信息 + 3 个输入→输出完整示例，牺牲 spec 等冷门分支，换取
# wiki 分流 / 一次性任务丢弃 / 多事实拆分三大判别稳定（PROMPT-EVALUATION 附录 B）。
_EXTRACT_PROMPT_SMALL = (
    "你是记忆提取器，只输出 JSON，不回复用户。\n"
    "输入格式：\n用户：{对话}\n分身：{回复}\n"
    "输出 JSON（cards 或 wiki 可为空数组）：\n"
    '{"cards": [{"title": "一句话标题", "content": "第三人称事实描述", '
    '"evidence": "explicit|inferred|uncertain|directive", "chain": "事件链标题（无则空串）", '
    '"entities": ["专有名词"], "supersedes": "", "ended": false, '
    '"source_part": "user|assistant"}], '
    '"wiki": [{"kind": "concept|tutorial|spec", "title": "标题", "content": "完整定义/步骤/条文", '
    '"spec_id": "规范类必填（如 GB 50137-2011），其余空串", "evidence": "explicit|inferred|uncertain"}]}\n'
    "规则：\n"
    "1. 只提取四类永久事实，每条独立事实输出一张卡：偏好（喜欢/不喜欢/习惯）；硬性规则/约束"
    "（端口/账号/截止日/禁用项/安全要求，填 directive）；带时间约定的计划；长期需求/目标。"
    "同一回合多条独立事实必须分别输出多张卡，禁止合并成一条。\n"
    "2. 用户明确说的填 explicit；用户说记住/规定/必须/不许填 directive；分身推断填 inferred；"
    "用户说好像/记不清/可能但提到具体事实填 uncertain（仍要提取）。\n"
    "3. 一律不输出（cards/wiki 双空）：寒暄（好的/谢谢/天气/再见）、一次性闲聊、临时问答、一次性任务"
    "（帮我把X列出来/做一下/检查一下）、纯查询、API Key/密码/Token 明文及其\"记住/别泄露\"类保密指令。\n"
    "4. 用户问\"是什么/怎么做/标准是什么\"，回复给出定义/步骤/条文 → 不产卡，产 wiki 条目"
    "（concept=概念，tutorial=步骤教程，spec=规范条文并填 spec_id）；"
    "不确定的知识（我猜/大概/不一定对）→ wiki evidence=uncertain（不产卡）。\n"
    "5. 用户亲口说的填 source_part=user（即使回复复述了），分身说的填 assistant，"
    "工具结果填 tool:工具名。\n"
    "6. 事件结束（搞定了/搬完了/结项了）→ ended=true；新结果替代旧事实 → supersedes 填被替代的一句话标题。\n"
    "7. 只输出 JSON，不要任何其他文字。\n"
    "示例1（偏好）：\n用户：我以后都用中文回复。\n分身：好的。\n"
    '输出：{"cards": [{"title": "偏好中文回复", "content": "用户偏好用中文回复。", '
    '"evidence": "explicit", "chain": "语言偏好", "entities": [], "supersedes": "", '
    '"ended": false, "source_part": "user"}], "wiki": []}\n'
    "示例2（一次性任务，双空）：\n用户：帮我把这个文件里的 TODO 列出来。\n分身：已列出：fix xxx。\n"
    '输出：{"cards": [], "wiki": []}\n'
    "示例3（知识问答 → wiki）：\n用户：什么是三区三线？\n分身：三区三线是国土空间规划中的概念："
    "农业空间、生态空间、城镇空间三区，以及永久基本农田、生态保护红线、城镇开发边界三条控制线。\n"
    '输出：{"cards": [], "wiki": [{"kind": "concept", "title": "三区三线", '
    '"content": "三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区，'
    '以及永久基本农田、生态保护红线、城镇开发边界三条控制线。", '
    '"spec_id": "", "evidence": "explicit"}]}\n'
    "示例4（工具结果，source_part=tool:工具名）：\n用户：帮我看看服务器磁盘空间\n"
    "分身：[tool:bash] /dev/sda1 100G 60G 40G 60% /\n"
    '输出：{"cards": [{"title": "服务器磁盘占用", '
    '"content": "服务器磁盘 /dev/sda1 共 100G 已用 60G（使用率 60%）。", '
    '"evidence": "explicit", "chain": "", "entities": [], "supersedes": "", '
    '"ended": false, "source_part": "tool:bash"}], "wiki": []}\n'
)


def extract_json_object(text: str) -> dict:
    """模型 JSON 输出容错解析：剥代码围栏、取首 { 到末 }、json.loads。

    P2：公开化（distill/fruit 跨模块复用——私有名跨模块导入是循环导入引爆点）。
    截断容错（P2）：LLM 输出被 max_tokens 截断（Unterminated string / 未闭合括号）时，
    尝试修复后再解析——重试一次补齐字符串 + 补全闭合括号，仍失败才抛错。
    """
    payload, _ = _extract_json_object_detailed(text)
    return payload


def _extract_json_object_detailed(text: str) -> tuple[dict, bool]:
    """同 extract_json_object，额外返回 repaired 标志。

    抢救修复（v0.3）：json.loads 失败后经 _repair_truncated_json 修复成功，
    说明原始输出不是合法 JSON——大概率被 max_tokens 截断（结构被补齐但内容
    可能残缺，修复成功会掩盖截断）。调用方拿到 repaired=True 必须降级处理：
    强制 evidence=uncertain → 卡进 lesson_pending / wiki 进 pending（待审），
    残缺内容不得自动固化进永久记忆。
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        end_fence = cleaned.find("```", 3)
        if end_fence != -1:
            cleaned = cleaned[3:end_fence]
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    repaired = False
    try:
        payload = json.loads(cleaned)
    except (ValueError, TypeError):
        # 截断容错：尝试修复未闭合字符串与括号（LLM 输出常被 max_tokens 截断）
        repaired = True
        repaired_text = _repair_truncated_json(cleaned)
        try:
            payload = json.loads(repaired_text)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"JSON parse failed after truncation repair: {exc}") from exc
    if isinstance(payload, list):
        # V3.5：模型"无可提取"会输出裸 []（v2 时是 {}）——视为空提取，不炸
        return {}, repaired
    if not isinstance(payload, dict):
        raise ValueError("JSON top level is not an object")
    return payload, repaired


def _repair_truncated_json(text: str) -> str:
    """修复截断 JSON：补全未闭合字符串的引号、转义尾随反斜杠、补全闭合括号。

    策略（逐字符扫描，够用即可，不追求完整 JSON 修复）：
    - 奇数个未配对 `"` → 在末尾补 `"`；
    - 末尾是孤立 `\\` → 移除（避免"字符串以反斜杠结尾"）；
    - 字符串结束后紧跟 `}`/`]`（缺逗号）→ 插逗号；
    - 计数 { [ ( 与 } ] )，差量补全闭合。
    """
    if not text:
        raise ValueError("empty JSON")
    # 去掉末尾孤立反斜杠（`...\` 是未转义的反斜杠，json 会拒）
    while text.endswith("\\"):
        text = text[:-1]
    in_str = False
    escaped = False
    out: list[str] = []
    # 记录"上一个非空白字符"，用于判断字符串结束是否紧贴闭合符
    last_significant = ""
    for ch in text:
        if in_str:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            else:
                last_significant = ch
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            last_significant = ""
        elif ch in " \t\r\n":
            out.append(ch)
        elif ch in "}],":
            # 前一个非空白字符是字符串结束引号且当前是闭合符 → 缺逗号
            if last_significant == '"' and ch in "}],":
                out.append(",")
            out.append(ch)
            last_significant = ch
        else:
            out.append(ch)
            last_significant = ch
    if in_str:
        out.append('"')  # 字符串未闭合 → 补引号
    repaired = "".join(out)
    # 用栈追踪未闭合符顺序，按 LIFO 补全正确闭合（`[{"` → `}]}`）
    stack: list[str] = []
    in_s = False
    esc = False
    for ch in repaired:
        if in_s:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_s = False
            continue
        if ch == '"':
            in_s = True
        elif ch in "{([":
            stack.append(ch)
        elif ch in "})]":
            if stack:
                stack.pop()
    close_map = {"{": "}", "[": "]", "(": ")"}
    for open_ch in reversed(stack):
        repaired += close_map[open_ch]
    return repaired


# 向后兼容别名（README §9.8 将 _extract_json_object 列为 DSH 侧复用点）
_extract_json_object = extract_json_object


def _jaccard(a: list[str], b: list[str]) -> float:
    """词元集合 Jaccard 相似度（B2 时序裁决规则兜底用）。"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class ExtractError(Exception):
    """提取失败（端点不可用 / 解析失败）。"""


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """一次提取的完整结果：记忆卡 + 知识库条目（V3.5 分流输出）。

    cards 与旧返回同构（list[tuple[MemoryCard, str]]，兼容旧 fake/后端）；
    wiki_entries 为空表示本次无知识类内容（旧模型只回 cards 也兼容）。
    """

    cards: list[tuple[MemoryCard, str]] = field(default_factory=list)
    wiki_entries: list[WikiEntry] = field(default_factory=list)


class Extractor(Protocol):
    def extract(self, run: MemoryRun) -> list[tuple[MemoryCard, str]]:
        """返回 (事件卡, 事件链标题)；链标题为空表示不归属任何链。"""
        ...


_BATCH_EXTRACT_PROMPT = (
    "你是一次性记忆提取器，不是对话助手。下面有多段独立对话，每段以「对话 <idx>」开头。"
    "对每段对话分别提取值得长期记住的事实，按编号输出 JSON：\n"
    '{"results": [{"idx": 0, "cards": [{"title": "一句话标题", "content": "事实描述（第三人称、可独立理解）", '
    '"evidence": "explicit|inferred|uncertain|directive", "chain": "事件链标题（无则空串）", '
    '"entities": ["实体1"], "supersedes": "", "ended": false, "source_part": "user"}], '
    '"wiki": [{"kind": "concept|spec|tutorial", "title": "标题", "content": "正文", '
    '"tags": ["标签"], "entities": ["实体"], "aliases": ["同义说法"], '
    '"spec_id": "（kind=spec 必填）", "level": "national|province|city|county|township", '
    '"evidence": "explicit|inferred|uncertain"}]}]}\n'
    "四类永久事实与单条一致：①偏好→explicit+chain ②硬性规则/约束→directive 或 explicit+entities"
    "③带时间约定的计划→explicit+chain ④长期需求/目标→explicit+chain；"
    "寒暄客套、一次性闲聊、纯查询、一次性任务、凭证不输出；"
    "同一回合多条独立事实分别输出多张卡，禁止合并；"
    "知识类内容（概念/规范/教程）不产 cards，改产 wiki 条目（kind=spec|concept|tutorial；"
    "spec 需 spec_id/level；不确定/推断的知识 evidence=inferred|uncertain 进待审）；"
    "evidence 只用四个枚举之一；新结果在 supersedes 填被替代旧事实标题；"
    "chain 跨会话同主题用同一标题；只输出 JSON 不要其他文字。"
)


class LLMExtractor:
    """LLM 提取（Backend 协议：role=extract 后端；策略驱动单条/批量）。"""

    def __init__(
        self,
        backend: Backend,
        *,
        fallback_backend: Backend | None = None,
        strategy: ExtractStrategy | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,  # 抢救修复（v0.3）：1024 曾致 wiki 双分支输出被截断（详见 PROMPT-EVALUATION §6；截断卡已入库）→ 提至与批量一致
        prompt: str | None = None,  # 提示词变体：缺省全量；小模型（本地轨）由装配方注入精简版
    ) -> None:
        self.backend = backend
        self.fallback_backend = fallback_backend  # P1b：hybrid 超长降级云端用
        self.strategy = strategy
        self.batch_size = strategy.batch_size() if strategy is not None else 1
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt = prompt or _EXTRACT_PROMPT

    def extract(
        self, run: MemoryRun, *, timeout: float | None = None
    ) -> ExtractionResult:
        # P1b：路由消费——策略裁决驱动 skip/降级（此前 RouteDecision.backend 无人使用）
        decision = self.strategy.decide(run) if self.strategy is not None else None
        if decision is not None and decision.backend == "skip":
            # 云端超容量：省一次调用（CloudStrategy "跳过"语义真正落地）
            return ExtractionResult()
        backend = self.backend
        if (
            decision is not None
            and decision.backend == "cloud"
            and self.fallback_backend is not None
        ):
            backend = self.fallback_backend  # hybrid：本地超长 → 降级云端
        # 消解能力：策略给定的输入规模上限（默认兼容 200/400 旧行为）
        user_text, reply_text = self._truncate(run, decision)
        messages = [
            {"role": "system", "content": self.prompt},
            {
                "role": "user",
                "content": f"用户（档位 {run.tier}）：{user_text}\n分身：{reply_text}",
            },
        ]
        try:
            resp = backend.complete(
                messages, temperature=self.temperature, max_tokens=self.max_tokens,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 - 端点不可用（含云端失败）
            raise ExtractError(f"后端调用失败: {exc}") from exc
        try:
            payload, json_repaired = _extract_json_object_detailed(resp.text)
            raw_cards = payload.get("cards")  # 模型正确判"无可提取"时返回空对象，视为零卡
            if raw_cards is None:
                raw_cards = []
            raw_wiki = payload.get("wiki")  # V3.5 分流：知识类内容走知识库（可缺省=旧模型）
            if not isinstance(raw_wiki, list):
                raw_wiki = []
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            # 诊断友好：附带原始输出前 200 字符（NPU 真实模型排障用）
            raise ExtractError(
                f"提取 JSON 解析失败: {exc} (raw={resp.text[:200]!r})"
            ) from exc
        # 抢救修复（v0.3）：截断检测双信号——后端 finish_reason=length（明确截断）
        # 或 JSON 需结构修复（大概率被 max_tokens 截断）。截断产出的卡/wiki 一律
        # 降级 evidence=uncertain → lesson_pending / pending（待审），残缺内容
        # 不得自动固化进永久记忆（此前修复器成功会掩盖内容残缺）。
        truncated = (getattr(resp, "finish_reason", "") or "") == "length" or json_repaired
        return ExtractionResult(
            cards=self._cards_from_raw(run, raw_cards, truncated=truncated),
            wiki_entries=self._wiki_from_raw(run, raw_wiki, truncated=truncated),
        )

    def _turn_cap(self, run: MemoryRun, decision=None) -> int:
        """模型消解能力上限：策略裁决或默认 600 字符（兼容 200+400）。"""
        if decision is not None:
            return decision.truncate_chars
        if self.strategy is not None:
            return self.strategy.decide(run).truncate_chars
        return 600

    def _truncate(self, run: MemoryRun, decision=None) -> tuple[str, str]:
        """按容量截断（回复占 2/3 预算）：超长对话不撑爆小模型上下文。"""
        cap = self._turn_cap(run, decision)
        total = len(run.user_text or "") + len(run.reply_text or "")
        if total <= cap:
            return run.user_text or "", run.reply_text or ""
        reply_cap = max(0, cap - cap // 3)
        user_cap = max(0, cap - reply_cap)
        return (run.user_text or "")[:user_cap], (run.reply_text or "")[:reply_cap]

    def extract_batch(
        self, runs: list[MemoryRun]
    ) -> list[ExtractionResult]:
        """批量提取：云端攒批一次调用 N 条；本地/混合逐条（内部管道）。

        每条结果含 cards + wiki 双分支（分流）；旧格式 JSON 无 wiki 键 → 空列表兼容。
        """
        if self.batch_size <= 1 or self.strategy is None or self.strategy.name != "cloud":
            return [self.extract(run) for run in runs]
        blocks: list[str] = []
        for idx, run in enumerate(runs):
            user_text, reply_text = self._truncate(run)
            blocks.append(f"「对话 {idx}」用户：{user_text}\n分身：{reply_text}")
        messages = [
            {"role": "system", "content": _BATCH_EXTRACT_PROMPT},
            {"role": "user", "content": "\n\n".join(blocks)},
        ]
        try:
            resp = self.backend.complete(messages, temperature=0.0, max_tokens=2048)
            payload, json_repaired = _extract_json_object_detailed(resp.text)
            results = payload["results"]
        except Exception:  # noqa: BLE001 - 批量失败降级逐条重试
            return [self.extract(run) for run in runs]
        # 抢救修复（v0.3）：与单条同口径——批量输出截断 → 本批卡/wiki 全部降级待审
        truncated = (getattr(resp, "finish_reason", "") or "") == "length" or json_repaired
        out: list[ExtractionResult] = [ExtractionResult() for _ in runs]
        if isinstance(results, list):
            for entry in results:
                if not isinstance(entry, dict):
                    continue
                try:
                    idx = int(entry.get("idx", -1))
                except (TypeError, ValueError):
                    continue
                raw_cards = entry.get("cards")
                raw_wiki = entry.get("wiki")
                if 0 <= idx < len(runs):
                    out[idx] = ExtractionResult(
                        cards=(
                            self._cards_from_raw(runs[idx], raw_cards, truncated=truncated)
                            if isinstance(raw_cards, list) else []
                        ),
                        wiki_entries=(
                            self._wiki_from_raw(runs[idx], raw_wiki, truncated=truncated)
                            if isinstance(raw_wiki, list) else []
                        ),
                    )
        return out

    def _cards_from_raw(
        self, run: MemoryRun, raw_cards: list, *, truncated: bool = False
    ) -> list[tuple[MemoryCard, str]]:
        """raw cards -> MemoryCard（单条与批量共用；含证据枚举/回退映射）。

        truncated（抢救修复 v0.3）：输出被截断时强制 evidence=uncertain——
        auto_commit(uncertain)=False → 卡一律 lesson_pending（待审），
        残缺内容不自动固化（此前截断修复成功会掩盖内容残缺直接入 event）。
        """
        cards: list[tuple[MemoryCard, str]] = []
        for seq, raw in enumerate(raw_cards, start=1):
            if not isinstance(raw, dict):
                continue  # 模型偶发非 dict 条目 → 跳过（与 _wiki_from_raw 同防护）
            title = str(raw.get("title", "")).strip()
            content = str(raw.get("content", "")).strip()
            if not content:
                continue  # 内容为空 → 不写
            evidence = str(raw.get("evidence", "")).strip().lower()
            if evidence not in ("directive", "explicit", "inferred", "uncertain"):
                # 旧库/模型未遵守枚举：按旧 confidence 字段回退映射（迁移兼容）
                try:
                    _legacy_conf = float(raw.get("confidence", 0.0))
                except (TypeError, ValueError):
                    _legacy_conf = 0.0
                evidence = (
                    "explicit" if _legacy_conf >= 0.8
                    else "inferred" if _legacy_conf >= 0.5
                    else "uncertain"
                )
            if truncated:
                evidence = "uncertain"  # 截断降级：待审，不自动固化
            confidence = base_score(evidence)
            kind = "event" if auto_commit(evidence) else "lesson_pending"
            prefix = "evt" if kind == "event" else "les"
            card_id = f"{prefix}-{run.run_id}-{seq}"
            chain_title = str(raw.get("chain", "")).strip()
            raw_entities = raw.get("entities", [])
            if isinstance(raw_entities, list):
                entities = tuple(str(e).strip() for e in raw_entities if str(e).strip())
            else:
                entities = ()
            supersedes = str(raw.get("supersedes", "")).strip()
            ended = bool(raw.get("ended", False))
            source_part = str(raw.get("source_part", "assistant")).strip() or "assistant"
            # P2：source_path 按 kind 路由（旧实现一律 events/cards/——lesson_pending
            # 实际落盘 lessons/pending/，溯源元数据与明文位置不符）
            _kind_dir = {
                "event": "events/cards",
                "lesson_pending": "lessons/pending",
                "lesson_permanent": "lessons/permanent",
            }
            cards.append(
                (
                    MemoryCard(
                        id=card_id,
                        kind=kind,
                        title=title,
                        content=content,
                        source_path=f"{_kind_dir.get(kind, 'events/cards')}/{card_id}.md",
                        created_at=now_iso(),
                        run_id=run.run_id,
                        confidence=confidence,
                        evidence=evidence,
                        parent_id="",  # 链归属由管道 resolve_chain 确定性裁决（§9.7）
                        entities=entities,
                        trace_event_id=run.trace_event_id,
                        supersedes=supersedes,  # type: ignore[arg-type]
                        ended_at=(now_iso() if ended else None),  # type: ignore[arg-type]
                        source_part=source_part,
                    ),
                    chain_title,
                )
            )
        return cards

    def _wiki_from_raw(
        self, run: MemoryRun, raw_wiki: list, *, truncated: bool = False
    ) -> list[WikiEntry]:
        """raw wiki -> WikiEntry（分流知识库；单条与批量共用，与 _cards_from_raw 同构）。

        证据门与卡一致：explicit/directive → active（直通检索）；
        inferred/uncertain → pending（待审，不进检索；promote_entry 提升）。
        truncated（抢救修复 v0.3）：输出被截断时强制 evidence=uncertain →
        一律 pending（残缺知识不得直通检索）。
        """
        entries: list[WikiEntry] = []
        for raw in raw_wiki:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("kind", "")).strip().lower()
            if kind not in ("spec", "concept", "tutorial"):
                kind = "concept"
            title = str(raw.get("title", "")).strip()
            content = str(raw.get("content", "")).strip()
            if not title or not content:
                continue  # 标题或正文为空 → 不写
            evidence = str(raw.get("evidence", "")).strip().lower()
            if evidence not in ("directive", "explicit", "inferred", "uncertain"):
                evidence = "explicit"  # 缺省直通：模型没给证据时按可信处理
            if truncated:
                evidence = "uncertain"  # 截断降级：待审，不直通检索
            source_part = str(raw.get("source_part", "assistant")).strip() or "assistant"
            status = "active" if auto_commit(evidence, source_part=source_part) else "pending"
            entry_id = wiki_id(title, kind)
            _tags = raw.get("tags", []) if isinstance(raw.get("tags"), list) else []
            _aliases = raw.get("aliases", []) if isinstance(raw.get("aliases"), list) else []
            _entities = raw.get("entities", []) if isinstance(raw.get("entities"), list) else []
            entries.append(
                WikiEntry(
                    id=entry_id,
                    kind=kind,
                    title=title,
                    content=content,
                    spec_id=str(raw.get("spec_id", "")).strip(),
                    level=str(raw.get("level", "")).strip(),
                    tags=tuple(str(t).strip() for t in _tags if str(t).strip()),
                    aliases=tuple(str(a).strip() for a in _aliases if str(a).strip()),
                    entities=tuple(str(e).strip() for e in _entities if str(e).strip()),
                    source_path="",  # 落盘路径由 WikiStore.entry_path 按 status 裁决
                    created_at=now_iso(),
                    updated_at=now_iso(),
                    source_run_id=run.run_id,
                    source_part=source_part,
                    evidence=evidence,
                    supersedes=str(raw.get("supersedes", "")).strip(),
                    status=status,
                    confidence=compute_confidence(
                        evidence, source_part=source_part,
                        corroborated=False, directive_hit=False,
                    ),
                )
            )
        return entries


class MemoryWritePipeline:
    """写入管道：enqueue 非阻塞（对话不阻塞）→ 后台 worker / process_staged 异步提取。"""

    def __init__(
        self,
        store: MemoryStore,
        *,
        extractor: Extractor | None = None,
        wiki_store: WikiStore | None = None,
        enabled: bool = True,
        worker: bool = False,
        poll_seconds: float = 0.5,
        cooldown_seconds: float = 20.0,
        max_failures: int = 3,
        bus: EventBus | None = None,
        batch_size: int | None = None,
        backlog_high_water: int = 0,
        idle_poll_seconds: float = 2.0,
        active_poll_seconds: float = 0.2,
        timeout_per_chars: float = 0.0,
    ) -> None:
        self.store = store
        self.extractor = extractor
        self.wiki_store = wiki_store  # None = 知识库支线关闭（向后兼容）
        # 知识写侧管道（幂等写 + 别名吸收 + 版本链 + 待审路由；worker=False：
        # 提取本身已由本管道 worker 异步，wiki 写同步快，无需再起线程）
        self._wiki_pipe: WikiWritePipeline | None = None
        if wiki_store is not None:
            self._wiki_pipe = WikiWritePipeline(
                wiki_store,
                enabled=enabled,
                worker=False,
                log=(
                    self.store.log_decision
                    if callable(getattr(self.store, "log_decision", None))
                    else None
                ),
            )
        self.enabled = enabled
        self.bus = bus
        # P1a：batch_size 双旋钮合一——缺省时自动对齐提取器（CloudStrategy 默认 8，
        # 旧实现管道恒为 1，云端攒批路径永远走不到 extract_batch）；显式传入仍可覆盖。
        if batch_size is None:
            batch_size = getattr(extractor, "batch_size", 1) or 1
        self.batch_size = max(1, batch_size)
        self.cooldown_seconds = cooldown_seconds
        self.max_failures = max_failures
        # NPU 慢速适配（V3.5）
        self.backlog_high_water = backlog_high_water  # 积压高水位：超过则跳过新入队
        self.idle_poll_seconds = idle_poll_seconds  # 无活时轮询间隔（少空转）
        self.active_poll_seconds = active_poll_seconds  # 有活时轮询间隔（快消化）
        self.timeout_per_chars = timeout_per_chars  # 超时自适应系数（秒/字符，0=不启用）
        self._last_extract_at = 0.0
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, float] = {}  # P1b：run_id → 下次可重试时刻（退避）
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if worker and enabled and extractor is not None:
            self._thread = threading.Thread(
                target=self._worker_loop, args=(poll_seconds,), daemon=True
            )
            self._thread.start()

    def _timeout_for(self, run: MemoryRun) -> float | None:
        """超时自适应：NPU 慢速下长回合给足预算（避免固定超时误杀）。"""
        if self.timeout_per_chars <= 0:
            return None
        chars = len(run.user_text or "") + len(run.reply_text or "")
        return max(60.0, chars * self.timeout_per_chars)

    def enqueue(
        self,
        *,
        user_text: str,
        reply_text: str,
        session_id: str = "default",
        tier: IntentTier | str,
        project_id: str | None = None,
        trace_event_id: str = "",
    ) -> str:
        """入队一条待提取对话；永不阻塞、永不抛错（对话不中断）。"""
        tier_value = tier.value if isinstance(tier, IntentTier) else str(tier)
        ts = now_iso()
        digest = hashlib.sha1(f"{session_id}|{ts}|{user_text}".encode()).hexdigest()[:12]
        run_id = f"run-{digest}"
        # NPU 慢速：积压超过高水位 → 跳过（记录不丢原文，但不再积压）。
        # P1b：禁用态（enabled=False / 无提取器）不参与水位判定——否则禁用期
        # 入队的 staged run 永远不消化，一旦堆满水位，恢复后所有新对话都被误拦（A5 违例）。
        if (
            self.enabled
            and self.extractor is not None
            and self.backlog_high_water > 0
            and self.store.staged_backlog() >= self.backlog_high_water
        ):
            with contextlib.suppress(Exception):
                self.store.log_decision("extract_backlog", f"{run_id}: 积压 {self.store.staged_backlog()} ≥ 高水位")
            return run_id
        priority = extract_priority(user_text, reply_text)
        run = MemoryRun(
            run_id=run_id, session_id=session_id, user_text=user_text,
            reply_text=reply_text, tier=tier_value, ts=ts, project_id=project_id,
            trace_event_id=trace_event_id, priority=priority,
        )
        try:
            self.store.insert_run(run)
            if not self.enabled or self.extractor is None:
                self.store.log_decision("extract_disabled", f"提取未启用，run 暂存: {run_id}")
            else:
                # §9.7 成本控制：门卫粗筛，寒暄/无事实信号 → 落盘但跳过提取（对话不丢）
                worth, reason = should_extract(user_text, reply_text)
                if not worth:
                    self.store.mark_run(run_id, "skipped", reason)
                    self.store.log_decision("extract_skip", f"{run_id}: {reason}")
        except Exception as exc:  # noqa: BLE001 - 存储失败也不阻塞对话
            with contextlib.suppress(Exception):
                self.store.log_decision("enqueue_failed", f"{run_id}: {exc}")
        return run_id

    def process_staged(self, limit: int | None = None) -> int:
        """同步处理 staged/failed runs（测试与 flush 用）；返回处理数量。

        limit 缺省时按 batch_size 取量：云端攒批一次处理多条。
        """
        if not self.enabled or self.extractor is None:
            return 0
        take = limit if limit is not None else self.batch_size
        runs: list[MemoryRun] = []
        while len(runs) < take:
            run = self.store.next_staged_run()
            if run is None:
                break
            if self._retry_at.get(run.run_id, 0.0) > time.monotonic():
                # P1b：退避期内不重试——认领式取单需回滚为 failed，等下一轮
                with contextlib.suppress(Exception):
                    self.store.mark_run(run.run_id, "failed")
                break
            runs.append(run)
        if not runs:
            return 0
        if len(runs) > 1 and self.batch_size > 1 and hasattr(self.extractor, "extract_batch"):
            return self._process_batch(runs)
        for run in runs:
            self._process(run)
        return len(runs)

    def _apply_conflict(self, card: MemoryCard) -> None:
        """B2 时序裁决（ADR-0019 决策 4）：同一件事出现不同结果 → 新结果覆盖旧结果。

        - LLM 显式 supersedes 标注 → 按标题匹配旧卡；
        - 规则兜底：同枝 + 实体交集 + 词元 Jaccard >= 0.35（同断言近似）；
        - 仅 event（高置信 >= 0.5）自动执行；lesson_pending（低置信）走 pending 人工，不自动覆盖；
        - 旧卡 superseded + invalid_at + decision_log 审计，不删（版本链）。
        """
        if card.kind != "event":
            return
        target: MemoryCard | None = None
        if card.supersedes.strip():
            target = self.store.find_card_by_title(card.supersedes)
        if target is None:
            best: MemoryCard | None = None
            best_sim = 0.0
            for cand in self.store.conflict_candidates(card):
                sim = _jaccard(tokenize(cand.content), tokenize(card.content))
                if sim > best_sim:
                    best_sim = sim
                    best = cand
            if best is not None and best_sim >= 0.35:
                target = best
        if target is not None and target.id != card.id:
            self.store.supersede_card(target.id, card.id)

    def _finalize_card(self, card: MemoryCard, run: MemoryRun) -> MemoryCard:
        """置信校准（§9.7）：证据门最终裁决——LLM 标签 + 确定性修正（来源/佐证/指令）。

        无证据标签（直写卡/旧管道）→ 原样保留，不破坏既有行为。
        """
        evidence = (card.evidence or "").strip()
        if not evidence:
            return card
        directive_hit = any(t in (run.user_text or "") for t in DIRECTIVE_TRIGGERS)
        corroborated = self.store.count_corroborations(card) >= 1
        confidence = compute_confidence(
            evidence, source_part=card.source_part,
            corroborated=corroborated, directive_hit=directive_hit,
        )
        kind = "event" if auto_commit(
            evidence, source_part=card.source_part,
            corroborated=corroborated, directive_hit=directive_hit,
        ) else "lesson_pending"
        return replace(card, kind=kind, confidence=confidence, corroborations=int(corroborated))

    def close(self) -> None:
        """停止后台 worker（应用退出/测试清理）。"""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    # ---------- 内部 ----------

    def _worker_loop(self, poll_seconds: float) -> None:
        while not self._stop.is_set():
            # P2：cooldown 语义落地——上一轮提取后冷却期内不提取（NPU 慢速喘息，
            # 防止连续打爆推理；此前参数存而不用）
            if time.monotonic() - self._last_extract_at < self.cooldown_seconds:
                self._stop.wait(poll_seconds)
                continue
            processed = 0
            try:
                processed = self.process_staged()
            except Exception as exc:  # noqa: BLE001 - B3：兜底不静默，记入决策日志
                with contextlib.suppress(Exception):
                    self.store.log_decision(
                        "extract_worker_error", f"{type(exc).__name__}: {exc}"
                    )
            if processed > 0:
                # 有活：短轮询快消化（NPU 慢速下一条一条来）
                self._stop.wait(self.active_poll_seconds)
            else:
                # 无活：长轮询少空转（不抢 CPU/NPU）
                self._stop.wait(self.idle_poll_seconds)

    def _process(self, run: MemoryRun) -> None:
        """单条处理（本地/混合路径；失败保留 run 可重试）。"""
        self.store.mark_run(run.run_id, "extracting")
        try:
            timeout = self._timeout_for(run)
            if timeout is not None:
                try:
                    # 自适应超时：LLMExtractor 支持 timeout 参数（NPU 长回合给足预算）
                    result = self.extractor.extract(run, timeout=timeout)  # type: ignore[union-attr, call-arg]
                except TypeError:
                    # 非 LLMExtractor（测试 fake / 无 timeout 支持）：回退无 timeout
                    result = self.extractor.extract(run)  # type: ignore[union-attr]
            else:
                result = self.extractor.extract(run)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - 提取失败：run 保留，退避重试
            self._mark_failed(run, exc)
            return
        if isinstance(result, list):
            # 兼容旧 fake / 旧后端：裸卡列表 → 包一层分流结果（wiki 空）
            result = ExtractionResult(cards=result)
        if not isinstance(result, ExtractionResult):
            self._mark_failed(run, ExtractError("提取结果类型异常"))
            return
        try:
            card_summaries = self._commit_cards(run, result.cards)
            wiki_summaries = self._commit_wiki_entries(run, result.wiki_entries)
            self._finalize_run(run, card_summaries, wiki_summaries)
        except Exception as exc:  # noqa: BLE001 - B3：提交阶段失败 → failed 重试，run 不卡 extracting
            self._mark_failed(run, exc)
            return

    def _process_batch(self, runs: list[MemoryRun]) -> int:
        """批量处理（云端攒批路径）：一次提取 N 条，逐条提交。"""
        for run in runs:
            self.store.mark_run(run.run_id, "extracting")
        try:
            cards_batch = self.extractor.extract_batch(runs)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - 批量失败：整批保留重试
            for run in runs:
                self._mark_failed(run, exc)
            return len(runs)
        for run, result in zip(runs, cards_batch):
            if isinstance(result, list):
                # 兼容旧 extract_batch 返回 list[list[(卡,链)]] → 包一层分流结果
                result = ExtractionResult(cards=result)
            if isinstance(result, ExtractionResult):
                try:
                    card_summaries = self._commit_cards(run, result.cards)
                    wiki_summaries = self._commit_wiki_entries(run, result.wiki_entries)
                    self._finalize_run(run, card_summaries, wiki_summaries)
                except Exception as exc:  # noqa: BLE001 - B3：单条提交失败不影响整批其余
                    self._mark_failed(run, exc)
            else:
                self._mark_failed(run, ExtractError("批量提取单条结果异常"))
        return len(runs)

    def _mark_failed(self, run: MemoryRun, exc: Exception) -> None:
        """提取失败记账：run 保留，退避重试，超限转 error（对话永不丢）。

        P1b：失败后按指数退避（5s/10s/15s…，上限 60s）再重试——旧实现
        active_poll 0.2s 下 3 次失败秒烧完直接 error，瞬时故障无机会恢复。
        """
        failures = self._failures.get(run.run_id, 0) + 1
        self._failures[run.run_id] = failures
        self.store.mark_run(run.run_id, "failed", str(exc))
        with contextlib.suppress(Exception):
            self.store.log_decision("extract_failed", f"{run.run_id}: {exc}")
        if failures >= self.max_failures:
            self.store.mark_run(run.run_id, "error", "max_failures")
            self._retry_at.pop(run.run_id, None)
        else:
            self._retry_at[run.run_id] = time.monotonic() + min(
                60.0, 5.0 * failures
            )

    def _commit_cards(
        self, run: MemoryRun, cards: list[tuple[MemoryCard, str]]
    ) -> list[dict]:
        """提交一张 run 的提取结果（单条与批量共用；返回卡摘要供事件/日志）。"""
        # §9.7 实证：记录提取成本（输入字符量，审计聚合用；对话不阻塞）
        with contextlib.suppress(Exception):
            self.store.log_decision(
                "extract_cost",
                f"{run.run_id}: in_chars={len(run.user_text or '') + len(run.reply_text or '')}",
            )
        card_summaries: list[dict] = []
        for card, chain_title in cards:
            if chain_title.strip():
                # 归链稳定（§9.7）：确定性裁决，不再直接哈希 LLM 标题
                resolved_id = self.store.resolve_chain(chain_title, card.entities)
                card = replace(card, parent_id=resolved_id)
            card = self._finalize_card(card, run)
            self.store.write_card(card)
            if chain_title.strip():
                self.store.register_chain_card(chain_title, card)
                # B2：事件已结束（LLM ended=true）→ 枝完结萎缩
                if card.ended_at:
                    with contextlib.suppress(Exception):
                        self.store.mark_ended(card.parent_id, at=card.ended_at)
            # B2：时序裁决（同枝+同实体+同断言 → 新覆盖旧；低置信 pending 不自动覆盖）
            self._apply_conflict(card)
            card_summaries.append(
                {
                    "id": card.id,
                    "kind": card.kind,
                    "title": card.title,
                    "confidence": card.confidence,
                    "evidence": card.evidence,
                    "chain_title": chain_title,
                    "entities": list(card.entities),
                }
            )
        return card_summaries

    def _commit_wiki_entries(
        self, run: MemoryRun, entries: list[WikiEntry]
    ) -> list[dict]:
        """提交知识库条目（分流；经 WikiWritePipeline 幂等写 + 版本链 + 待审路由）。"""
        if self._wiki_pipe is None or not entries:
            return []
        return self._wiki_pipe.submit(run, entries)

    def _finalize_run(
        self,
        run: MemoryRun,
        card_summaries: list[dict],
        wiki_summaries: list[dict],
    ) -> None:
        """一次 run 提取完成收尾：日记 + 状态 done + 事件 + 决策日志（卡/知识库共用）。"""
        # B2：日记 = 时间视角第一检索路由（V2 append_daily_log 移植回退补漏）
        with contextlib.suppress(Exception):
            wiki_part = f"，{len(wiki_summaries)} 条知识" if wiki_summaries else ""
            entry = (
                f"- {run.ts} [{run.tier}] 用户：{run.user_text}\n"
                f"  分身：{run.reply_text}\n"
                f"  提取：{len(card_summaries)} 张卡{wiki_part}\n"
            )
            self.store.append_daily_log(run.ts[:10], entry)
        self.store.mark_run(run.run_id, "done")
        self._failures.pop(run.run_id, None)
        self._retry_at.pop(run.run_id, None)
        self._last_extract_at = time.monotonic()
        if self.bus is not None:
            # V3 独有：提取结果进事件树（挂 turn 子节点，可溯源）
            self.bus.publish(
                Event(
                    session_id=run.session_id,
                    type=EventType.MEMORY_EXTRACT,
                    payload={
                        "run_id": run.run_id,
                        "cards": card_summaries,
                        "wiki": wiki_summaries,
                        "project_id": run.project_id,
                    },
                )
            )
        with contextlib.suppress(Exception):
            self.store.log_decision(
                "extract_done",
                f"{run.run_id}: {len(card_summaries)} 张卡，{len(wiki_summaries)} 条知识",
            )
