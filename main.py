from datetime import datetime

import psycopg
from elastic_transport import TransportError
from elasticsearch import ApiError
from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field, field_validator
from delete_documents import DocumentNotFoundError, delete_document
from search_documents import search_documents


app = FastAPI(
    title="Поиск документов",
    version="0.1.0",
)


class SearchRequest(BaseModel):
    text: str = Field(strict=True, min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Текст поиска не должен быть пустым.")
        return value


class Document(BaseModel):
    id: int
    rubrics: list[str]
    text: str
    created_date: datetime


@app.post(
    "/search",
    response_model=list[Document],
    responses={
        503: {"description": "Поиск временно недоступен"}
    },
)
async def search(request: SearchRequest):
    try:
        return await search_documents(request.text)
    except (
        psycopg.Error,
        ApiError,
        TransportError,
        RuntimeError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail="Поиск временно недоступен: "
                   "ошибка хранилищ или рассогласование данных.",
        ) from error

class DeleteResult(BaseModel):
    id: int
    deleted: bool


@app.delete(
    "/documents/{document_id}",
    response_model=DeleteResult,
    responses={
        404: {"description": "Документ не существует"},
        503: {"description": "Удаление не завершено"},
    },
)
async def remove_document(
    document_id: int = Path(gt=0, le=2147483647),
):
    try:
        await delete_document(document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except (
        psycopg.Error,
        ApiError,
        TransportError,
        RuntimeError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail="Удаление не завершено. "
                   "Проверьте хранилища и повторите запрос.",
        ) from error

    return {"id": document_id, "deleted": True}
