import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch


load_dotenv(Path(__file__).resolve().parent / ".env")


class DocumentNotFoundError(Exception):
    pass


async def delete_document(document_id: int) -> None:
    async with await psycopg.AsyncConnection.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE id = %s
                FOR UPDATE;
                """,
                (document_id,),
            )

            if await cursor.fetchone() is None:
                raise DocumentNotFoundError(
                    "Документ не существует."
                )

            async with AsyncElasticsearch(
                os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
                request_timeout=30,
            ) as client:
                response = await client.options(
                    ignore_status=404,
                ).delete(
                    index="documents",
                    id=str(document_id),
                    refresh="wait_for",
                )

                if response.get("result") not in {
                    "deleted",
                    "not_found",
                }:
                    raise RuntimeError(
                        "Elasticsearch не подтвердил удаление."
                    )

            await cursor.execute(
                "DELETE FROM documents WHERE id = %s;",
                (document_id,),
            )