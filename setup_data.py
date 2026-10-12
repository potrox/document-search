import argparse
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from import_posts import main as import_posts_main
from index_documents import INDEX_NAME, main as index_documents_main


def main():
    parser = argparse.ArgumentParser(description="Подготовка данных и поискового индекса")
    parser.add_argument(
        "--index-only", action="store_true",
        help="Индексация существующей таблицы documents без импорта CSV и изменения PostgreSQL.",
    )
    args = parser.parse_args()
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    if not args.index_only and not (project_dir / "data" / "posts.csv").is_file():
        raise FileNotFoundError("Файл data/posts.csv не найден.")

    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as connection:
        if args.index_only:
            connection.execute("SELECT id, text, created_date, rubrics FROM documents LIMIT 0")
        else:
            connection.execute(
                (project_dir / "schema.sql").read_text(encoding="utf-8")
            )

    with Elasticsearch(
        os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
        request_timeout=30,
    ) as client:
        if not client.indices.exists(index=INDEX_NAME):
            definition = json.loads(
                (project_dir / "index.json").read_text(encoding="utf-8")
            )
            client.indices.create(index=INDEX_NAME, **definition)

    if not args.index_only:
        import_posts_main()
    index_documents_main()
    print("Подготовка данных завершена.")


if __name__ == "__main__":
    main()
