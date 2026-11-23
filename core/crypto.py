"""
PresiTrust: Presidency University - Cryptographic Verification Engine
Implements:
1. W3C-compliant Decentralized Identifiers (DIDs)
2. ECDSA Digital Signatures (SECP256k1 Curve)
3. Merkle Tree Batch Hashing & Inclusion Proofs (SHA-256)
4. Multi-step Verification Engine
"""

import hashlib
import json
import base64
from typing import List, Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature


def canonical_json(data: Any) -> str:
    """Serialize data into canonical JSON for deterministic SHA-256 hashing."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def sha256_hash(data: Any) -> str:
    """Compute SHA-256 hash of a string, bytes, or dictionary."""
    if isinstance(data, (dict, list)):
        data_bytes = canonical_json(data).encode('utf-8')
    elif isinstance(data, str):
        data_bytes = data.encode('utf-8')
    elif isinstance(data, bytes):
        data_bytes = data
    else:
        data_bytes = str(data).encode('utf-8')
    return hashlib.sha256(data_bytes).hexdigest()


# ---------------------------------------------------------------------------
# 1. Decentralized Identity (DID) Engine
# ---------------------------------------------------------------------------

def generate_did(role: str, identifier: str) -> str:
    """
    Generate a W3C-style DID for Presidency University entities.
    Examples:
      - did:presidency:institution:main
      - did:presidency:student:a1b2c3d4...
      - did:presidency:teacher:e5f6g7h8...
    """
    clean_role = role.lower().strip()
    if clean_role in ["admin", "institution"]:
        return "did:presidency:institution:main"
    
    hash_prefix = hashlib.sha256(identifier.strip().upper().encode('utf-8')).hexdigest()[:20]
    return f"did:presidency:{clean_role}:{hash_prefix}"


def create_did_document(did: str, public_key_pem: str, controller: str = "did:presidency:institution:main") -> Dict[str, Any]:
    """Generate a standard W3C DID Document."""
    return {
        "@context": "https://www.w3.org/ns/did/v1",
        "id": did,
        "controller": controller,
        "verificationMethod": [
            {
                "id": f"{did}#keys-1",
                "type": "EcdsaSecp256k1VerificationKey2019",
                "controller": did,
                "publicKeyPem": public_key_pem
            }
        ],
        "authentication": [f"{did}#keys-1"],
        "assertionMethod": [f"{did}#keys-1"]
    }


# ---------------------------------------------------------------------------
# 2. ECDSA Digital Signatures (SECP256k1)
# ---------------------------------------------------------------------------

def generate_ecdsa_keypair() -> Tuple[str, str]:
    """Generate a new ECDSA SECP256k1 keypair (PEM formatted strings)."""
    private_key = ec.generate_private_key(ec.SECP256K1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return private_pem, public_pem


def sign_payload(private_key_pem: str, payload: Any) -> str:
    """
    Sign a payload (string, hash, or dict) using an ECDSA private key.
    Returns URL-safe Base64 encoded DER signature.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None
    )
    if isinstance(payload, (dict, list)):
        data_bytes = canonical_json(payload).encode('utf-8')
    elif isinstance(payload, str):
        data_bytes = payload.encode('utf-8')
    else:
        data_bytes = bytes(payload)

    signature = private_key.sign(data_bytes, ec.ECDSA(hashes.SHA256()))
    return base64.urlsafe_b64encode(signature).decode('utf-8')


def verify_payload_signature(public_key_pem: str, signature_b64: str, payload: Any) -> bool:
    """Verify an ECDSA signature against the provided public key."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
        signature = base64.urlsafe_b64decode(signature_b64.encode('utf-8'))
        
        if isinstance(payload, (dict, list)):
            data_bytes = canonical_json(payload).encode('utf-8')
        elif isinstance(payload, str):
            data_bytes = payload.encode('utf-8')
        else:
            data_bytes = bytes(payload)

        public_key.verify(signature, data_bytes, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, Exception):
        return False


# ---------------------------------------------------------------------------
# 3. Merkle Tree & Proof Generation
# ---------------------------------------------------------------------------

class MerkleTree:
    """
    Cryptographic Merkle Tree using SHA-256.
    Batches credential leaves, computes root, and generates inclusion proofs.
    """
    def __init__(self, leaves: List[str]):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf hash.")
        self.raw_leaves = leaves
        # Ensure leaves are all 64-char hex strings
        self.leaves = [l if len(l) == 64 else sha256_hash(l) for l in leaves]
        self.levels: List[List[str]] = [self.leaves]
        self._build_tree()

    def _hash_pair(self, left: str, right: str) -> str:
        # Standard sorted or left+right concatenation for determinism
        combined = (left + right).encode('utf-8')
        return hashlib.sha256(combined).hexdigest()

    def _build_tree(self) -> None:
        current_level = self.leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    # Duplicate last leaf if odd count (standard blockchain rule)
                    right = left
                parent = self._hash_pair(left, right)
                next_level.append(parent)
            self.levels.append(next_level)
            current_level = next_level

    def get_root(self) -> str:
        """Return the Merkle Root hex hash."""
        return self.levels[-1][0]

    def get_proof(self, index: int) -> List[Dict[str, str]]:
        """
        Generate inclusion proof for the leaf at specified index.
        Returns a list of sibling nodes with direction:
        [{"position": "right", "hash": "abc..."}, {"position": "left", "hash": "123..."}]
        """
        if index < 0 or index >= len(self.leaves):
            raise IndexError("Leaf index out of bounds")

        proof = []
        current_idx = index

        for level in self.levels[:-1]:
            if current_idx % 2 == 0:
                # Target is left, sibling is right
                sibling_idx = current_idx + 1 if current_idx + 1 < len(level) else current_idx
                proof.append({"position": "right", "hash": level[sibling_idx]})
            else:
                # Target is right, sibling is left
                sibling_idx = current_idx - 1
                proof.append({"position": "left", "hash": level[sibling_idx]})
            current_idx = current_idx // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Dict[str, str]], expected_root: str) -> bool:
        """
        Verify whether leaf_hash belongs to the Merkle tree with expected_root
        by reconstructing the path using the sibling proof.
        """
        current_hash = leaf_hash
        for step in proof:
            sibling_hash = step.get("hash")
            position = step.get("position")
            if not sibling_hash or not position:
                return False

            if position == "right":
                combined = (current_hash + sibling_hash).encode('utf-8')
            else:
                combined = (sibling_hash + current_hash).encode('utf-8')
            current_hash = hashlib.sha256(combined).hexdigest()

        return current_hash.lower() == expected_root.lower()


# ---------------------------------------------------------------------------
# 4. Credential Integrity & Verification Pipeline
# ---------------------------------------------------------------------------

def compute_credential_leaf_hash(cred_data: Dict[str, Any]) -> str:
    """
    Extract canonical subject fields from a credential and compute its SHA-256 leaf hash.
    Ensures that tampering with any core field alters the leaf hash.
    """
    canonical_subject = {
        "credential_id": cred_data.get("credential_id"),
        "student_usn": str(cred_data.get("student_usn", "")).strip().upper(),
        "student_name": str(cred_data.get("student_name", "")).strip(),
        "degree_type": str(cred_data.get("degree_type", "")).strip(),
        "major_specialization": str(cred_data.get("major_specialization", "")).strip(),
        "cgpa": f"{float(cred_data.get('cgpa', 0.0)):.2f}",
        "completion_year": int(cred_data.get("completion_year", 0)),
        "honors": str(cred_data.get("honors", "")).strip(),
        "skills": sorted(cred_data.get("skills", []) if isinstance(cred_data.get("skills"), list) else []),
        "institution": "Presidency University",
    }
    return sha256_hash(canonical_subject)


def verify_credential_complete(
    credential_payload: Dict[str, Any],
    merkle_proof: List[Dict[str, str]],
    merkle_root: str,
    root_signature: str,
    university_public_key_pem: str,
    is_revoked: bool = False
) -> Dict[str, Any]:
    """
    Executes the 4-tier cryptographic verification pipeline:
    1. Schema & Leaf Hash integrity check (recomputes SHA-256 and compares)
    2. Merkle Tree inclusion proof verification
    3. Presidency University ECDSA digital signature verification on Merkle Root
    4. Revocation registry check
    """
    results = {
        "step1_hash_integrity": False,
        "step2_merkle_inclusion": False,
        "step3_university_signature": False,
        "step4_revocation_status": False,
        "overall_verified": False,
        "recomputed_leaf_hash": "",
        "claimed_leaf_hash": credential_payload.get("leaf_hash", ""),
        "timestamp_checked": None,
        "reasons": []
    }

    # Step 1: Recompute leaf hash
    expected_leaf_hash = compute_credential_leaf_hash(credential_payload)
    results["recomputed_leaf_hash"] = expected_leaf_hash
    claimed_leaf_hash = credential_payload.get("leaf_hash")

    if claimed_leaf_hash and claimed_leaf_hash.lower() == expected_leaf_hash.lower():
        results["step1_hash_integrity"] = True
    else:
        results["reasons"].append(
            f"Hash Mismatch: Credential attributes do not match leaf hash! Expected {expected_leaf_hash[:12]}..., found {str(claimed_leaf_hash)[:12]}..."
        )

    # Step 2: Merkle Proof verification
    if results["step1_hash_integrity"] and (merkle_proof is not None) and merkle_root:
        proof_valid = MerkleTree.verify_proof(expected_leaf_hash, merkle_proof, merkle_root)
        results["step2_merkle_inclusion"] = proof_valid
        if not proof_valid:
            results["reasons"].append("Merkle Proof Failure: The credential leaf does not resolve to the registered University Merkle Root.")
    else:
        results["step2_merkle_inclusion"] = False
        if not results["step1_hash_integrity"]:
            results["reasons"].append("Merkle Proof skipped due to leaf hash mismatch.")

    # Step 3: ECDSA Signature on Merkle Root
    if merkle_root and root_signature and university_public_key_pem:
        sig_valid = verify_payload_signature(university_public_key_pem, root_signature, merkle_root)
        results["step3_university_signature"] = sig_valid
        if not sig_valid:
            results["reasons"].append("Digital Signature Invalid: Merkle Root was not signed by Presidency University's official private key.")
    else:
        results["step3_university_signature"] = False
        results["reasons"].append("Missing signature or university public key.")

    # Step 4: Revocation status
    if not is_revoked:
        results["step4_revocation_status"] = True
    else:
        results["reasons"].append("Revocation Alert: This credential has been officially revoked by Presidency University Exam Controller.")

    # Overall outcome
    results["overall_verified"] = (
        results["step1_hash_integrity"]
        and results["step2_merkle_inclusion"]
        and results["step3_university_signature"]
        and results["step4_revocation_status"]
    )

    return results
