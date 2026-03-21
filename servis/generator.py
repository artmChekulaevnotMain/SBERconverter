"""Генератор TypeScript-кода через GigaChat API напрямую."""
import json
import re
import requests
import uuid

GIGACHAT_TOKEN = "MDE5Y2ZiNmYtZGFkZC03YjYwLWFlN2MtN2IwMWJlOTZiZTY3OmJiZjJhNWFkLTgxMTUtNGYwZC1iNzAyLWVkYjg4Y2UxNDI4YQ=="

AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

SYSTEM_PROMPT = """Генерируй только TypeScript-код. Функция: export default function(base64file: string): T[]. Декодируй base64, парси формат, маппи поля в целевой JSON. Без пояснений."""


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

    response = requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "model": "GigaChat-2-Max",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
            "max_tokens": 1500,
        },
        verify=False,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

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

    src = json.dumps({"fmt": file_format, "sep": sep, "cols": columns, "row": sample[0] if sample else {}}, ensure_ascii=False)

    if target_json:
        t = target_json[0] if isinstance(target_json, list) and target_json else target_json
        tgt = json.dumps(t, ensure_ascii=False)
    else:
        tgt = "{}"

    user_message = f"Src:{src}\nTarget:{tgt}"

    result = call_gigachat(SYSTEM_PROMPT, user_message)
    ts_code = clean_ts_code(result["content"])

    return {
        "typescript_code": ts_code,
        "tokens_used": result["total_tokens"],
        "prompt_tokens": result["prompt_tokens"],
        "response_tokens": result["completion_tokens"],
    }


def clean_ts_code(code: str) -> str:
    """Убирает markdown-обёртки из ответа LLM."""
    code = re.sub(r"^```(?:typescript|ts)?\s*\n", "", code.strip())
    code = re.sub(r"\n```\s*$", "", code.strip())
    return code.strip()


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
