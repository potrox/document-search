import ast
import csv
import os
import psycopg
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

def prepare_document(row: dict, document_id: int) -> dict:
    rubrics = ast.literal_eval(row['rubrics'])

    if not isinstance(rubrics, list):
        raise ValueError(
            f"Документ {document_id}: rubrics должен содержать список"
        )

    if not all(isinstance(rubric, str) for rubric in rubrics):
        raise ValueError(
            f"Документ {document_id}: каждая рубрика должна быть строкой"
        )

    return {
        "id": document_id,
        "text": row["text"],
        "created_date": datetime.strptime(
            row["created_date"], "%Y-%m-%d %H:%M:%S"
        ),
        "rubrics": rubrics,
    }


def main():
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    processed = 0

    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            with open(
                project_dir / "data" / "posts.csv",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(file)

                for number, row in enumerate(reader, start=1):
                    document = prepare_document(row, number)

                    cursor.execute(
                        """
                        INSERT INTO documents (id, text, created_date, rubrics)
                        VALUES (%(id)s, %(text)s, %(created_date)s, %(rubrics)s)
                        ON CONFLICT (id) DO UPDATE SET
                            text = EXCLUDED.text,
                            created_date = EXCLUDED.created_date,
                            rubrics = EXCLUDED.rubrics;
                        """,
                        document,
                    )
                    processed += 1

    print(f"Обработано документов: {processed}")


if __name__ == "__main__":
    main()