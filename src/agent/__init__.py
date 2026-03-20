from langchain_core.output_parsers import StrOutputParser
from langchain_gigachat import GigaChat

from agent.message import agent_prompt

llm = GigaChat()

chain = agent_prompt | llm | StrOutputParser()