from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.services.ollama_service import generate

class AgentState(TypedDict):
    prompt: str
    answer: str

async def llama_node(state: AgentState) -> AgentState:
    answer = await generate(state["prompt"])
    return {"prompt": state["prompt"], "answer": answer}

builder = StateGraph(AgentState)
builder.add_node("llama", llama_node)
builder.add_edge(START, "llama")
builder.add_edge("llama", END)
applyai_graph = builder.compile()

async def run_agent(prompt: str) -> str:
    result = await applyai_graph.ainvoke({"prompt": prompt, "answer": ""})
    return result["answer"]
