"""云端脱敏（安全缺口堵漏）：发送到外部云端前的敏感信息清洗。

本地轨（Lemonade Server / 本地模型端点）不出网，无需脱敏；
云端轨（通用 OpenAI 兼容 API / 云端独立模型提取）会把对话与工具输出
发给第三方服务器，必须先过本模块：命中即替换为占位符，并把命中类型
记录进审计（decision_log / last_sanitize_hits），让用户感知"哪些内容
被脱过敏"。

设计取舍：脱敏会轻微降低提取质量（占位符可能进记忆卡），但保证密钥、
身份证等凭证不以明文离开本机；宁可占位符，不可泄漏。
"""

from __future__ import annotations

import re

__all__ = ["SENSITIVE_KINDS", "sanitize_for_cloud", "sanitize_messages"]

SENSITIVE_KINDS: tuple[str, ...] = (
    "api_key",
    "bearer_token",
    "private_key",
    "aws_key",
    "id_card",
    "phone",
    "email",
    "credential",
)

# (正则, 占位符, 命中类型)：顺序即优先级，先命中的先替换
#
# 边界断言说明（B1 修复）：Python 的 \b 把 CJK 字符视为 \w，导致
# "手机号13812345678发我" 这类中文邻接敏感信息完全漏配（两侧都是 \w，无边界）。
# 统一改用 ASCII 字母数字边界断言：前界 (?<![A-Za-z0-9])、后界 (?![A-Za-z0-9])，
# CJK 属于合法边界，敏感值照常命中；同时邮箱域名字符集收窄为 ASCII，
# 避免 "abc@test.com发送" 把后随中文吞进匹配（over-consumption）。
_BEFORE = r"(?<![A-Za-z0-9])"
_AFTER = r"(?![A-Za-z0-9])"

_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # OpenAI/通用 API Key：sk-...（8 位以上）
    (re.compile(rf"(?i){_BEFORE}sk-[A-Za-z0-9_-]{{8,}}{_AFTER}"), "<API_KEY>", "api_key"),
    # Bearer/Token 明文（12 位以上，避免误伤短词）
    (
        re.compile(rf"(?i){_BEFORE}(?:Bearer|Token)\s+[A-Za-z0-9._~+/=-]{{12,}}{_AFTER}"),
        "<BEARER_TOKEN>",
        "bearer_token",
    ),
    # 私有密钥块
    (
        re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
        "<PRIVATE_KEY>",
        "private_key",
    ),
    # AWS Access Key
    (re.compile(rf"{_BEFORE}AKIA[0-9A-Z]{{16}}{_AFTER}"), "<AWS_ACCESS_KEY>", "aws_key"),
    # 身份证号（18 位，末位可为 X）
    (re.compile(rf"{_BEFORE}\d{{17}}[\dXx]{_AFTER}"), "<ID_CARD>", "id_card"),
    # 中国大陆手机号
    (re.compile(rf"{_BEFORE}1[3-9]\d{{9}}{_AFTER}"), "<PHONE>", "phone"),
    # 邮箱（仅 ASCII 字符集，避免吞并后随中文）
    (
        re.compile(rf"{_BEFORE}[A-Za-z0-9._+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+{_AFTER}"),
        "<EMAIL>",
        "email",
    ),
    # 常见凭证键值：password=... / secret: ... / api_key = ...
    (
        re.compile(
            rf"(?i){_BEFORE}(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token){_AFTER}"
            r"\s*[=:]\s*[\"']?[^\s\"',}]+"
        ),
        "<CREDENTIAL>",
        "credential",
    ),
    # 中文凭证表述：密码是 xxx / 账号为 xxx / 密钥：xxx（真实模型实测会提取此类明文）
    (
        re.compile(
            r"(?i)(?:密码|口令|账号|用户名|密钥|登录密码|token|secret)"
            r"\s*(?:是|为|[:：=])\s*[\"']?[^\s，。；;,:：\"']+"
        ),
        "<CREDENTIAL>",
        "credential",
    ),
]


def sanitize_for_cloud(text: str) -> tuple[str, list[str]]:
    """清洗单段文本中的敏感信息。

    返回 (脱敏文本, 命中类型列表，按首次命中顺序去重)。
    命中类型可写入审计：用户据此知道本次云端请求脱过哪些类。
    """
    if not text:
        return text, []
    out = text
    hits: list[str] = []
    for pattern, placeholder, kind in _PATTERNS:
        new, n = pattern.subn(placeholder, out)
        if n:
            hits.append(kind)
            out = new
    return out, list(dict.fromkeys(hits))


def sanitize_messages(
    messages: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[str]]:
    """对 OpenAI 风格 messages 的 content 逐条脱敏。

    返回 (脱敏后 messages, 命中类型列表)；非字符串 content 原样保留。
    """
    hits: list[str] = []
    out: list[dict[str, object]] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            cleaned, kinds = sanitize_for_cloud(content)
            if kinds:
                hits.extend(kinds)
            msg = {**msg, "content": cleaned}
        out.append(msg)
    return out, list(dict.fromkeys(hits))
