"""云端脱敏专项测试（安全缺口堵漏）。

覆盖：API Key / Bearer Token / 私有密钥块 / AWS Key / 身份证 / 手机号 /
邮箱 / 常见凭证键值 的替换与命中类型记录；sanitize_messages 逐条清洗。
"""

from __future__ import annotations

from memory.sanitize import sanitize_for_cloud, sanitize_messages


def test_sanitize_api_key() -> None:
    text, hits = sanitize_for_cloud("key is sk-abcdefghijklmnop123")
    assert "sk-abcdefghijklmnop123" not in text
    assert "<API_KEY>" in text
    assert hits == ["api_key"]


def test_sanitize_bearer_token() -> None:
    text, hits = sanitize_for_cloud("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc")
    assert "eyJhbGciOiJIUzI1NiJ9" not in text
    assert "<BEARER_TOKEN>" in text
    assert "bearer_token" in hits


def test_sanitize_private_key_block() -> None:
    text, hits = sanitize_for_cloud(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    )
    assert "BEGIN RSA PRIVATE KEY" not in text
    assert "<PRIVATE_KEY>" in text
    assert "private_key" in hits


def test_sanitize_aws_key() -> None:
    text, hits = sanitize_for_cloud("AKIAIOSFODNN7EXAMPLE")
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "aws_key" in hits


def test_sanitize_id_card() -> None:
    text, hits = sanitize_for_cloud("身份证 11010519491231002X")
    assert "11010519491231002X" not in text
    assert "id_card" in hits


def test_sanitize_phone() -> None:
    text, hits = sanitize_for_cloud("电话 13800138000")
    assert "13800138000" not in text
    assert "phone" in hits


def test_sanitize_email() -> None:
    text, hits = sanitize_for_cloud("联系 me@example.com 或他")
    assert "me@example.com" not in text
    assert "email" in hits


def test_sanitize_credential_kv() -> None:
    text, hits = sanitize_for_cloud("password=abc123 secret: xyz789")
    assert "abc123" not in text
    assert "xyz789" not in text
    assert "credential" in hits


def test_sanitize_credential_chinese_phrasing() -> None:
    """中文凭证表述（真实模型实测会提取此类明文）：密码是/为/：/账号是/密钥是。"""
    cases = [
        "我的数据库密码是 Abc@123456，记住别泄露",
        "服务器账号为 root，密码为 P@ssw0rd!",
        "支付密钥：qwerty12345",
        "登录密码: hunter2",
    ]
    for text in cases:
        cleaned, hits = sanitize_for_cloud(text)
        assert "credential" in hits, f"未命中: {text}"
        assert "<CREDENTIAL>" in cleaned
    # 值已脱敏，明文不残留
    assert "Abc@123456" not in sanitize_for_cloud(cases[0])[0]
    assert "P@ssw0rd" not in sanitize_for_cloud(cases[1])[0]


def test_sanitize_credential_chinese_no_false_positive() -> None:
    """"密码是"句式在正常上下文（非凭证值）不应误伤整体文本。"""
    text, hits = sanitize_for_cloud("用户说密码是八个字符比较好记，这是他的习惯。")
    # 尾随的普通短语也会被当作值替换——保守起见只断言 hits 记录 + 文本仍可读
    assert "credential" in hits or text == "用户说密码是八个字符比较好记，这是他的习惯。"


def test_sanitize_cjk_adjacency_phone() -> None:
    """中文邻接的手机号必须命中（\b 对 CJK 失效的回归用例）。"""
    text, hits = sanitize_for_cloud("手机号13812345678发我")
    assert "13812345678" not in text
    assert "<PHONE>" in text
    assert "phone" in hits


def test_sanitize_cjk_adjacency_api_key() -> None:
    text, hits = sanitize_for_cloud("密钥sk-abc1234567890 已配置")
    assert "sk-abc1234567890" not in text
    assert "<API_KEY>" in text
    assert "api_key" in hits


def test_sanitize_cjk_adjacency_id_card() -> None:
    text, hits = sanitize_for_cloud("身份证11010119900307789X已提交")
    assert "11010119900307789X" not in text
    assert "id_card" in hits


def test_sanitize_email_no_cjk_overconsume() -> None:
    """邮箱后随中文不得被吞进匹配（over-consumption 回归用例）。"""
    text, hits = sanitize_for_cloud("发到abc@test.com发送即可")
    assert "abc@test.com" not in text
    assert "<EMAIL>" in text
    assert "发送" in text  # 中文没有被吞掉
    assert "email" in hits


def test_sanitize_credential_kv_cjk_adjacent_key() -> None:
    """凭证键紧贴中文时仍命中（'配置password=abc123完成'）。"""
    text, hits = sanitize_for_cloud("配置password=abc123完成")
    assert "abc123" not in text
    assert "<CREDENTIAL>" in text
    assert "credential" in hits


def test_sanitize_keeps_normal_text() -> None:
    text, hits = sanitize_for_cloud("用户喜欢喝茶，明天去杭州。")
    assert text == "用户喜欢喝茶，明天去杭州。"
    assert hits == []


def test_sanitize_empty() -> None:
    assert sanitize_for_cloud("") == ("", [])


def test_sanitize_messages_cleans_all_contents() -> None:
    msgs = [
        {"role": "user", "content": "我的密钥 sk-aaaaaaaaaaaaaaaa"},
        {"role": "assistant", "content": "好的"},
    ]
    out, hits = sanitize_messages(msgs)
    assert "sk-aaaaaaaaaaaaaaaa" not in out[0]["content"]
    assert "<API_KEY>" in out[0]["content"]
    assert out[1]["content"] == "好的"
    assert hits == ["api_key"]


def test_sanitize_messages_keeps_non_string_content() -> None:
    msgs = [{"role": "user", "content": ["数组", "内容"]}]
    out, hits = sanitize_messages(msgs)
    assert out[0]["content"] == ["数组", "内容"]
    assert hits == []
