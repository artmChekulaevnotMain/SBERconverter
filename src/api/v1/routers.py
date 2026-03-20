from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from langgraph.graph.state import CompiledStateGraph

from agent.main import get_graph_agent
from agent.state import AgentState
from api.v1.schemas import AgentRequest, AgentResponse

api_router = APIRouter()


@api_router.post("/prediction")
async def prediction(
    request: AgentRequest,
    graph: CompiledStateGraph = Depends(get_graph_agent)
):
    try:
        result: AgentState = await graph.ainvoke({"question": request.message}) 
        return AgentResponse(content=result.get("answer"))
    except Exception as ex:
        return JSONResponse(
            status_code=500,
            content={"message": str(ex)}
        )
    
    