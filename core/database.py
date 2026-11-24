"""
PresiTrust: Presidency University - Database & Storage Layer
SQLite storage for users, degrees catalog, credentials, Merkle batches, revocations, and audit logs.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

def get_default_db_path() -> str:
    """Determine the optimal database path, supporting local dev and Vercel serverless /tmp."""
    if "PRESIDENCY_DB_PATH" in os.environ:
        return os.environ["PRESIDENCY_DB_PATH"]
    
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/presidency_credentials.db"

    local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "presidency_credentials.db")
    try:
        # Test if we can open/create the file in the workspace directory
        test_conn = sqlite3.connect(local_path)
        test_conn.execute("CREATE TABLE IF NOT EXISTS _test_probe (id INT)")
        test_conn.execute("DROP TABLE IF EXISTS _test_probe")
        test_conn.close()
        return local_path
    except (sqlite3.OperationalError, PermissionError, OSError):
        # On Linux/Unix (like Vercel containers), /tmp is the writable storage
        if os.name != 'nt':
            return "/tmp/presidency_credentials.db"
        # On Windows fallback to user home directory
        home_path = os.path.join(os.path.expanduser("~"), ".presidency_credentials.db")
        return home_path

DB_PATH = get_default_db_path()


def get_db_connection():
    """Create a thread-safe connection to SQLite with row dictionary factory."""
    global DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
    except (sqlite3.OperationalError, PermissionError, OSError):
        if os.name != 'nt':
            DB_PATH = "/tmp/presidency_credentials.db"
        else:
            DB_PATH = os.path.join(os.path.expanduser("~"), ".presidency_credentials.db")
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize database tables and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. System Keys (Presidency University Master Keys)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_keys (
        key_name TEXT PRIMARY KEY,
        did TEXT NOT NULL,
        private_key_pem TEXT NOT NULL,
        public_key_pem TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Users Table (Supports Admin, Teacher, Student)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL,          -- 'admin', 'teacher', 'student'
        full_name TEXT NOT NULL,
        identifier TEXT NOT NULL,    -- USN for student, Faculty ID for teacher, Employee ID for admin
        department TEXT NOT NULL,
        sub_role TEXT,               -- 'Dean', 'Associate Professor', 'Registrar', 'Student'
        did TEXT UNIQUE NOT NULL,
        public_key_pem TEXT,
        private_key_pem TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 3. Degrees Catalog
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS degrees_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        degree_type TEXT NOT NULL,   -- 'B.Tech', 'BBA', 'BCA', 'MBA', 'M.Tech', 'B.Com', 'Ph.D.'
        school TEXT NOT NULL,
        duration_years INTEGER NOT NULL,
        specializations TEXT NOT NULL, -- JSON list
        default_skills TEXT NOT NULL   -- JSON list
    )
    """)

    # 4. Credentials Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credentials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credential_id TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL REFERENCES users(id),
        student_name TEXT NOT NULL,
        student_usn TEXT NOT NULL,
        student_did TEXT NOT NULL,
        degree_type TEXT NOT NULL,
        major_specialization TEXT NOT NULL,
        cgpa REAL NOT NULL,
        completion_year INTEGER NOT NULL,
        honors TEXT NOT NULL,
        credits_earned INTEGER NOT NULL DEFAULT 160,
        skills TEXT NOT NULL,        -- JSON list of verified skills
        teacher_id INTEGER REFERENCES users(id),
        teacher_name TEXT,
        teacher_did TEXT,
        teacher_endorsement_sig TEXT,
        status TEXT NOT NULL,        -- 'draft', 'teacher_endorsed', 'university_sealed', 'revoked'
        leaf_hash TEXT,
        merkle_proof TEXT,           -- JSON list of proof steps
        batch_id TEXT,
        block_number INTEGER,
        created_at TEXT NOT NULL,
        issued_at TEXT
    )
    """)

    # 5. Merkle Batches (Blocks on ledger)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT UNIQUE NOT NULL,
        merkle_root TEXT NOT NULL,
        signature TEXT NOT NULL,
        university_public_key TEXT NOT NULL,
        university_did TEXT NOT NULL,
        total_credentials INTEGER NOT NULL,
        block_number INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # 6. Revocation Registry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credential_id TEXT UNIQUE NOT NULL,
        reason TEXT NOT NULL,
        revoked_by TEXT NOT NULL,
        revoked_at TEXT NOT NULL
    )
    """)

    # 7. Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        actor_name TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def log_audit(actor_name: str, actor_role: str, action: str, details: str):
    """Record an immutable audit log entry."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO audit_logs (timestamp, actor_name, actor_role, action, details) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor_name, actor_role, action, details)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# University Master Key Storage
# ---------------------------------------------------------------------------

def get_or_create_university_keys():
    """Retrieve Presidency University master signing keys, or create if first run."""
    from core.crypto import generate_ecdsa_keypair
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_keys WHERE key_name = 'presidency_master'")
    row = cursor.fetchone()
    if row:
        conn.close()
        return {
            "did": row["did"],
            "private_key_pem": row["private_key_pem"],
            "public_key_pem": row["public_key_pem"],
            "created_at": row["created_at"]
        }

    # Generate new master university keypair
    private_pem, public_pem = generate_ecdsa_keypair()
    now_str = datetime.now().isoformat()
    did = "did:presidency:institution:main"

    cursor.execute(
        "INSERT INTO system_keys (key_name, did, private_key_pem, public_key_pem, created_at) VALUES (?, ?, ?, ?, ?)",
        ("presidency_master", did, private_pem, public_pem, now_str)
    )
    conn.commit()
    conn.close()

    log_audit("SYSTEM", "admin", "KEYPAIR_INITIALIZATION", "Generated Presidency University master ECDSA SECP256k1 keypair.")
    return {
        "did": did,
        "private_key_pem": private_pem,
        "public_key_pem": public_pem,
        "created_at": now_str
    }
