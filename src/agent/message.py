from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """
You are a helpful assistant.
"""

agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("user", "{question}")
    ]
)