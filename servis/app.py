"""FastAPI приложение — точка входа бэкенда."""
import base64
import csv
import io
import json
import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from parsery import get_parser, SUPPORTED_FORMATS, ParsedData
from generator import generate_ts_code_with_retry

BINARY_FORMATS = {".xlsx", ".xls", ".docx", ".pdf"}


def parsed_to_csv(parsed: ParsedData) -> str:
    """Конвертирует ParsedData в CSV-строку."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=parsed.columns)
    writer.writeheader()
    for row in parsed.all_rows:
        writer.writerow(row)
    return output.getvalue()

app = FastAPI(title="Генератор TypeScript-кода")

# Путь к React-билду
BUILD_DIR = Path(__file__).parent.parent / "sajt" / "build"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/formats")
async def get_formats():
    """Список поддерживаемых форматов файлов."""
    return {"formats": SUPPORTED_FORMATS}


@app.post("/generate")
async def generate(
    file: UploadFile = File(...),
    target_json: str = Form(default=""),
):
    """Принимает файл + пример JSON, возвращает TypeScript-код."""
    # Определяем расширение файла
    filename = file.filename or "file.csv"
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Формат {ext} не поддерживается. Доступные: {SUPPORTED_FORMATS}",
        )

    # Читаем файл
    file_bytes = await file.read()

    # Парсим файл
    try:
        parser = get_parser(ext)
        parsed: ParsedData = parser.parse(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга файла: {str(e)}")

    # Парсим целевой JSON
    parsed_target = None
    if target_json and target_json.strip():
        try:
            parsed_target = json.loads(target_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Невалидный JSON в target_json")

    # Для бинарных форматов конвертируем в CSV и генерируем код для CSV
    csv_base64_str = None
    gen_format = ext
    if ext in BINARY_FORMATS:
        csv_text = parsed_to_csv(parsed)
        csv_base64_str = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")
        gen_format = ".csv"
        parsed.separator = ","

    # Генерируем TypeScript-код
    result = generate_ts_code_with_retry(
        file_structure=parsed.to_dict(),
        target_json=parsed_target,
        file_format=gen_format,
    )

    response = {
        "typescript_code": result.get("typescript_code", ""),
        "tokens_used": result.get("tokens_used", 0),
        "prompt_tokens": result.get("prompt_tokens", 0),
        "response_tokens": result.get("response_tokens", 0),
        "file_info": {
            "filename": filename,
            "format": ext,
            "columns": parsed.columns,
            "row_count": len(parsed.sample_rows),
        },
        "error": result.get("error"),
    }
    if csv_base64_str:
        response["csv_base64"] = csv_base64_str

    return JSONResponse(content=response)


@app.post("/parse")
async def parse_file(file: UploadFile = File(...)):
    """Парсит файл и возвращает его структуру."""
    filename = file.filename or "file.csv"
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Формат {ext} не поддерживается.",
        )

    file_bytes = await file.read()

    try:
        parser = get_parser(ext)
        parsed = parser.parse(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга: {str(e)}")

    return JSONResponse(content=parsed.to_dict())


# Раздаём статику React-билда
if BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(BUILD_DIR / "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """Все остальные запросы отдают React SPA."""
        file_path = BUILD_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(BUILD_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
