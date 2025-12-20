import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class Call(BaseModel):
    id: str
    name: str
    transcript: str
    duration_seconds: int
    recording_url: Optional[str] = None
    created_at: str

class ExpectedOutput(BaseModel):
    id: str
    call_id: str
    segment_start: Optional[int] = None
    segment_end: Optional[int] = None
    tie_downs: List[str]
    script_position: str
    should_flag: List[str]
    suggested_response: str
    notes: Optional[str] = None

class TestRun(BaseModel):
    id: str
    call_id: str
    expected_id: str
    model: str
    script_version: str
    raw_output: str
    created_at: str

class TestResult(BaseModel):
    id: str
    test_run_id: str
    caught_tie_downs: bool
    correct_position: bool
    correct_flags: bool
    good_suggestion: bool
    overall_pass: bool
    notes: Optional[str] = None

class ValidationDB:
    def __init__(self, db_path: str = "validation.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # SQLite compatible schema
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS calls (
                id TEXT PRIMARY KEY,
                name TEXT,
                transcript TEXT,
                duration_seconds INTEGER,
                recording_url TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS expected_outputs (
                id TEXT PRIMARY KEY,
                call_id TEXT REFERENCES calls(id),
                segment_start INTEGER,
                segment_end INTEGER,
                tie_downs TEXT,              -- JSON stored as text
                script_position TEXT,
                should_flag TEXT,            -- JSON stored as text
                suggested_response TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS test_runs (
                id TEXT PRIMARY KEY,
                call_id TEXT REFERENCES calls(id),
                expected_id TEXT REFERENCES expected_outputs(id),
                model TEXT,
                script_version TEXT,
                raw_output TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS test_results (
                id TEXT PRIMARY KEY,
                test_run_id TEXT REFERENCES test_runs(id),
                caught_tie_downs BOOLEAN,
                correct_position BOOLEAN,
                correct_flags BOOLEAN,
                good_suggestion BOOLEAN,
                overall_pass BOOLEAN,
                notes TEXT
            );
        """)
        conn.commit()
        conn.close()

    # --- CRUD Operations ---

    def add_call(self, name: str, transcript: str, duration: int, url: str = None) -> str:
        call_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self.get_connection()
        conn.execute(
            "INSERT INTO calls (id, name, transcript, duration_seconds, recording_url, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (call_id, name, transcript, duration, url, created_at)
        )
        conn.commit()
        conn.close()
        return call_id

    def add_expected_output(self, call_id: str, tie_downs: List[str], script_pos: str, flags: List[str], suggestion: str, notes: str = None, start: int = None, end: int = None) -> str:
        out_id = str(uuid.uuid4())
        
        conn = self.get_connection()
        conn.execute(
            """INSERT INTO expected_outputs 
               (id, call_id, segment_start, segment_end, tie_downs, script_position, should_flag, suggested_response, notes) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (out_id, call_id, start, end, json.dumps(tie_downs), script_pos, json.dumps(flags), suggestion, notes)
        )
        conn.commit()
        conn.close()
        return out_id

    def log_test_run(self, call_id: str, expected_id: str, model: str, script_ver: str, raw_output: str) -> str:
        run_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self.get_connection()
        conn.execute(
            """INSERT INTO test_runs 
               (id, call_id, expected_id, model, script_version, raw_output, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (run_id, call_id, expected_id, model, script_ver, raw_output, created_at)
        )
        conn.commit()
        conn.close()
        return run_id

    def log_result(self, run_id: str, caught_ties: bool, correct_pos: bool, correct_flags: bool, good_sugg: bool, passed: bool, notes: str = None) -> str:
        res_id = str(uuid.uuid4())
        
        conn = self.get_connection()
        conn.execute(
            """INSERT INTO test_results 
               (id, test_run_id, caught_tie_downs, correct_position, correct_flags, good_suggestion, overall_pass, notes) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (res_id, run_id, caught_ties, correct_pos, correct_flags, good_sugg, passed, notes)
        )
        conn.commit()
        conn.close()
        return res_id

    def get_call(self, call_id: str) -> Optional[Dict]:
        conn = self.get_connection()
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_calls(self) -> List[Dict]:
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM calls").fetchall()
        conn.close()
        return [dict(row) for row in rows]
