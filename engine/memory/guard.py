"""提取门卫（零 LLM）：决定哪些回合值得进 LLM 提取队列，寒暄直接跳过（§9.7 成本控制）。

每回合 LLM 提取是后台主要成本，但寒暄/无新事实的回合不值得花这个 token。
门卫用确定性启发式粗筛：有事实嫌疑才入队；无嫌疑的 run 照常落盘（对话永不丢，
A5），但标记 status=skipped，不触发提取。宁多勿漏——误放行只多花一次提取，
漏放行才会丢事实。
"""

from __future__ import annotations

import re

__all__ = ["should_extract"]

MIN_LEN = 6          # 用户消息短于 → 视为无信息（除非有回复可读）
LONG_LEN = 20        # 长句默认有内容
REPLY_LONG = 50      # 分身长回复视为有内容

# 指令触发词（与 rules.py / confidence.py 同源）
_DIRECTIVE = ("记住", "记下", "记牢", "别忘了", "别忘", "记一下")

# 事实提示词：出现任一 → 值得提取（宁多勿漏）
_FACT_HINTS = (
    "项目", "部署", "配置", "端口", "地址", "密码", "账号", "买了", "约了",
    "定了", "预约", "搬家", "装修", "安装", "下载", "更新", "升级", "付款",
    "收到", "搞定", "完成", "安排", "计划", "决定", "开始", "结束", "取消",
    "改成", "换成", "不要", "别用", "喜欢", "偏好", "习惯",
    "每天", "每晚", "经常", "总是", "一般",
)

_TIME_WORDS = (
    "今天", "明天", "后天", "下周", "上周", "本周", "周五", "周一",
    "周二", "周三", "周四", "周六", "周日",
)

# 寒暄/无信息量词表（命中且无其他信号 → 跳过）
_CHIT_CHAT = (
    "好的", "嗯", "嗯嗯", "谢谢", "多谢", "没问题", "可以", "哈哈",
    "知道了", "了解", "明白", "哦", "好吧", "okk", "ok", "好",
    "再见", "拜拜", "早上好", "晚安", "在吗",
)

_NUM_RE = re.compile(r"[0-9]+")


def should_extract(user_text: str, reply_text: str) -> tuple[bool, str]:
    """判定回合是否值得 LLM 提取。返回 (值得提取, 跳过原因；值得时原因为空串)。

    检查顺序（事实信号在前，寒暄判断在后）：指令 > 数字 > 专名提示 > 时间词 >
    长句/长回复 > 寒暄词 > 默认跳过。
    """
    u = (user_text or "").strip()
    r = (reply_text or "").strip()
    if not u:
        return False, "空用户消息"
    if len(u) < MIN_LEN and not r:
        return False, "过短且无回复"
    if any(t in u for t in _DIRECTIVE):
        return True, ""
    if _NUM_RE.search(u):
        return True, ""
    if any(h in u for h in _FACT_HINTS):
        return True, ""
    if any(w in u for w in _TIME_WORDS):
        return True, ""
    if len(u) >= LONG_LEN or len(r) >= REPLY_LONG:
        return True, ""
    if any(c in u for c in _CHIT_CHAT):
        return False, "寒暄"
    return False, "无事实信号"


def extract_priority(user_text: str, reply_text: str) -> int:
    """NPU 慢速下的提取优先级：1=高优先（directive/关键事实先行），0=普通。

    高优先判定（命中任一）：
    - 指令触发词（记住/记下/记牢/别忘了/记一下/记住教训）——用户明确要求记住
    - 关键事实信号（账号/密码/端口/截止/项目/部署等强信号词）
    目的：积压时高价值回合不被 FIFO 堵在后面（NPU 吞吐有限）。
    """
    u = (user_text or "").strip()
    if any(t in u for t in _DIRECTIVE):
        return 1
    # 强信号词（subset of _FACT_HINTS，语义更强）
    for strong in ("项目", "部署", "配置", "端口", "密码", "账号", "截止", "地址", "买了", "约了", "预约"):
        if strong in u:
            return 1
    return 0
