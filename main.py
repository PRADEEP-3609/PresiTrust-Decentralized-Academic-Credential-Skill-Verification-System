"""
PresiTrust: Presidency University - Decentralized Academic Credential & Skill Verification System
FastAPI Backend Application with Role-Based Access Control, Merkle Tree Batching,
ECDSA Digital Signatures, and Zero-Trust Verification.
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr

from core.database import (
    init_db,
    get_db_connection,
    get_or_create_university_keys,
    log_audit
)
from core.crypto import (
    generate_did,
    generate_ecdsa_keypair,
    compute_credential_leaf_hash,
    MerkleTree,
    sign_payload,
    verify_credential_complete,
    create_did_document
)
from core.auth import (
    hash_password,
    verify_password,
    create_session,
    invalidate_session,
    get_current_user,
    require_user,
    require_role
)

app = FastAPI(
    title="PresiTrust - Presidency University Academic Credential & Skill Verification Ledger",
    description="PresiTrust: Cryptographically secured degree and skill verification platform utilizing W3C DIDs, Merkle Trees, and ECDSA signatures.",
    version="2.0.0"
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str  # 'admin', 'teacher', 'student'
    full_name: str
    identifier: str  # USN for student, Faculty ID for teacher, Employee ID for admin
    department: str
    sub_role: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class CredentialEndorseRequest(BaseModel):
    student_id: int
    degree_type: str  # e.g., 'B.Tech', 'BBA', 'BCA', 'MBA', 'M.Tech', 'B.Com'
    major_specialization: str
    cgpa: float
    completion_year: int
    honors: str
    credits_earned: int = 160
    skills: List[str]


class BatchSealRequest(BaseModel):
    credential_ids: Optional[List[str]] = None


class RevokeRequest(BaseModel):
    credential_id: str
    reason: str


# ---------------------------------------------------------------------------
# Startup & Health
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    init_db()
    get_or_create_university_keys()


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "institution": "Presidency University",
        "system": "PresiTrust - Decentralized Academic Credential Ledger",
        "timestamp": datetime.now().isoformat()
    }


# ---------------------------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------------------------

@app.post("/api/auth/register")
def register_user(req: RegisterRequest):
    role = req.role.lower().strip()
    if role not in ["admin", "teacher", "student"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin', 'teacher', or 'student'.")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check unique username and email
    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (req.username, req.email))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username or email already registered.")

    # Generate user cryptographic identity
    did = generate_did(role, req.identifier)
    priv_pem, pub_pem = generate_ecdsa_keypair()
    pwd_hash, salt = hash_password(req.password)
    now_iso = datetime.now().isoformat()

    sub_role_display = req.sub_role or (
        "Graduating Student" if role == "student" else (
            "Faculty Member" if role == "teacher" else "Registrar Staff"
        )
    )

    try:
        cursor.execute("""
        INSERT INTO users (
            username, email, password_hash, salt, role, full_name,
            identifier, department, sub_role, did, public_key_pem,
            private_key_pem, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.username, req.email, pwd_hash, salt, role,
            req.full_name, req.identifier.strip().upper(), req.department,
            sub_role_display, did, pub_pem, priv_pem, now_iso
        ))
        user_id = cursor.lastrowid
        conn.commit()

        user_data = {
            "id": user_id,
            "username": req.username,
            "email": req.email,
            "role": role,
            "full_name": req.full_name,
            "identifier": req.identifier.strip().upper(),
            "department": req.department,
            "sub_role": sub_role_display,
            "did": did,
            "public_key_pem": pub_pem
        }

        token = create_session(user_data)
        log_audit(req.full_name, role, "USER_REGISTERED", f"Created {role} account for {req.full_name} ({did}).")

        return {
            "success": True,
            "message": f"Successfully registered as {role.capitalize()} at Presidency University.",
            "token": token,
            "user": user_data
        }
    finally:
        conn.close()


@app.post("/api/auth/login")
def login_user(req: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (req.username, req.username))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(req.password, row["password_hash"], row["salt"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    user_data = {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "full_name": row["full_name"],
        "identifier": row["identifier"],
        "department": row["department"],
        "sub_role": row["sub_role"],
        "did": row["did"],
        "public_key_pem": row["public_key_pem"]
    }

    token = create_session(user_data)
    log_audit(row["full_name"], row["role"], "USER_LOGIN", f"User logged in from web portal.")

    return {
        "success": True,
        "token": token,
        "user": user_data
    }


@app.post("/api/auth/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        invalidate_session(token)
    return {"success": True, "message": "Logged out successfully."}


@app.get("/api/auth/me")
def get_current_user_profile(user: Dict[str, Any] = Depends(require_user)):
    return {"user": user}


# ---------------------------------------------------------------------------
# Degree & Skill Catalog
# ---------------------------------------------------------------------------

@app.get("/api/catalog/degrees")
def get_degrees_catalog():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM degrees_catalog ORDER BY degree_type, name")
    rows = cursor.fetchall()
    conn.close()

    catalog = []
    for r in rows:
        catalog.append({
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "degree_type": r["degree_type"],
            "school": r["school"],
            "duration_years": r["duration_years"],
            "specializations": json.loads(r["specializations"]),
            "default_skills": json.loads(r["default_skills"])
        })
    return {"catalog": catalog}


# ---------------------------------------------------------------------------
# Teacher / Faculty Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/teacher/students")
def get_students_list(user: Dict[str, Any] = Depends(require_role(["teacher", "admin"]))):
    """List students available for degree endorsement."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, identifier, department, did FROM users WHERE role = 'student' ORDER BY full_name")
    rows = cursor.fetchall()
    conn.close()

    students = [
        {
            "id": r["id"],
            "full_name": r["full_name"],
            "usn": r["identifier"],
            "department": r["department"],
            "did": r["did"]
        }
        for r in rows
    ]
    return {"students": students}


@app.post("/api/teacher/credentials/endorse")
def endorse_credential(req: CredentialEndorseRequest, teacher: Dict[str, Any] = Depends(require_role(["teacher"]))):
    """Faculty reviews, endorses and signs an academic credential draft."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student record
    cursor.execute("SELECT * FROM users WHERE id = ? AND role = 'student'", (req.student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Student record not found.")

    # Fetch teacher's private key to produce digital endorsement signature
    cursor.execute("SELECT private_key_pem FROM users WHERE id = ?", (teacher["user_id"],))
    teacher_row = cursor.fetchone()
    teacher_priv_pem = teacher_row["private_key_pem"] if teacher_row else None

    # Generate Credential ID
    clean_usn = student["identifier"].replace(" ", "").upper()
    degree_tag = req.degree_type.replace(".", "").upper()
    cred_id = f"PU-{req.completion_year}-{degree_tag}-{clean_usn}"

    # Construct canonical data payload
    credential_data = {
        "credential_id": cred_id,
        "student_usn": student["identifier"],
        "student_name": student["full_name"],
        "degree_type": req.degree_type,
        "major_specialization": req.major_specialization,
        "cgpa": f"{req.cgpa:.2f}",
        "completion_year": req.completion_year,
        "honors": req.honors,
        "skills": sorted(req.skills),
        "institution": "Presidency University"
    }

    # Compute leaf hash
    leaf_hash = compute_credential_leaf_hash(credential_data)

    # Produce teacher endorsement signature
    teacher_sig = sign_payload(teacher_priv_pem, leaf_hash) if teacher_priv_pem else "SIG_DUMMY"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Check if already exists
        cursor.execute("SELECT id FROM credentials WHERE credential_id = ?", (cred_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"A credential with ID {cred_id} already exists.")

        cursor.execute("""
        INSERT INTO credentials (
            credential_id, student_id, student_name, student_usn, student_did,
            degree_type, major_specialization, cgpa, completion_year, honors,
            credits_earned, skills, teacher_id, teacher_name, teacher_did,
            teacher_endorsement_sig, status, leaf_hash, merkle_proof, batch_id,
            block_number, created_at, issued_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cred_id, student["id"], student["full_name"], student["identifier"], student["did"],
            req.degree_type, req.major_specialization, req.cgpa, req.completion_year, req.honors,
            req.credits_earned, json.dumps(req.skills), teacher["user_id"], teacher["full_name"],
            teacher["did"], teacher_sig, "teacher_endorsed", leaf_hash, None, None,
            None, now_str, None
        ))
        conn.commit()

        log_audit(
            teacher["full_name"],
            "teacher",
            "CREDENTIAL_ENDORSED",
            f"Endorsed {req.degree_type} in {req.major_specialization} for {student['full_name']} ({student['identifier']})."
        )

        return {
            "success": True,
            "message": "Academic credential endorsed and signed successfully. Submitted to Presidency University Exam Controller for batch sealing.",
            "credential_id": cred_id,
            "leaf_hash": leaf_hash,
            "status": "teacher_endorsed"
        }
    finally:
        conn.close()


@app.get("/api/teacher/credentials/my-submissions")
def get_teacher_submissions(teacher: Dict[str, Any] = Depends(require_role(["teacher"]))):
    """View credentials endorsed by the logged-in faculty member."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM credentials WHERE teacher_id = ? ORDER BY id DESC
    """, (teacher["user_id"],))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "credential_id": r["credential_id"],
            "student_name": r["student_name"],
            "student_usn": r["student_usn"],
            "degree_type": r["degree_type"],
            "major_specialization": r["major_specialization"],
            "cgpa": r["cgpa"],
            "completion_year": r["completion_year"],
            "honors": r["honors"],
            "status": r["status"],
            "batch_id": r["batch_id"],
            "block_number": r["block_number"],
            "created_at": r["created_at"],
            "issued_at": r["issued_at"]
        })
    return {"submissions": items}


# ---------------------------------------------------------------------------
# Admin / Examination Controller Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/admin/pending-credentials")
def get_pending_credentials(admin: Dict[str, Any] = Depends(require_role(["admin"]))):
    """Retrieve all credentials awaiting Merkle tree batching and university signature."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM credentials WHERE status = 'teacher_endorsed' ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    pending = []
    for r in rows:
        pending.append({
            "id": r["id"],
            "credential_id": r["credential_id"],
            "student_name": r["student_name"],
            "student_usn": r["student_usn"],
            "degree_type": r["degree_type"],
            "major_specialization": r["major_specialization"],
            "cgpa": r["cgpa"],
            "completion_year": r["completion_year"],
            "honors": r["honors"],
            "skills": json.loads(r["skills"]) if r["skills"] else [],
            "teacher_name": r["teacher_name"],
            "leaf_hash": r["leaf_hash"],
            "created_at": r["created_at"]
        })
    return {"pending_credentials": pending}


@app.post("/api/admin/batches/create")
def create_batch_and_seal(req: BatchSealRequest, admin: Dict[str, Any] = Depends(require_role(["admin"]))):
    """
    Batches endorsed credentials into a cryptographic Merkle Tree,
    computes the Merkle Root, signs it with the University Private Key (ECDSA),
    generates inclusion proofs for each credential, and commits the batch to the ledger.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if req.credential_ids and len(req.credential_ids) > 0:
        placeholders = ",".join("?" for _ in req.credential_ids)
        cursor.execute(f"SELECT * FROM credentials WHERE status = 'teacher_endorsed' AND credential_id IN ({placeholders})", req.credential_ids)
    else:
        cursor.execute("SELECT * FROM credentials WHERE status = 'teacher_endorsed'")

    pending_creds = cursor.fetchall()
    if not pending_creds:
        conn.close()
        raise HTTPException(status_code=400, detail="No pending teacher-endorsed credentials available to batch.")

    univ_keys = get_or_create_university_keys()

    # Step 1: Collect Leaf Hashes
    leaf_hashes = [r["leaf_hash"] for r in pending_creds]

    # Step 2: Build Merkle Tree
    tree = MerkleTree(leaf_hashes)
    merkle_root = tree.get_root()

    # Step 3: Sign Merkle Root with Presidency University ECDSA Private Key
    univ_signature = sign_payload(univ_keys["private_key_pem"], merkle_root)

    # Step 4: Determine next Block Number
    cursor.execute("SELECT COALESCE(MAX(block_number), 100) AS max_block FROM batches")
    max_block = cursor.fetchone()["max_block"]
    next_block = max_block + 1

    batch_id = f"PU-BATCH-{datetime.now().strftime('%Y%m%d')}-{next_block:03d}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 5: Save Batch to ledger
    cursor.execute("""
    INSERT INTO batches (
        batch_id, merkle_root, signature, university_public_key, university_did,
        total_credentials, block_number, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        batch_id, merkle_root, univ_signature, univ_keys["public_key_pem"],
        univ_keys["did"], len(pending_creds), next_block, now_str
    ))

    # Step 6: Update each credential with its Merkle inclusion proof
    for idx, cred in enumerate(pending_creds):
        proof = tree.get_proof(idx)
        cursor.execute("""
        UPDATE credentials SET
            status = 'university_sealed',
            merkle_proof = ?,
            batch_id = ?,
            block_number = ?,
            issued_at = ?
        WHERE id = ?
        """, (
            json.dumps(proof), batch_id, next_block, now_str, cred["id"]
        ))

    conn.commit()
    conn.close()

    log_audit(
        admin["full_name"],
        "admin",
        "BATCH_SEALED",
        f"Sealed Batch {batch_id} (Block #{next_block}) with {len(pending_creds)} credentials. Merkle Root: {merkle_root[:16]}..."
    )

    return {
        "success": True,
        "message": f"Batch {batch_id} sealed and recorded to Ledger Block #{next_block}!",
        "batch_id": batch_id,
        "block_number": next_block,
        "total_sealed": len(pending_creds),
        "merkle_root": merkle_root,
        "university_signature": univ_signature
    }


@app.post("/api/admin/credentials/revoke")
def revoke_credential(req: RevokeRequest, admin: Dict[str, Any] = Depends(require_role(["admin"]))):
    """Revoke a credential with official reason and publish to revocation registry."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM credentials WHERE credential_id = ?", (req.credential_id,))
    cred = cursor.fetchone()
    if not cred:
        conn.close()
        raise HTTPException(status_code=404, detail="Credential not found.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("UPDATE credentials SET status = 'revoked' WHERE credential_id = ?", (req.credential_id,))
    cursor.execute("""
    INSERT OR REPLACE INTO revocations (credential_id, reason, revoked_by, revoked_at)
    VALUES (?, ?, ?, ?)
    """, (req.credential_id, req.reason, admin["full_name"], now_str))

    conn.commit()
    conn.close()

    log_audit(
        admin["full_name"],
        "admin",
        "CREDENTIAL_REVOKED",
        f"Revoked credential {req.credential_id}. Reason: {req.reason}"
    )

    return {
        "success": True,
        "message": f"Credential {req.credential_id} successfully revoked.",
        "revocation": {
            "credential_id": req.credential_id,
            "reason": req.reason,
            "revoked_by": admin["full_name"],
            "revoked_at": now_str
        }
    }


@app.get("/api/admin/stats")
def get_admin_stats(admin: Dict[str, Any] = Depends(require_role(["admin"]))):
    """System-wide metrics and dashboard counts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS c FROM credentials WHERE status = 'university_sealed'")
    total_issued = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM credentials WHERE status = 'teacher_endorsed'")
    pending_endorsements = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM batches")
    total_batches = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'student'")
    total_students = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'teacher'")
    total_teachers = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM revocations")
    total_revoked = cursor.fetchone()["c"]

    conn.close()

    return {
        "total_issued": total_issued,
        "pending_endorsements": pending_endorsements,
        "total_batches": total_batches,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_revoked": total_revoked
    }


@app.get("/api/admin/audit-logs")
def get_audit_logs(admin: Dict[str, Any] = Depends(require_role(["admin"]))):
    """Retrieve recent 50 immutable audit logs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()

    return {"logs": [dict(r) for r in rows]}


@app.get("/api/admin/university-identity")
def get_university_identity():
    """Retrieve Presidency University master DID document and cryptographic parameters."""
    keys = get_or_create_university_keys()
    did_doc = create_did_document(keys["did"], keys["public_key_pem"])
    return {
        "institution": "Presidency University",
        "did": keys["did"],
        "did_document": did_doc,
        "public_key_pem": keys["public_key_pem"],
        "established": 2013,
        "location": "Bengaluru, Karnataka, India"
    }


# ---------------------------------------------------------------------------
# Student Portal Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/student/credentials")
def get_student_credentials(student: Dict[str, Any] = Depends(require_role(["student"]))):
    """Retrieve all academic credentials & skill badges belonging to the authenticated student."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM credentials WHERE student_id = ? ORDER BY id DESC
    """, (student["user_id"],))
    rows = cursor.fetchall()
    conn.close()

    credentials = []
    for r in rows:
        credentials.append({
            "id": r["id"],
            "credential_id": r["credential_id"],
            "student_name": r["student_name"],
            "student_usn": r["student_usn"],
            "student_did": r["student_did"],
            "degree_type": r["degree_type"],
            "major_specialization": r["major_specialization"],
            "cgpa": r["cgpa"],
            "completion_year": r["completion_year"],
            "honors": r["honors"],
            "credits_earned": r["credits_earned"],
            "skills": json.loads(r["skills"]) if r["skills"] else [],
            "teacher_name": r["teacher_name"],
            "teacher_did": r["teacher_did"],
            "status": r["status"],
            "leaf_hash": r["leaf_hash"],
            "merkle_proof": json.loads(r["merkle_proof"]) if r["merkle_proof"] else [],
            "batch_id": r["batch_id"],
            "block_number": r["block_number"],
            "issued_at": r["issued_at"]
        })

    return {"credentials": credentials}


@app.get("/api/student/credential/{credential_id}/export")
def export_verifiable_credential(credential_id: str):
    """
    Export a tamper-proof, W3C-standard Verifiable Credential JSON package
    including canonical attributes, Merkle tree inclusion proof, and Presidency University root signature.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credentials WHERE credential_id = ?", (credential_id,))
    cred = cursor.fetchone()

    if not cred:
        conn.close()
        raise HTTPException(status_code=404, detail="Credential not found.")

    # Retrieve batch signature and Merkle root
    batch_root = None
    batch_sig = None
    if cred["batch_id"]:
        cursor.execute("SELECT merkle_root, signature FROM batches WHERE batch_id = ?", (cred["batch_id"],))
        batch_row = cursor.fetchone()
        if batch_row:
            batch_root = batch_row["merkle_root"]
            batch_sig = batch_row["signature"]

    univ_keys = get_or_create_university_keys()
    conn.close()

    skills_list = json.loads(cred["skills"]) if cred["skills"] else []
    proof_steps = json.loads(cred["merkle_proof"]) if cred["merkle_proof"] else []

    vc = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://presidencyuniversity.in/credentials/v1"
        ],
        "id": f"urn:uuid:{cred['credential_id']}",
        "type": ["VerifiableCredential", "AcademicDegreeCredential"],
        "issuer": {
            "id": univ_keys["did"],
            "name": "Presidency University",
            "location": "Bengaluru, Karnataka, India"
        },
        "issuanceDate": cred["issued_at"] or cred["created_at"],
        "credentialSubject": {
            "id": cred["student_did"],
            "credential_id": cred["credential_id"],
            "student_name": cred["student_name"],
            "student_usn": cred["student_usn"],
            "degree_type": cred["degree_type"],
            "major_specialization": cred["major_specialization"],
            "cgpa": f"{cred['cgpa']:.2f}",
            "completion_year": cred["completion_year"],
            "honors": cred["honors"],
            "credits_earned": cred["credits_earned"],
            "skills": skills_list,
            "institution": "Presidency University"
        },
        "leaf_hash": cred["leaf_hash"],
        "merkleAudit": {
            "batch_id": cred["batch_id"],
            "block_number": cred["block_number"],
            "merkle_root": batch_root,
            "inclusion_proof": proof_steps
        },
        "proof": {
            "type": "EcdsaSecp256k1Signature2019",
            "created": cred["issued_at"] or cred["created_at"],
            "verificationMethod": f"{univ_keys['did']}#keys-1",
            "proofPurpose": "assertionMethod",
            "proofValue": batch_sig
        }
    }

    return vc


# ---------------------------------------------------------------------------
# Public Zero-Trust Verification Engine (No Login Required)
# ---------------------------------------------------------------------------

@app.post("/api/verify/credential")
async def verify_credential_endpoint(request: Request):
    """
    Public Verification API:
    Accepts raw Verifiable Credential JSON payload or a credential ID.
    Executes the 4-tier cryptographic verification pipeline in < 50ms.
    """
    start_time = time.perf_counter()

    body = await request.json()
    cred_id = None
    cred_payload = None

    if "credentialSubject" in body:
        # Full W3C Verifiable Credential object
        cred_payload = body["credentialSubject"]
        cred_id = cred_payload.get("credential_id")
        leaf_hash = body.get("leaf_hash")
        merkle_proof = body.get("merkleAudit", {}).get("inclusion_proof", [])
        merkle_root = body.get("merkleAudit", {}).get("merkle_root", "")
        signature = body.get("proof", {}).get("proofValue", "")
        batch_id = body.get("merkleAudit", {}).get("batch_id")
        block_number = body.get("merkleAudit", {}).get("block_number")
    elif "credential_id" in body and "degree_type" not in body:
        # User entered credential ID or USN search
        cred_id = body["credential_id"].strip()
    else:
        # Raw credential object
        cred_payload = body
        cred_id = body.get("credential_id")
        leaf_hash = body.get("leaf_hash")
        merkle_proof = body.get("merkle_proof", [])
        merkle_root = body.get("merkle_root", "")
        signature = body.get("signature", "")
        batch_id = body.get("batch_id")
        block_number = body.get("block_number")

    # If queried by ID, load from database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.*, b.merkle_root AS b_root, b.signature AS b_sig
    FROM credentials c
    LEFT JOIN batches b ON c.batch_id = b.batch_id
    WHERE c.credential_id = ? OR c.student_usn = ?
    """, (cred_id, cred_id))
    db_cred = cursor.fetchone()

    # Check revocation status
    cursor.execute("SELECT * FROM revocations WHERE credential_id = ?", (cred_id,))
    revocation = cursor.fetchone()
    is_revoked = revocation is not None

    univ_keys = get_or_create_university_keys()
    conn.close()

    if not cred_payload and not db_cred:
        raise HTTPException(status_code=404, detail=f"No academic credential found matching '{cred_id}'.")

    # If payload wasn't fully supplied in request, populate from DB
    if not cred_payload and db_cred:
        cred_payload = {
            "credential_id": db_cred["credential_id"],
            "student_usn": db_cred["student_usn"],
            "student_name": db_cred["student_name"],
            "degree_type": db_cred["degree_type"],
            "major_specialization": db_cred["major_specialization"],
            "cgpa": f"{db_cred['cgpa']:.2f}",
            "completion_year": db_cred["completion_year"],
            "honors": db_cred["honors"],
            "skills": json.loads(db_cred["skills"]) if db_cred["skills"] else [],
            "institution": "Presidency University",
            "leaf_hash": db_cred["leaf_hash"]
        }
        leaf_hash = db_cred["leaf_hash"]
        merkle_proof = json.loads(db_cred["merkle_proof"]) if db_cred["merkle_proof"] else []
        merkle_root = db_cred["b_root"] or ""
        signature = db_cred["b_sig"] or ""
        batch_id = db_cred["batch_id"]
        block_number = db_cred["block_number"]

    # Run cryptographic verification
    audit_results = verify_credential_complete(
        credential_payload=cred_payload,
        merkle_proof=merkle_proof,
        merkle_root=merkle_root,
        root_signature=signature,
        university_public_key_pem=univ_keys["public_key_pem"],
        is_revoked=is_revoked
    )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    audit_results["verification_time_ms"] = elapsed_ms
    audit_results["timestamp_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    response_data = {
        "success": True,
        "overall_verified": audit_results["overall_verified"],
        "verification_metrics": {
            "verification_time_ms": elapsed_ms,
            "verification_speed_comparison": "Reduced verification time from ~14 days (traditional manual background checks) to under 50 milliseconds.",
            "steps": [
                {
                    "step": 1,
                    "title": "Payload Canonical SHA-256 Hash Integrity",
                    "passed": audit_results["step1_hash_integrity"],
                    "description": "Recalculates deterministic SHA-256 hash of credential subject fields to detect any tampering with grades, name, or degree.",
                    "computed_hash": audit_results["recomputed_leaf_hash"]
                },
                {
                    "step": 2,
                    "title": "Merkle Tree Inclusion Proof Traversal",
                    "passed": audit_results["step2_merkle_inclusion"],
                    "description": "Traverses sibling cryptographic hashes along the Merkle proof path to verify inclusion in the University batch root without exposing other students' private records.",
                    "proof_steps_count": len(merkle_proof) if merkle_proof else 0
                },
                {
                    "step": 3,
                    "title": "Presidency University ECDSA Signature Verification",
                    "passed": audit_results["step3_university_signature"],
                    "description": "Cryptographically verifies the University Exam Controller's SECP256k1 digital signature against the institutional Public Key.",
                    "institution_did": univ_keys["did"]
                },
                {
                    "step": 4,
                    "title": "On-Chain Revocation Registry Check",
                    "passed": audit_results["step4_revocation_status"],
                    "description": "Queries the decentralized revocation ledger to confirm the degree has not been revoked due to academic dishonesty or disciplinary action.",
                    "is_revoked": is_revoked,
                    "revocation_reason": revocation["reason"] if is_revoked else None
                }
            ]
        },
        "credential_details": {
            "credential_id": cred_payload.get("credential_id"),
            "student_name": cred_payload.get("student_name"),
            "student_usn": cred_payload.get("student_usn"),
            "degree_type": cred_payload.get("degree_type"),
            "major_specialization": cred_payload.get("major_specialization"),
            "cgpa": cred_payload.get("cgpa"),
            "completion_year": cred_payload.get("completion_year"),
            "honors": cred_payload.get("honors"),
            "skills": cred_payload.get("skills", []),
            "institution": "Presidency University",
            "batch_id": batch_id,
            "block_number": block_number
        },
        "cryptographic_proofs": {
            "leaf_hash": audit_results["recomputed_leaf_hash"],
            "merkle_root": merkle_root,
            "root_signature": signature[:32] + "..." if signature else "",
            "university_did": univ_keys["did"]
        },
        "reasons": audit_results["reasons"]
    }

    return response_data


# ---------------------------------------------------------------------------
# Blockchain Ledger Explorer
# ---------------------------------------------------------------------------

@app.get("/api/ledger/blocks")
def get_ledger_blocks():
    """Public blockchain explorer endpoint displaying all sealed blocks and Merkle roots."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM batches ORDER BY block_number DESC")
    rows = cursor.fetchall()
    conn.close()

    blocks = []
    for r in rows:
        blocks.append({
            "block_number": r["block_number"],
            "batch_id": r["batch_id"],
            "merkle_root": r["merkle_root"],
            "signature": r["signature"],
            "university_did": r["university_did"],
            "total_credentials": r["total_credentials"],
            "created_at": r["created_at"]
        })
    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Static Web Assets Serving
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Presidency University Credential Verification System API is running."}
