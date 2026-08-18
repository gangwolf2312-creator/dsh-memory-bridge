"""记忆闭环（DESIGN-v3 §2：记忆服务；M1.7 存储+检索，提取/注入管道后置）。
知识库支线（LLM Wiki）：WikiStore / WikiSearch，见 docs/WIKI-DESIGN.md。
"""

__version__ = "0.1.1"  # 版本号规矩（2026-08-19 起）：每次 bug 修复/功能更新随代码 bump 并打 vX.Y.Z tag

from memory.backends import (
    BackendError,
    CloudBackend,
    CloudConfig,
    ExtractConfig,
    LOCAL_PRESETS,
    LocalBackend,
    LocalConfig,
    MainModelBackend,
    MainModelConfig,
    resolve_local_config,
)
from memory.lemonade import (
    DEFAULT_PRESET_MODEL,
    LemonadeError,
    LemonadeManager,
    LemonadeStatus,
    ensure_local_ready,
    set_runner,
)
from memory.wiki import WikiSearch, WikiStore, split_spec_sections, wiki_id
from memory.govern import (
    GovernanceReport,
    apply_usage_feedback,
    card_usage,
    govern_injection,
)
from memory.paths import (
    DEFAULT_MEMORY_DIR_NAME,
    DEFAULT_WIKI_DIR_NAME,
    resolve_dsh_home,
    resolve_memory_root,
    resolve_wiki_root,
)
from memory.sanitize import SENSITIVE_KINDS, sanitize_for_cloud
from memory.search import MemorySearch, detect_feedback
from memory.service import MemoryService, build_extractor, load_extract_config
from memory.store import MemoryStore
from memory.strategy import (
    CloudStrategy,
    HybridStrategy,
    LocalStrategy,
    MainStrategy,
)
from memory.tokenize import tokenize

__all__ = [
    "DEFAULT_MEMORY_DIR_NAME",
    "DEFAULT_WIKI_DIR_NAME",
    "SENSITIVE_KINDS",
    "BackendError",
    "CloudBackend",
    "CloudConfig",
    "CloudStrategy",
    "ExtractConfig",
    "GovernanceReport",
    "HybridStrategy",
    "LocalBackend",
    "LOCAL_PRESETS",
    "LocalConfig",
    "LocalStrategy",
    "MainModelBackend",
    "MainModelConfig",
    "MainStrategy",
    "MemorySearch",
    "MemoryService",
    "MemoryStore",
    "apply_usage_feedback",
    "build_extractor",
    "card_usage",
    "detect_feedback",
    "govern_injection",
    "load_extract_config",
    "DEFAULT_PRESET_MODEL",
    "LemonadeError",
    "LemonadeManager",
    "LemonadeStatus",
    "ensure_local_ready",
    "resolve_local_config",
    "set_runner",
    "resolve_dsh_home",
    "resolve_memory_root",
    "resolve_wiki_root",
    "split_spec_sections",
    "wiki_id",
    "WikiSearch",
    "WikiStore",
    "sanitize_for_cloud",
    "tokenize",
]
