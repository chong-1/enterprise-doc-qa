"""LangGraph Agent 编排：Router → RAG / ReAct → 答案生成。

StateGraph:
    START → router → [rag_direct / react_loop] → generate → END

react_loop 内部是标准的 ReAct 模式（Thought → Tool → Observation 循环），
最大 3 轮，每轮的思考过程记录到 thought_chain 供前端展示。
"""

import json
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.services.agent.tools import AGENT_TOOLS
from app.services.llm import get_llm_backend
from app.services.llm.base import ChatMessage

MAX_REACT_STEPS = 3


def _last_human_question(messages: list) -> str:
    """取最后一条用户消息。

    Agent 模式的输入是「历史消息 + 当前问题」，只有最后一条 human 才是当前问题，
    取第一条会把第一轮的历史问题当成当前问题（旧答案 bug 的根源）。
    """
    for m in reversed(messages):
        if hasattr(m, "type") and m.type == "human":
            return m.content or ""
    return ""


# ========== State ==========

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    kb_id: int
    thought_chain: list[str]
    final_answer: str
    citations: list[dict]


# ========== Router ==========

ROUTER_PROMPT = """分析用户意图，返回 JSON：
{"intent": "simple_qa" | "document_lookup" | "complex", "reasoning": "一句话原因"}

- simple_qa: 单一事实查询（"XX 是多少"、"XX 是什么"）
- document_lookup: 询问有哪些文档或文档详情
- complex: 需要比较、分析、多步推理的问题"""


async def _classify_intent(question: str) -> dict:
    llm = get_llm_backend()
    raw = await llm.chat([
        ChatMessage(role="system", content=ROUTER_PROMPT),
        ChatMessage(role="user", content=question),
    ], max_tokens=200, temperature=0)
    try:
        return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
    except json.JSONDecodeError:
        return {"intent": "simple_qa", "reasoning": "fallback"}


async def router_node(state: AgentState) -> dict:
    question = _last_human_question(state["messages"])
    result = await _classify_intent(question or "")
    intent = result.get("intent", "simple_qa")
    state["thought_chain"] = [f"[Router] 意图识别: {intent} — {result.get('reasoning', '')}"]
    return {"thought_chain": state["thought_chain"]}


def route_decision(state: AgentState) -> str:
    last = state["thought_chain"][-1] if state["thought_chain"] else ""
    if "complex" in last:
        return "react_loop"
    elif "document_lookup" in last:
        return "react_loop"
    return "rag_direct"


# ========== RAG Direct ==========

async def rag_direct_node(state: AgentState) -> dict:
    from app.services.rag import retriever
    from app.services.rag.generator import SYSTEM_PROMPT, _trim_context, _format_context

    question = _last_human_question(state["messages"])
    kb_id = state["kb_id"]

    # 指代消解：检索 query 拼接最近对话历史（最近 300 字）。
    # "它能够用来做什么"这类指代问题，裸 query 没有语义，检索必然跑偏
    # （命中文档里最像"能做什么"的 LLM-Agent 片段）。带上历史后
    # "什么是NLP？→NLP是自然语言处理"才能把检索锚定到 NLP 相关内容。
    history_query = ""
    for m in state["messages"][:-1]:
        if hasattr(m, "type") and m.type == "human":
            history_query += f"用户：{m.content}\n"
        elif hasattr(m, "type") and m.type == "ai":
            history_query += f"助手：{m.content}\n"
    search_query = question
    if history_query:
        search_query = f"{history_query[-300:]}\n当前问题：{question}"

    candidates = retriever.hybrid_search(kb_id, search_query)
    candidates = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:5]

    state["thought_chain"].append(f"[RAG] 检索到 {len(candidates)} 条相关片段")

    trimmed = _trim_context(candidates)
    context = _format_context(trimmed)

    # 携带最近对话历史（不含当前问题），否则指代类问题（"它/这个/上述"）无法解析
    history_lines = []
    for m in state["messages"][:-1]:
        if hasattr(m, "type") and m.type == "human":
            history_lines.append(f"用户：{m.content}")
        elif hasattr(m, "type") and m.type == "ai":
            history_lines.append(f"助手：{m.content}")
    history_text = "\n".join(history_lines[-6:])

    llm = get_llm_backend()
    prompt = f"根据以下资料回答问题：\n\n{context}\n\n问题：{question}"
    if history_text:
        prompt = f"对话历史：\n{history_text}\n\n{prompt}"
    answer = await llm.chat([
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ])

    from app.services.rag.generator import format_citations
    return {
        "final_answer": answer.strip(),
        "citations": format_citations(candidates),
        "thought_chain": state["thought_chain"],
    }


# ========== ReAct Loop（含 tool calling） ==========

_REACT_SYSTEM = """你是企业文档助手。可以使用工具来查询知识库和文档信息。
思考-行动-观察：先思考需要什么信息，然后调用工具，根据结果再决定下一步。
最多 3 轮工具调用，最后给出完整答案。用中文回答。"""


async def react_agent_node(state: AgentState) -> dict:
    """ReAct Agent：调用 LLM with tools，执行 tool，循环。"""
    from langchain_core.messages import ToolMessage as LCToolMessage

    llm = get_llm_backend()
    # 构建 LangChain messages
    lc_messages = [SystemMessage(content=_REACT_SYSTEM)]
    for m in state["messages"]:
        lc_messages.append(m)

    # 用 LLM 一次性决定是否需要调 tool
    # 简化：直接用 LangChain ChatOpenAI 绑定 tools
    from langchain_openai import ChatOpenAI
    from app.core.config import settings

    chat_model = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0,
        max_tokens=1024,
    )
    from app.services.agent.tools import (
        search_knowledge_base as _search_kb,
        list_documents as _list_docs,
        get_document_info as _get_doc_info,
    )
    tools = [_search_kb, _list_docs, _get_doc_info]
    chat_with_tools = chat_model.bind_tools(tools)

    step = 0
    while step < MAX_REACT_STEPS:
        step += 1
        response = await chat_with_tools.ainvoke(lc_messages)
        lc_messages.append(response)

        if not response.tool_calls:
            state["thought_chain"].append(f"[ReAct 第{step}轮] 模型认为信息足够，准备回答")
            break

        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            # Agent 不知道 kb_id，始终从 state 覆盖
            tool_args["kb_id"] = state["kb_id"]
            state["thought_chain"].append(f"[ReAct 第{step}轮] 调用 {tool_name}({tool_args})")

            tool_func = {t.name: t for t in AGENT_TOOLS}.get(tool_name)
            if tool_func:
                try:
                    result = tool_func.invoke(tool_args)
                except Exception as e:
                    result = f"工具调用失败: {e}"
                lc_messages.append(LCToolMessage(content=str(result), tool_call_id=tc["id"]))
                state["thought_chain"].append(f"[ReAct 第{step}轮] 结果: {str(result)[:200]}...")

    if step >= MAX_REACT_STEPS and not state.get("final_answer"):
        state["thought_chain"].append(f"[ReAct] 达到最大步数 {MAX_REACT_STEPS}，强制生成答案")

    # 最终生成：对话历史轮次放前面（保证"它/这个"等指代有前文可循），
    # 最后 5 条 LLM/工具记录放后面，避免历史被工具结果挤出上下文
    context_parts = []
    for m in state["messages"][:-1]:
        if hasattr(m, "content") and m.content:
            context_parts.append(str(m.content)[:800])
    for m in lc_messages[-5:]:
        if hasattr(m, "content") and m.content:
            context_parts.append(str(m.content)[:1000])
    context = "\n\n".join(context_parts)

    llm_final = get_llm_backend()
    question = _last_human_question(state["messages"])

    answer = await llm_final.chat([
        ChatMessage(role="system", content="根据对话内容总结答案，简洁准确。中文回答。"),
        ChatMessage(role="user", content=f"对话记录：\n{context}\n\n用户问题：{question}\n\n请给出最终答案："),
    ])

    return {
        "final_answer": answer.strip(),
        "thought_chain": state["thought_chain"],
        "citations": [],
        "messages": lc_messages,
    }


# ========== 构建 Graph ==========

def build_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("rag_direct", rag_direct_node)
    workflow.add_node("react_loop", react_agent_node)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges("router", route_decision, {
        "rag_direct": "rag_direct",
        "react_loop": "react_loop",
    })
    workflow.add_edge("rag_direct", END)
    workflow.add_edge("react_loop", END)

    return workflow.compile()


_agent_graph = None


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph
