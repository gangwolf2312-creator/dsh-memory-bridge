"""画像层（B3，ADR-0020）：用户模型 = 8 轴人格 + <=200 tok 摘要 + 草稿/审批。

存储（memory root 内，明文事实来源）：
  profiles/PROFILE.md            已审批主画像（F 桶每轮注入）
  profiles/drafts/*.md           蒸馏草稿（待人工审批）
  profiles/rejected/*.md         驳回草稿（明文保留可找回）
消费：approved 摘要 <=200 tok 进 F 桶（assemble_context profile_provider）；
人格多边形 8 轴 0-1 分数（MBTI 四维 + 4 行为轴），雷达渲染，F 桶只注入紧凑文本行。
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path

PROFILE_DIR = "profiles"
PROFILE_FILE = "PROFILE.md"
DRAFT_DIR = "drafts"
DRAFT_PREFIX = "PROFILE.draft-"
REJECTED_DIR = "rejected"

# 画像摘要进 F 桶的预算上限（ADR-0020：<=200 tok，token 契约测试锁定）
PROFILE_SUMMARY_BUDGET_TOKENS = 200

# 人格 8 轴：MBTI 四维 + 4 行为轴（轴序固定，雷达/注入/蒸馏共用）
AXIS_DEFS: tuple[tuple[str, str, str, str], ...] = (
    ("ei", "外向-内向", "外向", "内向"),
    ("sn", "感觉-直觉", "感觉", "直觉"),
    ("tf", "思考-情感", "思考", "情感"),
    ("jp", "判断-知觉", "判断", "知觉"),
    ("task", "任务-关系", "任务", "关系"),
    ("risk", "保守-进取", "保守", "进取"),
    ("style", "简洁-详尽", "简洁", "详尽"),
    ("form", "结构-发散", "结构", "发散"),
)


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class Dimension:
    """一条人格轴：0=左锚，1=右锚（如 ei: 0=外向 -> 1=内向）。"""

    key: str
    label: str
    value: float  # 0.0-1.0
    anchor: str = ""  # 显示侧（右侧锚点名，如"内向"）


@dataclass(frozen=True, slots=True)
class Profile:
    """一份画像摘要（approved 或 draft），可带人格多边形与溯源。"""

    summary: str
    updated_at: str = ""
    version: int = 1
    status: str = "draft"  # draft | approved
    source_refs: tuple[str, ...] = ()  # 溯源：事件卡 / 日记录路径
    mbti: str = ""  # 如 "ISTJ"（证据不足时为空 -> 不更新人格）
    dimensions: tuple[Dimension, ...] = ()  # 8 轴分数（雷达多边形）
    trace_event_id: str = ""  # B3：溯源（蒸馏源回合根 event_id，回合级）

    def render_f_block(self) -> str:
        """F 桶注入文本：摘要 + 紧凑人格行（摘要 <=200 tok + 人格 <=~120 tok）。"""
        block = self.summary.strip()
        if self.mbti or self.dimensions:
            axes = " ".join(f"{d.key}={d.value:.2f}" for d in self.dimensions)
            mbti_part = self.mbti or "?"
            block += f"\n人格多边形：{mbti_part}（{axes}）"
        return block

    def to_md(self) -> str:
        src = "\n".join(f"  - {ref}" for ref in self.source_refs)
        refs_block = src if src else "  - (无)"
        dims = "\n".join(
            f"  - key: {d.key}  label: {d.label}  value: {d.value:.2f}  anchor: {d.anchor}"
            for d in self.dimensions
        )
        dims_block = dims if dims else "  - (无)"
        return "\n".join(
            [
                "---",
                f"version: {self.version}",
                f"updated_at: {self.updated_at}",
                f"status: {self.status}",
                f"mbti: {self.mbti}",
                f"trace_event_id: {self.trace_event_id}",
                "dimensions:",
                dims_block,
                "source_refs:",
                refs_block,
                "---",
                "# CGAOS 画像摘要",
                "",
                self.summary.strip(),
                "",
            ]
        )


_DIM_LINE_RE = re.compile(
    r"key:\s*(\S+)\s+label:\s*(.+?)\s+value:\s*([0-9.]+)\s+anchor:\s*(\S+)"
)


def parse_profile(text: str) -> Profile | None:
    """解析明文画像（缺 summary / 缺分隔线返回 None）。"""
    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---")
    head, sep, body = rest.partition("\n---\n")
    if not sep:
        return None
    fields: dict[str, list[str]] = {}
    dim_lines: list[str] = []
    current: str | None = None
    for line in head.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("-") and current is not None:
            if current == "dimensions":
                dim_lines.append(line[1:].strip())
            else:
                fields[current].append(line[1:].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            current = key.strip()
            fields[current] = [value.strip()] if value.strip() else []
    summary = body.strip()
    if summary.startswith("# CGAOS 画像摘要"):
        summary = summary[len("# CGAOS 画像摘要") :].strip()
    if not summary:
        return None

    def _text(key: str) -> str:
        values = fields.get(key)
        return values[0] if values else ""

    def _int(key: str, default: int) -> int:
        try:
            return int(_text(key))
        except ValueError:
            return default

    dimensions: list[Dimension] = []
    for line in dim_lines:
        match = _DIM_LINE_RE.search(line)
        if not match:
            continue
        try:
            value = float(match.group(3))
        except ValueError:
            continue
        if not (0.0 <= value <= 1.0):
            continue
        dimensions.append(
            Dimension(
                key=match.group(1),
                label=match.group(2),
                value=value,
                anchor=match.group(4),
            )
        )

    return Profile(
        summary=summary,
        updated_at=_text("updated_at"),
        version=_int("version", 1),
        status=_text("status") or "draft",
        source_refs=tuple(r for r in fields.get("source_refs", []) if r),
        mbti=_text("mbti"),
        dimensions=tuple(dimensions),
        trace_event_id=_text("trace_event_id"),
    )


class ProfileStore:
    """画像读写（纯明文，无索引依赖，可独立测试）。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.dir = self.root / PROFILE_DIR
        self.draft_dir = self.dir / DRAFT_DIR

    def path(self) -> Path:
        return self.dir / PROFILE_FILE

    def load(self) -> Profile | None:
        path = self.path()
        if not path.is_file():
            return None
        return parse_profile(path.read_text(encoding="utf-8"))

    def save(self, profile: Profile, *, approve: bool = False) -> Path:
        """写 PROFILE.md；approve=True 时 status=approved 并基于当前版本 +1。"""
        self.dir.mkdir(parents=True, exist_ok=True)
        current = self.load()
        version = profile.version
        if approve:
            version = (current.version + 1) if current is not None else 1
        final = Profile(
            summary=profile.summary,
            updated_at=now_iso(),
            version=version,
            status="approved" if approve else profile.status,
            source_refs=profile.source_refs,
            mbti=profile.mbti,
            dimensions=profile.dimensions,
            trace_event_id=profile.trace_event_id,
        )
        path = self.path()
        path.write_text(final.to_md(), encoding="utf-8")
        return path

    # —— 草稿（蒸馏产出，待人工审批）——

    def write_draft(self, profile: Profile) -> Path:
        self.draft_dir.mkdir(parents=True, exist_ok=True)
        ts = now_iso().replace(":", "").replace("+", "Z")
        path = self.draft_dir / f"{DRAFT_PREFIX}{ts}.md"
        path.write_text(profile.to_md(), encoding="utf-8")
        return path

    def list_drafts(self) -> list[tuple[str, Profile]]:
        if not self.draft_dir.is_dir():
            return []
        result: list[tuple[str, Profile]] = []
        for path in sorted(self.draft_dir.glob(f"{DRAFT_PREFIX}*.md")):
            parsed = parse_profile(path.read_text(encoding="utf-8"))
            if parsed is not None:
                result.append((path.name, parsed))
        return result

    def read_draft(self, draft_id: str) -> Profile | None:
        path = self.draft_dir / draft_id
        if not path.is_file():
            return None
        return parse_profile(path.read_text(encoding="utf-8"))

    def approve(self, draft_id: str) -> Profile:
        """审批：草稿 -> PROFILE.md（status=approved，version+1）；草稿保留可找回。"""
        draft = self.read_draft(draft_id)
        if draft is None:
            raise KeyError(f"画像草稿不存在: {draft_id}")
        self.save(draft, approve=True)
        approved = self.load()
        if approved is None:  # 理论不可达（刚写入）
            raise KeyError(f"画像审批后读取失败: {draft_id}")
        return approved

    def reject(self, draft_id: str) -> Path:
        """驳回：草稿移入 profiles/rejected/（明文保留可找回）。"""
        src = self.draft_dir / draft_id
        if not src.is_file():
            raise KeyError(f"画像草稿不存在: {draft_id}")
        rejected_dir = self.dir / REJECTED_DIR
        rejected_dir.mkdir(parents=True, exist_ok=True)
        dst = rejected_dir / draft_id
        src.replace(dst)
        return dst