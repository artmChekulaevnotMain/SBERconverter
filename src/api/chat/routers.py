
from typing import Annotated

from fastapi import APIRouter, Depends

# Импорты FastUI
from fastui import FastUI
from fastui import components as c
from fastui.events import BackEvent
from fastui.forms import fastui_form
from langgraph.graph.state import CompiledStateGraph

from agent.main import get_graph_agent
from api.v1.schemas import AgentRequest

ui_router = APIRouter(prefix="/api/ui")

@ui_router.get("/", response_model=FastUI, response_model_exclude_none=True)
def ui_landing():
    """
    Главная страница с формой.
    """
    return [
        c.Page(
            components=[
                c.Heading(text='GigaChat Agent Interface', level=1),
                c.Markdown(text='Этот интерфейс построен на **FastUI** и работает внутри FastAPI.'),
                
                # Форма, которая ссылается на модель Pydantic
                # При отправке она сделает POST запрос на /api/ui/predict
                c.ModelForm(
                    model=AgentRequest,
                    submit_url='/api/ui/predict',
                    submit_on_change=False,
                    display_mode='default' # или 'page'
                ),
            ]
        )
    ]

@ui_router.post("/predict", response_model=FastUI, response_model_exclude_none=True)
async def ui_predict(
    # fastui_form автоматически распаковывает Form Data в Pydantic модель
    form: Annotated[AgentRequest, fastui_form(AgentRequest)],
    graph: CompiledStateGraph = Depends(get_graph_agent)
):
    """
    Обработчик формы. Принимает данные, вызывает граф, возвращает UI с ответом.
    """
    try:
        # Вызываем ту же логику, что и в API
        result = await graph.ainvoke({"question": form.message})
        answer_text = result.get("answer", "Нет ответа")

        return [
            c.Page(
                components=[
                    c.Heading(text='Результат', level=2),
                    
                    # Блок с ответом
                    c.Markdown( text=answer_text),
                    
                    c.Div(components=[
                         c.Markdown(text=f"**Ваш запрос:** {form.message}"),
                    ], class_name="p-4 border rounded my-4"),

                    # Кнопка "Назад"
                    c.Button(text="Задать новый вопрос", on_click=BackEvent()),
                ]
            )
        ]
    except Exception as e:
        # Красивый вывод ошибки
        return [
            c.Page(components=[
                c.Markdown(text=str(e)),
                c.Button(text="Назад", on_click=BackEvent())
            ])
        ]
    