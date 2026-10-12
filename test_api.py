import json
import os
import random
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from elasticsearch import Elasticsearch


load_dotenv(Path(__file__).resolve().parent / ".env")
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def api_request(method, path, payload=None, timeout=40):
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        BASE_URL + path, data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


def connect_database():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token = "apitest" + uuid4().hex
        cls.rare_token = "rare" + uuid4().hex
        cls.no_match_token = "absent" + uuid4().hex
        cls.client = Elasticsearch(
            os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
            request_timeout=30,
        )
        cls.addClassCleanup(cls.client.close)
        cls.rows = []
        cls.indexed_ids = []
        cls.addClassCleanup(cls.clean_documents)
        with connect_database() as connection:
            candidates = random.SystemRandom().sample(range(1_000_000_000, 2_000_000_000), 80)
            for document_id in candidates:
                if connection.execute("SELECT 1 FROM documents WHERE id = %s", (document_id,)).fetchone():
                    continue
                if cls.client.exists(index="documents", id=str(document_id)):
                    continue
                if len(cls.rows) == 27:
                    cls.missing_id = document_id
                    break
                number = len(cls.rows)
                text = cls.token if number < 25 else "delete" + uuid4().hex
                if number == 0:
                    text += " " + cls.rare_token
                row = {
                    "id": document_id,
                    "text": text,
                    "created_date": datetime(2020, 1, 1) + timedelta(days=number % 4),
                    "rubrics": ["тест", cls.token],
                }
                connection.execute(
                    "INSERT INTO documents (id, text, created_date, rubrics) VALUES (%(id)s, %(text)s, %(created_date)s, %(rubrics)s)",
                    row,
                )
                cls.rows.append(row)
            if len(cls.rows) != 27 or not hasattr(cls, "missing_id"):
                raise RuntimeError("Не удалось подобрать свободные ID для тестов.")
        for row in cls.rows:
            cls.client.create(index="documents", id=str(row["id"]), document={"id": row["id"], "text": row["text"]})
            cls.indexed_ids.append(row["id"])
        cls.client.indices.refresh(index="documents")

    @classmethod
    def clean_documents(cls):
        try:
            with connect_database() as connection:
                for row in cls.rows:
                    connection.execute("DELETE FROM documents WHERE id = %s AND text = %s", (row["id"], row["text"]))
        finally:
            for document_id in cls.indexed_ids:
                cls.client.options(ignore_status=404).delete(index="documents", id=str(document_id))
            if cls.indexed_ids:
                cls.client.indices.refresh(index="documents")

    def test_search_limit_fields_and_order(self):
        status, documents = api_request("POST", "/search", {"text": self.token})
        self.assertEqual(status, 200)
        self.assertEqual(len(documents), 20)
        self.assertEqual(len({doc["id"] for doc in documents}), 20)
        selected = self.client.search(index="documents", query={"match": {"text": self.token}}, size=20, source_includes=["id"])
        selected_ids = {hit["_source"]["id"] for hit in selected["hits"]["hits"]}
        expected = sorted((row for row in self.rows if row["id"] in selected_ids), key=lambda row: (-row["created_date"].toordinal(), row["id"]))
        self.assertEqual([doc["id"] for doc in documents], [row["id"] for row in expected])
        for document, row in zip(documents, expected):
            self.assertEqual(set(document), {"id", "rubrics", "text", "created_date"})
            self.assertEqual(document["text"], row["text"])
            self.assertEqual(document["rubrics"], row["rubrics"])
            self.assertEqual(datetime.fromisoformat(document["created_date"]), row["created_date"])

    def test_search_fewer_than_twenty(self):
        status, documents = api_request("POST", "/search", {"text": self.rare_token})
        self.assertEqual(status, 200)
        self.assertEqual([doc["id"] for doc in documents], [self.rows[0]["id"]])

    def test_search_no_matches(self):
        status, documents = api_request("POST", "/search", {"text": self.no_match_token})
        self.assertEqual(status, 200)
        self.assertEqual(documents, [])

    def test_invalid_search(self):
        for payload in ({}, {"text": ""}, {"text": "   "}, {"text": None}, {"text": 123}, {"text": []}, []):
            with self.subTest(payload=payload):
                status, _ = api_request("POST", "/search", payload)
                self.assertEqual(status, 422)

    def test_search_with_quotes(self):
        status, documents = api_request("POST", "/search", {"text": '"' + self.token + '"'})
        self.assertEqual(status, 200)
        self.assertEqual(len(documents), 20)
        self.assertTrue(all(doc["id"] in {row["id"] for row in self.rows[:25]} for doc in documents))

    def test_invalid_document_id(self):
        for document_id in ("0", "-1", "abc", "1.5", "2147483648"):
            with self.subTest(document_id=document_id):
                status, _ = api_request("DELETE", f"/documents/{document_id}")
                self.assertEqual(status, 422)

    def test_delete_missing_document(self):
        status, body = api_request("DELETE", f"/documents/{self.missing_id}")
        self.assertEqual(status, 404)
        self.assertEqual(body["detail"], "Документ не существует.")

    def test_delete_existing_document(self):
        document_id = self.rows[25]["id"]
        status, body = api_request("DELETE", f"/documents/{document_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"id": document_id, "deleted": True})
        with connect_database() as connection:
            self.assertIsNone(connection.execute("SELECT id FROM documents WHERE id = %s", (document_id,)).fetchone())
        self.assertFalse(self.client.exists(index="documents", id=str(document_id)))
        status, _ = api_request("DELETE", f"/documents/{document_id}")
        self.assertEqual(status, 404)

    def test_concurrent_searches(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(api_request, "POST", "/search", {"text": self.token})
                for _ in range(4)
            ]
            for future in futures:
                status, documents = future.result(timeout=10)
                self.assertEqual(status, 200)
                self.assertEqual(len(documents), 20)
                self.assertTrue(all(self.token in doc["text"] for doc in documents))

    def test_concurrent_request_during_locked_delete(self):
        document_id = self.rows[26]["id"]
        with ThreadPoolExecutor(max_workers=1) as executor:
            with connect_database() as blocker:
                blocker.execute(
                    "SELECT id FROM documents WHERE id = %s FOR UPDATE",
                    (document_id,),
                )
                blocker_pid = blocker.info.backend_pid
                pending = executor.submit(
                    api_request, "DELETE", f"/documents/{document_id}"
                )
                with connect_database() as observer:
                    observer.autocommit = True
                    deadline = time.monotonic() + 5
                    while True:
                        waiting = observer.execute(
                            "SELECT pid FROM pg_stat_activity "
                            "WHERE %s = ANY(pg_blocking_pids(pid))",
                            (blocker_pid,),
                        ).fetchone()
                        if waiting:
                            break
                        if time.monotonic() >= deadline:
                            self.fail("Удаление не перешло в ожидание блокировки PostgreSQL.")
                        time.sleep(0.02)
                self.assertFalse(pending.done())
                status, documents = api_request(
                    "POST", "/search", {"text": self.no_match_token}, timeout=2
                )
                self.assertEqual(status, 200)
                self.assertEqual(documents, [])
            status, body = pending.result(timeout=10)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"id": document_id, "deleted": True})
        with connect_database() as connection:
            self.assertIsNone(connection.execute(
                "SELECT id FROM documents WHERE id = %s", (document_id,)
            ).fetchone())
        self.assertFalse(self.client.exists(index="documents", id=str(document_id)))


if __name__ == "__main__":
    unittest.main()
