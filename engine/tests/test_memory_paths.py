"""路径契约测试（§路径契约）：默认对齐 DSH home、可自定义、空值兜底。"""

from __future__ import annotations

from pathlib import Path

from memory.paths import (
    DSH_HOME_ENV,
    DEFAULT_MEMORY_DIR_NAME,
    DEFAULT_WIKI_DIR_NAME,
    resolve_dsh_home,
    resolve_memory_root,
    resolve_wiki_root,
)


def test_default_home_falls_back_to_homedir_dsh(tmp_path) -> None:
    """无 $DSH_HOME → 兜底 ~/.dsh（对齐 DSH home-paths 规则）。"""
    env = {"HOME": str(tmp_path)}  # Windows homedir 读 USERPROFILE，但本函数用 Path.home()
    home = resolve_dsh_home(env)
    # 空 DSH_HOME 视为未设 → 兜底 homedir/.dsh
    assert home.name == ".dsh"


def test_empty_dsh_home_treated_as_unset(tmp_path) -> None:
    """空/纯空白 $DSH_HOME 视为未设 → 兜底默认（对齐 DSH 规则，绝不落到奇怪路径）。"""
    for blank in ("", "   "):
        env = {DSH_HOME_ENV: blank}
        assert resolve_dsh_home(env) == Path.home() / ".dsh"
        assert resolve_memory_root(env=env) == Path.home() / ".dsh" / DEFAULT_MEMORY_DIR_NAME
        assert resolve_wiki_root(env=env) == Path.home() / ".dsh" / DEFAULT_WIKI_DIR_NAME


def test_dsh_home_env_used() -> None:
    """$DSH_HOME 生效 → 记忆/知识库落在 home 下的默认子目录。"""
    from memory.paths import DSH_HOME_ENV

    env = {DSH_HOME_ENV: r"C:\harness-home"}
    assert resolve_dsh_home(env) == Path(r"C:\harness-home")
    assert resolve_memory_root(env=env) == Path(r"C:\harness-home") / DEFAULT_MEMORY_DIR_NAME
    assert resolve_wiki_root(env=env) == Path(r"C:\harness-home") / DEFAULT_WIKI_DIR_NAME


def test_tilde_expansion() -> None:
    """~/ 前缀展开为 homedir（对齐 DSH expandHomePath）。"""
    from memory.paths import DSH_HOME_ENV

    env = {DSH_HOME_ENV: "~/.dsh"}
    assert resolve_dsh_home(env) == Path.home() / ".dsh"


def test_memory_wiki_roots_always_separate() -> None:
    """记忆库与知识库永远分离（两个独立 root，互不混写）。"""
    from memory.paths import DSH_HOME_ENV

    env = {DSH_HOME_ENV: r"D:\data\dsh"}
    memory = resolve_memory_root(env=env)
    wiki = resolve_wiki_root(env=env)
    assert memory != wiki
    assert memory.name == DEFAULT_MEMORY_DIR_NAME
    assert wiki.name == DEFAULT_WIKI_DIR_NAME


def test_env_override_wins_over_default() -> None:
    """环境变量自定义 root 优先于默认子目录。"""
    from memory.paths import DSH_HOME_ENV, MEMORY_ROOT_ENV, WIKI_ROOT_ENV

    env = {
        DSH_HOME_ENV: r"C:\harness-home",
        MEMORY_ROOT_ENV: r"D:\custom\mem",
        WIKI_ROOT_ENV: r"D:\custom\wiki",
    }
    assert resolve_memory_root(env=env) == Path(r"D:\custom\mem")
    assert resolve_wiki_root(env=env) == Path(r"D:\custom\wiki")


def test_explicit_wins_over_everything() -> None:
    """显式传入最高优先（测试/多实例用）。"""
    from memory.paths import MEMORY_ROOT_ENV, WIKI_ROOT_ENV

    env = {MEMORY_ROOT_ENV: r"D:\env-mem", WIKI_ROOT_ENV: r"D:\env-wiki"}
    assert resolve_memory_root(explicit=r"D:\explicit-mem", env=env) == Path(r"D:\explicit-mem")
    assert resolve_wiki_root(explicit=r"D:\explicit-wiki", env=env) == Path(r"D:\explicit-wiki")


def test_blank_explicit_treated_as_unset() -> None:
    """空/空白显式值视为未设 → 回落环境变量/默认。"""
    from memory.paths import DSH_HOME_ENV

    env = {DSH_HOME_ENV: r"C:\harness-home"}
    assert resolve_memory_root(explicit="  ", env=env) == Path(r"C:\harness-home") / DEFAULT_MEMORY_DIR_NAME


def test_relative_explicit_resolved_to_absolute(tmp_path) -> None:
    """相对输入 → 立即解析为绝对（相对调用 cwd），绝不保留相对 Path。"""
    import os

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        rel = resolve_memory_root(explicit="data/mem")
        assert rel == (tmp_path / "data/mem").resolve()
        assert rel.is_absolute()
        assert not str(rel).startswith("data")  # 不是裸相对
    finally:
        os.chdir(old_cwd)


def test_relative_env_root_resolved_to_absolute(tmp_path) -> None:
    """环境变量给相对路径 → 同样绝对化（防不同 cwd 下分裂）。"""
    import os

    from memory.paths import DSH_HOME_ENV, MEMORY_ROOT_ENV, WIKI_ROOT_ENV

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        env = {
            DSH_HOME_ENV: str(tmp_path / "home"),
            MEMORY_ROOT_ENV: "rel-mem",
            WIKI_ROOT_ENV: "rel-wiki",
        }
        assert resolve_memory_root(env=env) == (tmp_path / "rel-mem").resolve()
        assert resolve_wiki_root(env=env) == (tmp_path / "rel-wiki").resolve()
    finally:
        os.chdir(old_cwd)


def test_tilde_in_env_and_explicit() -> None:
    """~/ 展开在环境变量与显式输入中都生效（对齐 expandHomePath）。"""
    from memory.paths import MEMORY_ROOT_ENV

    env = {MEMORY_ROOT_ENV: "~/mem"}
    assert resolve_memory_root(env=env) == (Path.home() / "mem").resolve()
    assert resolve_memory_root(explicit="~/wiki") == (Path.home() / "wiki").resolve()


def test_default_home_is_absolute() -> None:
    """兜底 ~/.dsh 与默认子目录都是绝对路径。"""
    assert resolve_dsh_home({}).is_absolute()
    assert resolve_memory_root(env={}).is_absolute()
    assert resolve_wiki_root(env={}).is_absolute()
