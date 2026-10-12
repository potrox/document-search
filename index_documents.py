import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


INDEX_NAME = "documents"


def generate_actions(cursor):
    cursor.execute("SELECT id, text FROM documents ORDER BY id;")

    for document_id, text in cursor:
        yield {
            "_op_type": "index",
            "_index": INDEX_NAME,
            "_id": str(document_id),
            "_source": {
                "id": document_id,
                "text": text,
            },
        }


def main():
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    with Elasticsearch(
        os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
        request_timeout=30,
    ) as client:
        if not client.indices.exists(index=INDEX_NAME):
            raise RuntimeError(
                "Индекс documents не существует. Создайте индекс перед индексацией."
            )

        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                processed, _ = bulk(
                    client,
                    generate_actions(cursor),
                    chunk_size=200,
                )

        client.indices.refresh(index=INDEX_NAME)
        document_count = client.count(index=INDEX_NAME)["count"]

    print(f"Успешно проиндексировано документов: {processed}")
    print(f"Документов в индексе: {document_count}")


if __name__ == "__main__":
    main()
