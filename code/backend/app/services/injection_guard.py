"""提示注入防御：RAG 场景的检测与过滤（提示词工程学习路线·阶段 3 配套实现）。

设计原则（学习路线 3.4 第三层）：
- 纯关键词正则容易误杀或绕过，只能当"第一道便宜防线"
- 因此这里只匹配**强特征长短语**（"忽略之前的指令"类完整指令句），
  短词如"忽略/无视"单独出现不命中，降低正常文档误报率
- 编码绕过（base64 / hex）做二次解码检测

防御接入点（附加式，不改变原有流程）：
1. 上传环节：document_tasks 解析后扫描全文（命中记日志，不阻断）
2. 检索环节：pipeline 对检索结果过滤（剔除含注入特征的 chunk）
3. 生成环节：Spotlighting 标记见 generator.py / tools.py
4. 审计：pipeline 记录检索片段与检测结果（qa:retrieval）
"""

import base64
import binascii
import logging
import re

logger = logging.getLogger(__name__)

# ========== 强特征注入模式（长短语 → 低误报） ==========

_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    # 指令覆盖：要求忽略系统/上下文指令
    ("指令覆盖", re.compile(r"忽略(?:之前|上述|以上)?(?:的)?(?:所有|全部|任何)?(?:指令|提示|要求|规则)")),
    ("指令覆盖", re.compile(r"无视(?:之前|上述|以上)?(?:的)?(?:所有|全部|任何)?(?:指令|提示|要求|规则)")),
    ("指令覆盖", re.compile(r"(?:override|ignore|disregard)\s*(?:previous|above|all|prior)", re.IGNORECASE)),
    # 角色劫持
    ("角色劫持", re.compile(r"你现在(?:是|变成|扮演)(?:一个|一位|个)?(?:不受限制|没有限制|自由|无所不能)")),
    ("越狱", re.compile(r"jailbreak|越狱|破解系统", re.IGNORECASE)),
    # 系统提示词泄露试探（LLM07）
    ("系统提示词泄露", re.compile(r"(?:system\s*prompt|系统提示词|系统指令)\s*(?:是|是什么|是什么内容|是什么?|的内容|给我看|告诉我|输出|暴露)", re.IGNORECASE)),
    ("系统提示词泄露", re.compile(r"说出你的(?:系统提示词|system\s*prompt|秘密|内部指令)", re.IGNORECASE)),
    # 间接注入：要求把文档内容当指令执行
    ("间接注入", re.compile(r"把(?:文档|资料|检索到的内容|上文|以上内容)(?:中|内)?的?(?:内容|指令|规则).{0,10}(?:当作|作为|当成)(?:指令|规则|提示词|系统提示)")),
]

# 疑似编码绕过的最小长度与字符集比例（短文本不做判定，避免误伤）
_ENCODED_MIN_LEN = 40
_BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")


def scan_text(text: str) -> list[str]:
    """扫描文本，返回命中的注入攻击类别列表（空列表 = 未命中）。

    Args:
        text: 待检测文本（文档全文 / chunk / 用户输入）

    Returns:
        list[str]: 命中的攻击类别名，如 ["指令覆盖", "系统提示词泄露"]
    """
    if not text:
        return []
    hits: list[str] = []
    # 1. 明文强特征匹配
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(name)
    # 2. 编码绕过：长 base64 / hex 串尝试解码后再匹配一次
    stripped = text.strip()
    if len(stripped) >= _ENCODED_MIN_LEN and _looks_encoded(stripped):
        decoded = _try_decode(stripped)
        if decoded:
            for name, pattern in _INJECTION_PATTERNS:
                if pattern.search(decoded) and name not in hits:
                    hits.append(name)
    return hits


def _looks_encoded(text: str) -> bool:
    """粗判疑似 base64 / hex：字符集符合且比例足够。"""
    if re.fullmatch(r"[0-9a-fA-F]+", text):
        return True  # 长 hex
    if len(text) % 4 == 0:
        chars = sum(1 for ch in text if ch in _BASE64_CHARS)
        return chars / max(len(text), 1) >= 0.95
    return False


def _try_decode(text: str) -> str | None:
    """尝试 base64 / hex 解码，失败返回 None。"""
    try:
        return base64.b64decode(text).decode("utf-8", errors="ignore")
    except (binascii.Error, ValueError):
        pass
    try:
        return bytes.fromhex(text).decode("utf-8", errors="ignore")
    except (binascii.Error, ValueError):
        return None


def filter_injection(candidates: list[dict]) -> tuple[list[dict], list[str]]:
    """过滤检索结果：剔除含注入特征的 chunk（附加式防御，不影响其余结果）。

    Args:
        candidates: hybrid_search 的检索结果列表

    Returns:
        (kept, dropped): 安全结果列表 + 被剔除的 chunk_id 列表（用于审计）
    """
    kept: list[dict] = []
    dropped: list[str] = []
    for c in candidates:
        hits = scan_text(c.get("text", ""))
        if hits:
            cid = c.get("chunk_id", "") or c.get("text", "")[:60]
            dropped.append(cid)
            logger.warning(
                "检索结果剔除注入特征 chunk: id=%s 命中=%s", cid, ",".join(hits)
            )
        else:
            kept.append(c)
    return kept, dropped


def scan_answer(answer: str) -> list[str]:
    """输出侧校验：扫描模型输出是否泄露密钥/系统提示词（附加式，不阻断）。

    命中仅记日志与审计，由上层处理；这里保持 fail-open。
    """
    hits = scan_text(answer)
    # 密钥模式：OpenAI 风格 sk-xxx / 长密钥串
    if re.search(r"\bsk-[A-Za-z0-9]{16,}\b", answer):
        hits.append("密钥泄露")
    return hits
