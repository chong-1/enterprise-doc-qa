"""RAG 检索质量评估脚本。

评估指标：
  - Recall@5: 前 5 个检索结果中包含相关文档的比例
  - MRR (Mean Reciprocal Rank): 第一个相关结果排名的倒数均值
  - Faithfulness: LLM 评判答案是否忠实于检索到的上下文（可选）

用法:
    python scripts/eval_rag.py --kb-id 5

依赖：需要有一个已完成的 KB（文档 embedding 已入库）。
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rag.pipeline import RAGPipeline
from app.services.rag import retriever
from app.services.llm import get_llm_backend
from app.services.llm.base import ChatMessage

# ====== 测试问题集 ======
# 每个问题标注了预期出现在检索结果中的关键词（用于判断 Recall）
# 你需要根据实际文档内容修改这些关键词！
DEFAULT_QUESTIONS = [
    {
        "question": "文档的主要内容是什么？",
        "relevant_keywords": [],  # 通用问题，不标关键词
    },
    {
        "question": "文档中提到了哪些关键数据或指标？",
        "relevant_keywords": [],
    },
    {
        "question": "文档的结论或建议是什么？",
        "relevant_keywords": [],
    },
]


async def evaluate_retrieval(kb_id: int, test_questions: list[dict]) -> dict:
    """对每个问题执行混合检索，计算 Recall@5 和 MRR。"""

    results = []
    total_recall_5 = 0
    total_mrr = 0

    for i, item in enumerate(test_questions):
        q = item["question"]
        keywords = item.get("relevant_keywords", [])

        t0 = time.monotonic()
        candidates = retriever.hybrid_search(kb_id, q)
        top5 = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:5]
        elapsed = int((time.monotonic() - t0) * 1000)

        # Recall@5: 哪些关键词至少出现在一个 top-5 chunk 中
        recall_hits = 0
        if keywords:
            # 收集 top-5 的全部文本
            top5_text = " ".join(c.get("text", "") for c in top5).lower()
            for kw in keywords:
                if kw.lower() in top5_text:
                    recall_hits += 1
        recall_5 = recall_hits / len(keywords) if keywords else 1.0

        # MRR: 第一个匹配任意关键词的 chunk 排名倒数
        mrr = 0.0
        if keywords:
            for rank, c in enumerate(top5, 1):
                text = c.get("text", "").lower()
                if any(kw.lower() in text for kw in keywords):
                    mrr = 1.0 / rank
                    break

        total_recall_5 += recall_5
        total_mrr += mrr

        results.append({
            "question": q[:80],
            "recall@5": round(recall_5, 3),
            "mrr": round(mrr, 3),
            "top5_scores": [round(c["score"], 4) for c in top5],
            "top5_sources": [c.get("metadata", {}).get("filename", "?") for c in top5],
            "latency_ms": elapsed,
            "total_candidates": len(candidates),
        })

    n = len(test_questions)
    return {
        "kb_id": kb_id,
        "num_questions": n,
        "avg_recall_at_5": round(total_recall_5 / n, 3) if n else 0,
        "avg_mrr": round(total_mrr / n, 3) if n else 0,
        "details": results,
    }


async def evaluate_faithfulness(kb_id: int, test_questions: list[dict]) -> dict:
    """用 LLM 评判生成的答案是否忠实于检索到的上下文。

    对每个问题，让 RAG 生成答案，然后让 LLM 评判答案是否仅基于提供的上下文。
    返回忠实度评分（0-1）。
    """
    pipeline = RAGPipeline()
    llm = get_llm_backend()
    results = []
    total_faithfulness = 0

    FAITHFULNESS_PROMPT = """你是一个评估助手。请判断以下回答是否完全基于提供的上下文资料，没有编造信息。

上下文资料：
{context}

回答：
{answer}

请给出忠实度评分（0.0 到 1.0）：
- 1.0：回答完全基于上下文，没有任何编造
- 0.5：部分基于上下文，有少量推测
- 0.0：回答与上下文无关或大量编造

只输出一个数字，不要解释。"""

    for i, item in enumerate(test_questions):
        q = item["question"]
        try:
            result = await pipeline.query(q, kb_id)
            answer = result.answer

            # 取检索到的上下文
            candidates = retriever.hybrid_search(kb_id, q)
            top3 = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:3]
            context = "\n---\n".join(c.get("text", "")[:500] for c in top3)

            prompt = FAITHFULNESS_PROMPT.format(context=context[:3000], answer=answer)
            score_str = await llm.chat([ChatMessage(role="user", content=prompt)], max_tokens=10, temperature=0)
            try:
                score = float(score_str.strip())
                score = max(0.0, min(1.0, score))
            except (ValueError, TypeError):
                score = 0.5  # 解析失败给中等分

            total_faithfulness += score
            results.append({
                "question": q[:80],
                "answer_preview": answer[:200],
                "faithfulness": round(score, 3),
                "latency_ms": result.processing_time_ms,
            })
        except Exception as e:
            results.append({
                "question": q[:80],
                "error": str(e)[:100],
            })

    n = len(test_questions)
    return {
        "avg_faithfulness": round(total_faithfulness / n, 3) if n else 0,
        "details": results,
    }


async def main():
    parser = argparse.ArgumentParser(description="RAG 检索质量评估")
    parser.add_argument("--kb-id", type=int, default=5, help="目标知识库 ID")
    parser.add_argument("--faithfulness", action="store_true", help="同时评估 Faithfulness（会调用 LLM，较慢较贵）")
    parser.add_argument("--questions", type=str, default="", help="自定义问题 JSON 文件路径")
    args = parser.parse_args()

    questions = DEFAULT_QUESTIONS
    if args.questions:
        with open(args.questions, encoding="utf-8") as f:
            questions = json.load(f)

    print(f"\n{'='*60}")
    print(f"RAG 评估 — KB #{args.kb_id} — {len(questions)} 个问题")
    print(f"{'='*60}")

    # 1. 检索质量
    print("\n[1/2] 检索质量 (Recall@5 + MRR)...")
    retrieval_result = await evaluate_retrieval(args.kb_id, questions)
    print(f"  Avg Recall@5 : {retrieval_result['avg_recall_at_5']:.3f}")
    print(f"  Avg MRR       : {retrieval_result['avg_mrr']:.3f}")
    for d in retrieval_result["details"]:
        print(f"  Q: {d['question']}")
        print(f"    Recall@5={d['recall@5']:.3f}  MRR={d['mrr']:.3f}  latency={d['latency_ms']}ms  candidates={d['total_candidates']}")
        print(f"    Sources: {d['top5_sources'][:3]}")

    # 2. Faithfulness (可选)
    if args.faithfulness:
        print("\n[2/2] 忠实度评估 (Faithfulness)...")
        faith_result = await evaluate_faithfulness(args.kb_id, questions)
        print(f"  Avg Faithfulness: {faith_result['avg_faithfulness']:.3f}")
        for d in faith_result["details"]:
            print(f"  Q: {d.get('question','')}")
            if "error" in d:
                print(f"    ERROR: {d['error']}")
            else:
                print(f"    Faithfulness={d['faithfulness']:.3f}  latency={d['latency_ms']}ms")
                print(f"    Answer: {d['answer_preview'][:120]}...")

    # 汇总
    print(f"\n{'='*60}")
    print("评估完成")
    print(f"  Recall@5 : {retrieval_result['avg_recall_at_5']:.3f}")
    print(f"  MRR      : {retrieval_result['avg_mrr']:.3f}")
    if args.faithfulness:
        print(f"  Faithfulness: {faith_result['avg_faithfulness']:.3f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
