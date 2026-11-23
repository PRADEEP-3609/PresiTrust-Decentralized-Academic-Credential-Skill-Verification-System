"""
PresiTrust: Test suite for Presidency University Cryptographic Verification Engine.
Validates:
1. DID resolution
2. SHA-256 canonical hashing & Merkle tree root calculation
3. Merkle inclusion proof verification
4. ECDSA secp256k1 key generation, signing & verification
5. Tamper detection (e.g., GPA or degree modification)
"""

from core.crypto import (
    generate_did,
    generate_ecdsa_keypair,
    compute_credential_leaf_hash,
    MerkleTree,
    sign_payload,
    verify_payload_signature,
    verify_credential_complete
)


def test_crypto_pipeline():
    print("=== Testing PresiTrust Cryptographic Engine ===")

    # 1. Test DIDs
    student_did = generate_did("student", "20231CSE0001")
    univ_did = generate_did("admin", "main")
    assert student_did.startswith("did:presidency:student:"), f"Invalid student DID: {student_did}"
    assert univ_did == "did:presidency:institution:main", f"Invalid institution DID: {univ_did}"
    print("[PASS] DID generation verified.")

    # 2. Test ECDSA Signatures
    priv_pem, pub_pem = generate_ecdsa_keypair()
    test_msg = "Presidency University Degree Batch #101"
    sig = sign_payload(priv_pem, test_msg)
    assert verify_payload_signature(pub_pem, sig, test_msg) is True, "Signature verification failed!"
    assert verify_payload_signature(pub_pem, sig, "Altered Degree Batch") is False, "Altered payload should fail!"
    print("[PASS] ECDSA SECP256k1 signing & verification verified.")

    # 3. Test Merkle Tree
    leaf1 = compute_credential_leaf_hash({
        "credential_id": "PU-CRED-01",
        "student_usn": "20211CSE0452",
        "student_name": "Arjun Reddy",
        "degree_type": "B.Tech",
        "major_specialization": "Artificial Intelligence & ML",
        "cgpa": 9.24,
        "completion_year": 2025,
        "honors": "First Class with Distinction",
        "skills": ["PyTorch", "Deep Learning"],
        "institution": "Presidency University"
    })

    leaf2 = compute_credential_leaf_hash({
        "credential_id": "PU-CRED-02",
        "student_usn": "20221BBA0189",
        "student_name": "Priya Nair",
        "degree_type": "BBA",
        "major_specialization": "Business Analytics",
        "cgpa": 8.85,
        "completion_year": 2026,
        "honors": "First Class with Distinction",
        "skills": ["Tableau", "Financial Modeling"],
        "institution": "Presidency University"
    })

    leaf3 = "f" * 64
    leaf4 = "e" * 64

    tree = MerkleTree([leaf1, leaf2, leaf3, leaf4])
    root = tree.get_root()
    proof0 = tree.get_proof(0)
    proof1 = tree.get_proof(1)

    assert MerkleTree.verify_proof(leaf1, proof0, root) is True, "Merkle proof 0 failed!"
    assert MerkleTree.verify_proof(leaf2, proof1, root) is True, "Merkle proof 1 failed!"
    assert MerkleTree.verify_proof(leaf1, proof1, root) is False, "Cross-proof verification should fail!"
    print(f"[PASS] Merkle Tree verified. Root: {root[:16]}...")

    # 4. Test Complete 4-Step Verification Pipeline
    root_signature = sign_payload(priv_pem, root)

    cred_payload = {
        "credential_id": "PU-CRED-01",
        "student_usn": "20211CSE0452",
        "student_name": "Arjun Reddy",
        "degree_type": "B.Tech",
        "major_specialization": "Artificial Intelligence & ML",
        "cgpa": 9.24,
        "completion_year": 2025,
        "honors": "First Class with Distinction",
        "skills": ["PyTorch", "Deep Learning"],
        "institution": "Presidency University",
        "leaf_hash": leaf1
    }

    audit_result = verify_credential_complete(
        credential_payload=cred_payload,
        merkle_proof=proof0,
        merkle_root=root,
        root_signature=root_signature,
        university_public_key_pem=pub_pem,
        is_revoked=False
    )
    assert audit_result["overall_verified"] is True, f"Full verification should succeed: {audit_result}"
    print("[PASS] 4-Tier Zero-Trust verification passed for authentic credential.")

    # 5. Test Tamper Resistance (Simulate student modifying CGPA from 9.24 to 9.99)
    tampered_payload = dict(cred_payload)
    tampered_payload["cgpa"] = 9.99
    tampered_result = verify_credential_complete(
        credential_payload=tampered_payload,
        merkle_proof=proof0,
        merkle_root=root,
        root_signature=root_signature,
        university_public_key_pem=pub_pem,
        is_revoked=False
    )
    assert tampered_result["overall_verified"] is False, "Tampered payload MUST fail verification!"
    assert tampered_result["step1_hash_integrity"] is False, "Step 1 must catch hash mismatch!"
    print("[PASS] Tamper resistance verified: altered CGPA successfully caught and rejected.")

    print("\nALL CRYPTOGRAPHIC TESTS PASSED WITH 100% SUCCESS!\n")


if __name__ == "__main__":
    test_crypto_pipeline()
