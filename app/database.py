import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import OrderCreate, Patient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _patient_record(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["code"] = f"P-{result['id']:06d}"
    return result


def _order_record(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["tests"] = json.loads(result.pop("tests_json"))
    return result


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    medical_history TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                    tests_json TEXT NOT NULL,
                    doctor_name TEXT NOT NULL,
                    clinical_question TEXT NOT NULL,
                    copies INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_patient_id ON orders(patient_id);
                CREATE INDEX IF NOT EXISTS idx_patients_created_at ON patients(created_at);
            """)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_patients(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("""
                SELECT p.*, COUNT(o.id) AS order_count
                FROM patients AS p LEFT JOIN orders AS o ON o.patient_id = p.id
                GROUP BY p.id ORDER BY p.id DESC
            """).fetchall()
        return [_patient_record(row) for row in rows]

    def get_patient(self, patient_id: int) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return _patient_record(row) if row else None

    def create_patient(self, patient: Patient) -> dict:
        now = _now()
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO patients(name, age, medical_history, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (patient.name, patient.age, patient.medical_history, now, now),
            )
            row = connection.execute("SELECT * FROM patients WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _patient_record(row)

    def update_patient(self, patient_id: int, patient: Patient) -> dict | None:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE patients SET name = ?, age = ?, medical_history = ?, updated_at = ? WHERE id = ?",
                (patient.name, patient.age, patient.medical_history, _now(), patient_id),
            )
            row = connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone() if cursor.rowcount else None
        return _patient_record(row) if row else None

    def delete_patient(self, patient_id: int) -> bool:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        return cursor.rowcount > 0

    def create_order(self, patient_id: int, request: OrderCreate, tests: list[dict]) -> dict | None:
        with self.connection() as connection:
            if not connection.execute("SELECT 1 FROM patients WHERE id = ?", (patient_id,)).fetchone():
                return None
            cursor = connection.execute(
                "INSERT INTO orders(patient_id, tests_json, doctor_name, clinical_question, copies, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (patient_id, json.dumps(tests), request.doctor_name, request.clinical_question, request.copies, _now()),
            )
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _order_record(row)

    def list_orders(self, patient_id: int) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM orders WHERE patient_id = ? ORDER BY id DESC", (patient_id,)).fetchall()
        return [_order_record(row) for row in rows]

    def get_order(self, order_id: int) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return _order_record(row) if row else None

    def delete_order(self, patient_id: int, order_id: int) -> bool:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM orders WHERE id = ? AND patient_id = ?", (order_id, patient_id))
        return cursor.rowcount > 0

    def _cutoff(self, older_than_days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat(timespec="seconds")

    def purge_preview(self, older_than_days: int) -> int:
        with self.connection() as connection:
            row = connection.execute("SELECT COUNT(*) FROM patients WHERE created_at < ?", (self._cutoff(older_than_days),)).fetchone()
        return row[0]

    def purge(self, older_than_days: int) -> int:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM patients WHERE created_at < ?", (self._cutoff(older_than_days),))
        return cursor.rowcount
