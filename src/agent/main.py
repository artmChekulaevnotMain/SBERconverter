from functools import cache

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.state import AgentState

from . import chain


async def agent_node(state: AgentState) -> AgentState:
   result = await chain.ainvoke({"question": state.get("question")})
   
   return {
      "answer": result
   }


workflow = StateGraph(AgentState)

workflow.add_node(agent_node.__name__, agent_node)

workflow.set_entry_point(agent_node.__name__)


@cache
def get_graph_agent() -> CompiledStateGraph:
    """You can add memory if need"""
    return workflow.compile()
