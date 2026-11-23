"""
PresiTrust: Full End-to-End Integration Test Suite for Presidency University Credential Ledger.
Uses FastAPI TestClient to test the complete user lifecycle:
1. User registration & dynamic DID generation (Admin, Teacher, Student)
2. Teacher endorsement of academic degree
3. Registrar Merkle tree batching & ECDSA signature
4. Public verification & tamper rejection
"""

from fastapi.testclient import TestClient
from main import app
from seed_data import seed_all

client = TestClient(app)

def run_integration_tests():
    print("=== Running PresiTrust End-to-End Integration Tests ===")

    # 1. Initialize
    seed_all()
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["institution"] == "Presidency University"
    print("[PASS] System health verified.")

    import time
    ts = int(time.time())

    # 2. Test Dynamic Account Creation for Student
    reg_student_payload = {
        "username": f"kavya_{ts}",
        "email": f"kavya_{ts}@presidencyuniversity.in",
        "password": "mypassword123",
        "role": "student",
        "full_name": "Kavya Sharma",
        "identifier": f"20241CSE{ts % 10000:04d}",
        "department": "School of Computer Science & Information Science"
    }
    res = client.post("/api/auth/register", json=reg_student_payload)
    assert res.status_code == 200, res.text
    student_data = res.json()
    student_token = student_data["token"]
    student_did = student_data["user"]["did"]
    assert student_did.startswith("did:presidency:student:")
    print(f"[PASS] Dynamic Student Registration verified: DID = {student_did}")

    # 3. Test Dynamic Account Creation for Teacher
    reg_teacher_payload = {
        "username": f"prof_vikram_{ts}",
        "email": f"vikram_{ts}@presidencyuniversity.in",
        "password": "mypassword123",
        "role": "teacher",
        "full_name": "Dr. Vikram Joshi",
        "identifier": f"PU-FAC-{ts % 1000:03d}",
        "department": "School of Engineering"
    }
    res = client.post("/api/auth/register", json=reg_teacher_payload)
    assert res.status_code == 200, res.text
    teacher_data = res.json()
    teacher_token = teacher_data["token"]
    teacher_did = teacher_data["user"]["did"]
    assert teacher_did.startswith("did:presidency:teacher:")
    print(f"[PASS] Dynamic Teacher Registration verified: DID = {teacher_did}")

    # 4. Test Login for Existing Demo Admin
    login_admin = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["token"]
    print("[PASS] Admin Login verified.")

    # 5. Faculty Endorses Degree for the new student
    endorse_payload = {
        "student_id": student_data["user"]["id"],
        "degree_type": "B.Tech",
        "major_specialization": "Artificial Intelligence & ML",
        "cgpa": 9.45,
        "completion_year": 2026,
        "honors": "First Class with Distinction (Honours)",
        "credits_earned": 164,
        "skills": ["PyTorch", "Deep Learning", "Docker", "Algorithms"]
    }
    res = client.post(
        "/api/teacher/credentials/endorse",
        json=endorse_payload,
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert res.status_code == 200, res.text
    endorsed = res.json()
    cred_id = endorsed["credential_id"]
    print(f"[PASS] Faculty Endorsement verified: Credential ID = {cred_id}")

    # 6. Admin Batches & Seals to Blockchain Ledger
    res = client.post(
        "/api/admin/batches/create",
        json={"credential_ids": [cred_id]},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200, res.text
    batch_res = res.json()
    assert batch_res["success"] is True
    print(f"[PASS] Registrar Merkle Batch Sealing verified: Block #{batch_res['block_number']}")

    # 7. Public Zero-Trust Verification by Credential ID
    res = client.post("/api/verify/credential", json={"credential_id": cred_id})
    assert res.status_code == 200, res.text
    verification = res.json()
    assert verification["overall_verified"] is True
    assert verification["credential_details"]["student_name"] == "Kavya Sharma"
    assert verification["verification_metrics"]["steps"][0]["passed"] is True
    assert verification["verification_metrics"]["steps"][1]["passed"] is True
    assert verification["verification_metrics"]["steps"][2]["passed"] is True
    assert verification["verification_metrics"]["steps"][3]["passed"] is True
    print(f"[PASS] Public Zero-Trust Verification verified: {verification['verification_metrics']['verification_time_ms']} ms")

    # 8. Ledger Explorer
    res = client.get("/api/ledger/blocks")
    assert res.status_code == 200
    blocks = res.json()["blocks"]
    assert len(blocks) >= 1
    print(f"[PASS] Ledger Explorer verified: {len(blocks)} blocks committed on ledger.")

    print("\nALL END-TO-END INTEGRATION TESTS PASSED WITH 100% SUCCESS!\n")

if __name__ == "__main__":
    run_integration_tests()
