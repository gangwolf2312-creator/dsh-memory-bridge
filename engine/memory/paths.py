"""产物路径约束（§路径契约）：统一记忆树/知识库的落点，默认对齐 DSH home。

层级（优先级从高到低）：
  1. 显式传入（调用方指定 root，最高优先，测试/多实例用）
  2. 环境变量：DSH_MEMORY_ROOT / DSH_WIKI_ROOT（部署可自定义）
  3. DSH home：$DSH_HOME（空/空白视为未设，与 DSH home-paths 同规则）→ 兜底 ~/.dsh
  4. 默认子目录：<home>/memory-tree（记忆库）、<home>/memory-wiki（知识库）

对齐 DSH 官方规则（packages/util/home-paths/src/index.ts）：
  - 显式配置 > $DSH_HOME > ~/.dsh
  - 空/纯空白 $DSH_HOME 视为未设置（绝不落到奇怪路径）
  - 所有产物收敛在一个 home 根下，与 DSH 的 sessions/credentials 同级

约束（调用方必须遵守）：
  - 记忆库与知识库永远分离（两个 root，互不混写）
  - 明文卡与索引同根（.index/ 可重建，删了不丢明文）
  - 产物目录 gitignore（不进版本库）
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "DEFAULT_MEMORY_DIR_NAME",
    "DEFAULT_WIKI_DIR_NAME",
    "DSH_HOME_ENV",
    "MEMORY_ROOT_ENV",
    "WIKI_ROOT_ENV",
    "resolve_dsh_home",
    "resolve_memory_root",
    "resolve_wiki_root",
]

# 环境变量名（部署可自定义的旋钮）
DSH_HOME_ENV = "DSH_HOME"
MEMORY_ROOT_ENV = "DSH_MEMORY_ROOT"
WIKI_ROOT_ENV = "DSH_WIKI_ROOT"

# 默认子目录名（home 根下的固定子目录）
DEFAULT_MEMORY_DIR_NAME = "memory-tree"
DEFAULT_WIKI_DIR_NAME = "memory-wiki"


def resolve_dsh_home(env: dict[str, str] | None = None) -> Path:
    """解析 DSH home：显式 $DSH_HOME > 兜底 ~/.dsh（空/空白视为未设）。

    Args:
        env: 环境映射（默认 os.environ）；测试可注入。

    Returns:
        解析后的 home 根目录（绝对路径，不创建）。

    Note:
        输入可以是绝对/相对/~/ 形式；相对路径相对调用进程 cwd 解析为绝对
        （对齐 DSH home-paths：`resolveDshHome` 输出 `resolve()` 规范化绝对路径）。
        绝不在调用方之间传递相对 Path——不同 cwd 会解析到不同目录，造成"看似
        同一套记忆实际分裂"。
    """
    env = env if env is not None else os.environ
    raw = env.get(DSH_HOME_ENV, "")
    if raw and raw.strip():
        # 展开 ~/ 前缀（对齐 DSH home-paths 的 expandHomePath）
        if raw == "~":
            return Path.home().resolve()
        if raw.startswith("~/") or raw.startswith("~\\"):
            return (Path.home() / raw[2:]).resolve()
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".dsh").resolve()


def resolve_memory_root(
    explicit: str | Path | None = None, env: dict[str, str] | None = None
) -> Path:
    """解析记忆库 root：显式 > $DSH_MEMORY_ROOT > <dsh_home>/memory-tree。

    Args:
        explicit: 调用方显式指定的 root（最高优先）。
        env: 环境映射（默认 os.environ）；测试可注入。

    Returns:
        记忆库根目录（绝对路径，不创建；由 MemoryStore 初始化时 mkdir）。
    """
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip()).expanduser().resolve()
    env = env if env is not None else os.environ
    from_env = env.get(MEMORY_ROOT_ENV, "")
    if from_env and from_env.strip():
        return Path(from_env.strip()).expanduser().resolve()
    return resolve_dsh_home(env) / DEFAULT_MEMORY_DIR_NAME


def resolve_wiki_root(
    explicit: str | Path | None = None, env: dict[str, str] | None = None
) -> Path:
    """解析知识库 root：显式 > $DSH_WIKI_ROOT > <dsh_home>/memory-wiki。

    Args:
        explicit: 调用方显式指定的 root（最高优先）。
        env: 环境映射（默认 os.environ）；测试可注入。

    Returns:
        知识库根目录（绝对路径，不创建；由 WikiStore 初始化时 mkdir）。
    """
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip()).expanduser().resolve()
    env = env if env is not None else os.environ
    from_env = env.get(WIKI_ROOT_ENV, "")
    if from_env and from_env.strip():
        return Path(from_env.strip()).expanduser().resolve()
    return resolve_dsh_home(env) / DEFAULT_WIKI_DIR_NAME
