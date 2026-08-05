"""BGE-M3 tokenizer 感知的语义分块器。

设计：
1. 按中英文句子边界切句（。！？!?；;\n 等）
2. 用 BGE-M3 同源 tokenizer（XLM-RoBERTa）统计每句 token 数
3. 贪心累积句子直到达到 chunk_size，超长单句按 token 级硬切
4. 相邻 chunk 保留 overlap token 的重叠（默认 64），衔接上下文
5. 每个 chunk 记录原始字符偏移（char_start/char_end），供 Phase 4 引用溯源

tokenizer 为懒加载单例：只加载 tokenizer（约 20MB），不加载 BGE-M3 模型权重（Phase 4 才加载）。
"""

import os
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.exceptions import ServiceError

# 句子边界：以中英文标点/换行收尾的片段
_SENTENCE_BOUNDARY = re.compile(r"[^。！？!?；;\n]+[。！？!?；;\n]*")

_tokenizer: Any | None = None


@dataclass
class TextChunk:
    """一个分块：文本 + 原始字符偏移。"""

    index: int
    text: str
    char_start: int
    char_end: int


def get_tokenizer():
    """懒加载 BGE-M3 tokenizer（XLM-RoBERTa），全局单例。

    国内网络 huggingface.co 不可直连，默认走 hf-mirror.com 镜像
    （通过 settings.HF_ENDPOINT 配置，首次使用自动下载约 20MB）。
    """
    global _tokenizer
    if _tokenizer is None:
        os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
        if settings.HF_HOME:
            os.environ["HF_HOME"] = settings.HF_HOME
        try:
            from transformers import AutoTokenizer

            _tokenizer = AutoTokenizer.from_pretrained(settings.EMBEDDING_MODEL)
        except Exception as exc:
            raise ServiceError(f"BGE-M3 tokenizer 加载失败（首次使用需联网下载）: {exc}")
    return _tokenizer


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """按句子边界切分，返回 [(句子, 起始偏移, 结束偏移)]。"""
    return [
        (m.group().strip(), m.start(), m.end())
        for m in _SENTENCE_BOUNDARY.finditer(text)
        if m.group().strip()
    ]


def _token_count(tokenizer, sentence: str) -> int:
    """统计一句的 token 数（不含特殊 token）。"""
    return len(tokenizer.encode(sentence, add_special_tokens=False))


def _split_long_sentence(tokenizer, sentence: str, max_tokens: int) -> list[tuple[str, int]]:
    """超长单句按 token 级硬切，返回 [(片段, 相对偏移)]。"""
    tokens = tokenizer.encode(sentence, add_special_tokens=False)
    pieces: list[tuple[str, int]] = []
    pos = 0
    for start in range(0, len(tokens), max_tokens):
        piece = tokenizer.decode(tokens[start : start + max_tokens], skip_special_tokens=True)
        if not piece:
            continue
        idx = sentence.find(piece, pos)
        if idx == -1:
            idx = pos  # decode 后文本与原文有细微差异时顺序接续
        pieces.append((piece, idx))
        pos = idx + len(piece)
    return pieces


def split_text_into_chunks(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """将全文切分为语义分块。

    参数来自知识库配置（默认取全局配置 512/64）。
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP

    tokenizer = get_tokenizer()
    sentences = _split_sentences(text)
    if not sentences:
        return []

    # 预计算每句 token 数
    token_counts = [_token_count(tokenizer, s) for s, _, _ in sentences]

    chunks: list[TextChunk] = []
    i = 0
    while i < len(sentences):
        chunk_start = sentences[i][1]
        tokens_in_chunk = 0
        j = i
        # 贪心累积句子直到达到 chunk_size
        while j < len(sentences) and tokens_in_chunk + token_counts[j] <= chunk_size:
            tokens_in_chunk += token_counts[j]
            j += 1

        # 剩余句子都超长（单句 > chunk_size）：硬切当前句
        if j == i:
            for piece, rel_off in _split_long_sentence(tokenizer, sentences[i][0], chunk_size):
                piece_start = sentences[i][1] + rel_off
                chunks.append(
                    TextChunk(
                        index=len(chunks),
                        text=piece,
                        char_start=piece_start,
                        char_end=piece_start + len(piece),
                    )
                )
            i += 1
            continue

        chunk_text = text[chunk_start : sentences[j - 1][2]].strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=chunk_text,
                    char_start=chunk_start,
                    char_end=sentences[j - 1][2],
                )
            )

        # 计算 overlap：从上一 chunk 末尾往回补句子直到达到 overlap token 数
        overlap_tokens = 0
        k = j - 1
        while k >= i and overlap_tokens < chunk_overlap:
            overlap_tokens += token_counts[k]
            k -= 1
        i = k + 1 if k >= i else j  # k+1 起的句子并入下个 chunk 开头

    return chunks
