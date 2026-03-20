from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    message: str = Field(
        description="Запрос пользователя",
        min_length=4,
        max_length=2000,
        example="Привет! Запомни информацию: в конце года поднимется ключевая ставка ЦБ.",
    ) 


class AgentResponse(BaseModel):
    content: str = Field(
        description="Ответ от Greeter Agent",
        max_length=2000,
        example=(
            "Привет! Хорошо запомню твою информацию про ключевую ставку ЦБ к концу года."
            "Если захочешь обсудить это подробнее или что-то еще — обращайся!"
        ),
    )
    