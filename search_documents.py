import asyncio
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from psycopg.rows import dict_row


load_dotenv(Path(__file__).resolve().parent / ".env")


async def search_documents(text: str) -> list[dict]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Текст поиска должен быть непустой строкой.")

    async with AsyncElasticsearch(
        os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
        request_timeout=30,
    ) as client:
        response = await client.search(
            index="documents",
            query={"match": {"text": text.strip()}},
            size=20,
            source_includes=["id"],
        )

    document_ids = [
        hit["_source"]["id"]
        for hit in response["hits"]["hits"]
    ]

    if not document_ids:
        return []

    async with await psycopg.AsyncConnection.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
        row_factory=dict_row,
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT id, rubrics, text, created_date
                FROM documents
                WHERE id = ANY(%s)
                ORDER BY created_date DESC, id ASC;
                """,
                (document_ids,),
            )
            documents = await cursor.fetchall()

    if len(documents) != len(document_ids):
        raise RuntimeError(
            "Индекс и PostgreSQL рассогласованы: "
            "часть найденных документов отсутствует в базе."
        )

    return documents


def main():
    text = input("Текст для поиска: ")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        documents = runner.run(search_documents(text))

    print(f"Найдено документов в выдаче: {len(documents)}")
    print(
        json.dumps(
            documents,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
