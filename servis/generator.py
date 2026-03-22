"""Генератор TypeScript-кода через GigaChat API напрямую."""
import json
import re
import time
import datetime
import requests
import uuid

GIGACHAT_TOKEN = "MDE5Y2ZiNmYtZGFkZC03YjYwLWFlN2MtN2IwMWJlOTZiZTY3OmJiZjJhNWFkLTgxMTUtNGYwZC1iNzAyLWVkYjg4Y2UxNDI4YQ=="

AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

LANGFUSE_PUBLIC_KEY = "pk-lf-98279f8f-10d5-4cfb-b96c-c9c30ed6eaac"
LANGFUSE_SECRET_KEY = "sk-lf-dfb386f4-7d40-46f9-8950-5c67ebca0b4f"
LANGFUSE_HOST = "https://cloud.langfuse.com"


def langfuse_log(trace_id: str, name: str, model: str, input_msgs: list, output: str, usage: dict, latency: float):
    """Отправляет данные в LangFuse через REST API."""
    try:
        now = datetime.datetime.utcnow().isoformat() + "Z"
        requests.post(
            f"{LANGFUSE_HOST}/api/public/ingestion",
            auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY),
            json={"batch": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": now,
                    "body": {"id": trace_id, "name": name, "timestamp": now},
                },
                {
                    "id": str(uuid.uuid4()),
                    "type": "generation-create",
                    "timestamp": now,
                    "body": {
                        "traceId": trace_id,
                        "name": "gigachat-completion",
                        "model": model,
                        "input": input_msgs,
                        "output": output,
                        "usage": {
                            "input": usage.get("prompt_tokens", 0),
                            "output": usage.get("completion_tokens", 0),
                            "total": usage.get("total_tokens", 0),
                        },
                        "metadata": {"latency_seconds": round(latency, 2)},
                        "startTime": now,
                        "endTime": now,
                    },
                },
            ]},
            timeout=5,
        )
    except Exception:
        pass  # Не ломаем основной поток

SYSTEM_PROMPT = "Верни ТОЛЬКО TypeScript-код. БЕЗ примечаний, пояснений, markdown, import. Код БРАУЗЕРНЫЙ. Для CSV: atob()+split по разделителю. Для JSON: JSON.parse(atob()). Для XML: new DOMParser(). ЗАПРЕЩЕНО: import, require, fs, Buffer, повторное использование _ в деструктуризации (используй _1,_2 и т.д.). Функция parseFile(base64:string):T[]."


def get_access_token() -> str:
    """Получает access token через OAuth."""
    response = requests.post(
        AUTH_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {GIGACHAT_TOKEN}",
        },
        data={"scope": "GIGACHAT_API_CORP"},
        verify=False,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def call_gigachat(system_prompt: str, user_message: str) -> dict:
    """Вызывает GigaChat API и возвращает ответ."""
    token = get_access_token()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    start_time = time.time()

    response = requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "model": "GigaChat-2-Max",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 800,
        },
        verify=False,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    latency = time.time() - start_time

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    langfuse_log(
        trace_id=str(uuid.uuid4()),
        name="gigachat-generate",
        model="GigaChat-2-Max",
        input_msgs=messages,
        output=content,
        usage=usage,
        latency=latency,
    )

    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def generate_ts_code(
    file_structure: dict,
    target_json: dict | list | None,
    file_format: str,
) -> dict:
    """Генерирует TypeScript-код на основе структуры файла и целевого JSON."""
    columns = file_structure.get("columns", [])
    sample = file_structure.get("sample_rows", [])[:1]
    sep = file_structure.get("separator", ",")

    if target_json:
        t = target_json[0] if isinstance(target_json, list) and target_json else target_json
        tgt = json.dumps(t, ensure_ascii=False)
    else:
        tgt = "{}"

    user_message = f"Формат:{file_format} Разделитель:{sep} Колонки:{columns} Пример строки:{sample[0] if sample else {}} Целевой:{tgt}"

    result = call_gigachat(SYSTEM_PROMPT, user_message)
    ts_code = clean_ts_code(result["content"])

    return {
        "typescript_code": ts_code,
        "tokens_used": result["total_tokens"],
        "prompt_tokens": result["prompt_tokens"],
        "response_tokens": result["completion_tokens"],
    }


def clean_ts_code(code: str) -> str:
    """Убирает markdown-обёртки и пояснения из ответа LLM."""
    code = re.sub(r"^```(?:typescript|ts)?\s*\n", "", code.strip())
    code = re.sub(r"\n```\s*$", "", code.strip())
    # Убираем всё после последней закрывающей скобки функции
    lines = code.split("\n")
    result = []
    for line in lines:
        if line.startswith("**") or line.startswith("Примечание") or line.startswith("Для работы") or line.startswith("Эта функция"):
            break
        result.append(line)
    code = "\n".join(result).strip()
    # Заключаем не-ASCII ключи объектов в кавычки: №: → "№":
    code = re.sub(r'(?<=[\{,\n])\s*([^\x00-\x7F][\w%\s]*)\s*:', lambda m: f' "{m.group(1).strip()}":', code)
    return code


def generate_ts_code_with_retry(
    file_structure: dict,
    target_json: dict | list | None,
    file_format: str,
    max_retries: int = 2,
) -> dict:
    """Генерация с повторными попытками при ошибке."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = generate_ts_code(file_structure, target_json, file_format)
            return result
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                continue
    return {
        "typescript_code": f"// Ошибка генерации: {last_error}",
        "tokens_used": 0,
        "error": last_error,
    }
