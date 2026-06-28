"""Multi-agent LangGraph orchestration with specialist ReAct agents."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.context import set_thread_context
from agent.experiments import apply_variant_prompt, assign_variant
from agent.prompts import (
    GENERAL_PROMPT,
    HANDOVER_PROMPT,
    RECALL_PROMPT,
    SALES_PROMPT,
    SERVICE_PROMPT,
)
from agent.router import route_message
from agent.tools import (
    GENERAL_TOOLS,
    HANDOVER_TOOLS,
    RECALL_TOOLS,
    SALES_TOOLS,
    SERVICE_TOOLS,
    set_thread_id,
)
from metrics.store import ensure_variant, log_agent_route

load_dotenv()

AGENT_LABELS = {
    "service": "Service Agent",
    "sales": "Sales Agent",
    "recall": "Recall Agent",
    "handover": "Handover Agent",
    "general": "General Agent",
}

PROMPTS = {
    "service": SERVICE_PROMPT,
    "sales": SALES_PROMPT,
    "recall": RECALL_PROMPT,
    "handover": HANDOVER_PROMPT,
    "general": GENERAL_PROMPT,
}

TOOLS = {
    "service": SERVICE_TOOLS,
    "sales": SALES_TOOLS,
    "recall": RECALL_TOOLS,
    "handover": HANDOVER_TOOLS,
    "general": GENERAL_TOOLS,
}

_checkpointer = MemorySaver()
_specialists: dict[str, dict[str, object]] = {}


def _pre_model_hook(state):
    trimmed = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=4000,
        start_on="human",
        end_on=("human", "tool"),
        include_system=True,
    )
    return {"llm_input_messages": trimmed}


def _build_llm(api_key: str, variant: str) -> ChatGroq:
    # Tool calls need more headroom than short chat replies — low limits cause truncated JSON.
    max_tokens = 256 if variant == "B" else 320
    return ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        max_tokens=max_tokens,
        api_key=api_key,
    )


def _get_specialist(api_key: str, agent_name: str, variant: str):
    if variant not in _specialists:
        _specialists[variant] = {}
    if agent_name not in _specialists[variant]:
        llm = _build_llm(api_key, variant)
        prompt = apply_variant_prompt(PROMPTS[agent_name], variant)
        _specialists[variant][agent_name] = create_react_agent(
            llm,
            TOOLS[agent_name],
            prompt=prompt,
            checkpointer=_checkpointer,
            pre_model_hook=_pre_model_hook,
        )
    return _specialists[variant][agent_name]


@dataclass
class AgentResult:
    reply: str
    input_tokens: int = 0
    output_tokens: int = 0
    escalated: bool = False
    tool_calls: list[str] = field(default_factory=list)
    routed_agent: str = "general"
    route_reason: str = ""
    agent_label: str = "General Agent"
    variant: str = "A"


def _extract_usage(messages: list) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            input_tokens += msg.usage_metadata.get("input_tokens", 0)
            output_tokens += msg.usage_metadata.get("output_tokens", 0)
    return input_tokens, output_tokens


def _extract_tool_calls(messages: list) -> list[str]:
    names: list[str] = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                names.append(tc["name"])
        if isinstance(msg, ToolMessage) and msg.name:
            names.append(msg.name)
    return names


def _extract_reply(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _is_tool_parse_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "tool_use_failed" in text or "failed to parse tool call" in text


def run_agent(message: str, thread_id: str) -> AgentResult:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured")

    variant = ensure_variant(thread_id)
    set_thread_id(thread_id)

    agent_name, route_reason = route_message(message, thread_id, api_key=api_key)
    log_agent_route(thread_id, agent_name, route_reason, message)
    set_thread_context(thread_id, routed_agent=agent_name, variant=variant)

    agent = _get_specialist(api_key, agent_name, variant)
    config = {"configurable": {"thread_id": thread_id}}

    invoke_msg: HumanMessage | str = message
    result = None
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            result = agent.invoke(
                {"messages": [invoke_msg] if isinstance(invoke_msg, HumanMessage) else [HumanMessage(content=invoke_msg)]},
                config=config,
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt == 0 and _is_tool_parse_error(exc):
                invoke_msg = HumanMessage(
                    content=(
                        f"{message}\n\n"
                        "[System note: If booking, call book_appointment with valid JSON only. "
                        "Include vehicle_model as one string, e.g. \"2020 Toyota Camry\". "
                        "Required fields: service_type, date, time, customer_name, vehicle_model.]"
                    )
                )
                continue
            raise

    if result is None:
        raise last_error or RuntimeError("Agent invocation failed")

    messages = result["messages"]
    reply = _extract_reply(messages)
    input_tokens, output_tokens = _extract_usage(messages)
    tool_calls = _extract_tool_calls(messages)
    escalated = "escalate_to_human" in tool_calls

    return AgentResult(
        reply=reply,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        escalated=escalated,
        tool_calls=tool_calls,
        routed_agent=agent_name,
        route_reason=route_reason,
        agent_label=AGENT_LABELS.get(agent_name, agent_name),
        variant=variant,
    )
