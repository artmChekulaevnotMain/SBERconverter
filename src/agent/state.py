from langgraph.graph import MessagesState


class AgentState(MessagesState):
    question: str
    answer: str