"""内置人格库（B3，ADR-0020：V2 personas 移植 + V3 注入边界）。

personas/*.md：明文 front matter（id / name / mbti / when / default / dimensions）
+ 行为纪律正文。每轮按对话内容自动切换，人格纪律属"会话纪律"
（临时注入、有上限）-> 进动态层 D 桶，不占 F 桶。

选择规则：显式点名 > 关键词命中（when 触发词命中数多者优先，平局 default 优先）> 默认人格。

注入边界（ADR-0020）：人格库是给分身调语气的公开模板，不是用户私密数据；
用户自己的对话风格不做成注入人格（防冒名）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.types import IntentTier
from memory.profile import AXIS_DEFS, Dimension

# 显式切换动词：文本同时含人格名/ID 与任一动词 -> 视为显式点名（覆盖关键词）
_SWITCH_VERBS = (
    "用", "以", "切换", "换成", "扮演", "作为", "身份", "风格", "口吻", "方式", "口气", "模式",
)

_DIM_VALUE_RE = re.compile(r"key:\s*(\S+)\s+value:\s*([0-9.]+)")


@dataclass(frozen=True, slots=True)
class Persona:
    """一个内置人格（personas/*.md，零依赖）。"""

    id: str
    name: str
    mbti: str = ""
    when: tuple[str, ...] = ()  # 触发词（front matter 按 / 分隔）
    default: bool = False
    discipline: str = ""  # 行为纪律正文
    dimensions: tuple[Dimension, ...] = ()  # 8 轴（雷达渲染用，不进 prompt）

    def render_d_block(self) -> str:
        """D 桶注入文本：人格纪律（紧凑，<=~120 tok）。"""
        head = f"当前人格：{self.name}"
        if self.mbti:
            head += f"（{self.mbti}）"
        return f"{head}。行为纪律：{self.discipline}"


def parse_persona(text: str) -> Persona | None:
    """解析 personas/*.md（front matter + 行为纪律正文；缺 id/正文返回 None）。"""
    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---")
    head, sep, body = rest.partition("\n---\n")
    if not sep:
        return None
    fields: dict[str, str] = {}
    dim_lines: list[str] = []
    current: str | None = None
    for line in head.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("-") and current == "dimensions":
            dim_lines.append(line[1:].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            current = key.strip()
            if value.strip():
                fields[current] = value.strip()
    persona_id = fields.get("id", "").strip()
    if not persona_id:
        return None
    discipline = body.strip()
    if discipline.startswith("#"):
        _heading, _, discipline = discipline.partition("\n")
        discipline = discipline.strip()
    if not discipline:
        return None
    when = tuple(p.strip() for p in fields.get("when", "").split("/") if p.strip())
    dimensions: list[Dimension] = []
    axis_by_key = {axis[0]: axis for axis in AXIS_DEFS}
    for line in dim_lines:
        match = _DIM_VALUE_RE.search(line)
        if not match:
            continue
        key = match.group(1).lower()
        axis = axis_by_key.get(key)
        if axis is None:
            continue
        try:
            value = float(match.group(2))
        except ValueError:
            continue
        if not (0.0 <= value <= 1.0):
            continue
        dimensions.append(Dimension(key=key, label=axis[1], value=value, anchor=axis[3]))
    return Persona(
        id=persona_id,
        name=fields.get("name", persona_id),
        mbti=fields.get("mbti", "").strip().upper(),
        when=when,
        default=fields.get("default", "false").strip().lower() == "true",
        discipline=discipline,
        dimensions=tuple(dimensions),
    )


class PersonaLibrary:
    """扫描 personas/*.md（明文，零依赖）；顺序：default 优先，其次 id 字典序。"""

    def __init__(self, root: Path) -> None:
        self.dir = Path(root) / "personas"

    def list(self) -> list[Persona]:
        if not self.dir.is_dir():
            return []
        personas: list[Persona] = []
        for path in sorted(self.dir.glob("*.md")):
            parsed = parse_persona(path.read_text(encoding="utf-8"))
            if parsed is not None:
                personas.append(parsed)
        personas.sort(key=lambda p: (not p.default, p.id))
        return personas

    def get(self, persona_id: str) -> Persona | None:
        for persona in self.list():
            if persona.id == persona_id:
                return persona
        return None

    def default(self) -> Persona | None:
        for persona in self.list():
            if persona.default:
                return persona
        return None


class PersonaSelector:
    """自动切换：显式点名 > 关键词命中（平局 default 优先）> 默认人格。"""

    def __init__(self, library: PersonaLibrary) -> None:
        self.library = library

    def select(self, text: str, tier: IntentTier | None = None) -> Persona | None:
        """按本轮对话内容选人格；tier 预留（任务档位可作为平局提示，先不用）。"""
        personas = self.library.list()
        if not personas:
            return None
        explicit = self._explicit(text, personas)
        if explicit is not None:
            return explicit
        best: list[Persona] = []
        best_score = 0
        for persona in personas:
            score = sum(1 for phrase in persona.when if phrase and phrase in text)
            if score > best_score:
                best_score, best = score, [persona]
            elif score == best_score and score > 0:
                best.append(persona)
        if best:
            return min(best, key=lambda p: personas.index(p))
        return self.library.default()

    @staticmethod
    def _explicit(text: str, personas: list[Persona]) -> Persona | None:
        if not any(verb in text for verb in _SWITCH_VERBS):
            return None
        for persona in personas:
            if (persona.name and persona.name in text) or (
                persona.id and persona.id in text
            ):
                return persona
        return None