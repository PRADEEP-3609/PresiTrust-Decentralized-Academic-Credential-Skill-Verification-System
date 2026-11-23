"""
PresiTrust: Presidency University - Database Seeder
Seeds degree catalogs, institutional keys, and authentic demo accounts for Admin, Faculty, and Students.
Also generates a pre-sealed verified credential and a pending draft credential for live demonstration.
"""

import json
from datetime import datetime
from core.database import init_db, get_db_connection, get_or_create_university_keys, log_audit
from core.crypto import (
    generate_did,
    generate_ecdsa_keypair,
    compute_credential_leaf_hash,
    MerkleTree,
    sign_payload
)
from core.auth import hash_password


DEGREES_DATA = [
    {
        "code": "BTECH-CSE",
        "name": "Bachelor of Technology in Computer Science & Engineering",
        "degree_type": "B.Tech",
        "school": "School of Computer Science & Information Science",
        "duration_years": 4,
        "specializations": ["Artificial Intelligence & ML", "Data Science", "Cyber Security", "Cloud Computing & DevOps", "Full-Stack Software Engineering"],
        "default_skills": ["Data Structures & Algorithms", "Python Programming", "Docker & Kubernetes", "Distributed Systems", "SQL & Database Architecture"]
    },
    {
        "code": "BTECH-AIML",
        "name": "Bachelor of Technology in Artificial Intelligence & Machine Learning",
        "degree_type": "B.Tech",
        "school": "School of Computer Science & Information Science",
        "duration_years": 4,
        "specializations": ["Deep Learning & Neural Architectures", "Natural Language Processing", "Computer Vision Systems", "MLOps & Scalable AI"],
        "default_skills": ["PyTorch", "TensorFlow", "Feature Engineering", "Neural Networks", "Applied Linear Algebra"]
    },
    {
        "code": "BTECH-ECE",
        "name": "Bachelor of Technology in Electronics & Communication Engineering",
        "degree_type": "B.Tech",
        "school": "School of Engineering",
        "duration_years": 4,
        "specializations": ["VLSI Design", "Embedded Systems & IoT", "Wireless Communications", "Robotics & Micro-controllers"],
        "default_skills": ["Verilog HDL", "Digital Signal Processing", "FPGA Prototyping", "Circuit Design", "Embedded C"]
    },
    {
        "code": "BTECH-MECH",
        "name": "Bachelor of Technology in Mechanical Engineering",
        "degree_type": "B.Tech",
        "school": "School of Engineering",
        "duration_years": 4,
        "specializations": ["Robotics & Industrial Automation", "Thermal & Fluid Engineering", "CAD/CAM & Additive Manufacturing"],
        "default_skills": ["SolidWorks CAD", "Finite Element Analysis", "ANSYS", "Thermodynamics", "Mechatronics"]
    },
    {
        "code": "BBA-BA",
        "name": "Bachelor of Business Administration (BBA)",
        "degree_type": "BBA",
        "school": "School of Management",
        "duration_years": 3,
        "specializations": ["Business Analytics & Intelligence", "Financial Markets & Banking", "Digital Marketing & Strategy", "Supply Chain & Logistics"],
        "default_skills": ["Financial Modeling", "Business Intelligence", "Tableau & PowerBI", "Market Research Analysis", "Spreadsheet Optimization"]
    },
    {
        "code": "BCA-CC",
        "name": "Bachelor of Computer Applications (BCA)",
        "degree_type": "BCA",
        "school": "School of Computer Science & Information Science",
        "duration_years": 3,
        "specializations": ["Cloud Architecture", "Cyber Security & Forensics", "Data Analytics & Web Services"],
        "default_skills": ["JavaScript / TypeScript", "Web Services & APIs", "AWS Cloud Core", "Linux Server Administration", "Cyber Hygiene"]
    },
    {
        "code": "BCOM-HON",
        "name": "Bachelor of Commerce (Honours)",
        "degree_type": "B.Com",
        "school": "School of Commerce",
        "duration_years": 3,
        "specializations": ["Corporate Accounting & Taxation", "Banking, Financial Services & Insurance", "FinTech & Digital Currencies"],
        "default_skills": ["Corporate Taxation", "IFRS Compliance", "Financial Reporting", "Tally ERP", "Audit Principles"]
    },
    {
        "code": "MBA-INT",
        "name": "Master of Business Administration (MBA)",
        "degree_type": "MBA",
        "school": "School of Management",
        "duration_years": 2,
        "specializations": ["Executive Leadership & Strategy", "Investment Banking & Corporate Finance", "AI & Technology Management"],
        "default_skills": ["Strategic Management", "Risk Assessment & Mitigation", "Corporate Valuation", "Global Supply Networks", "Design Thinking"]
    },
    {
        "code": "MTECH-AI",
        "name": "Master of Technology in Artificial Intelligence",
        "degree_type": "M.Tech",
        "school": "School of Computer Science & Information Science",
        "duration_years": 2,
        "specializations": ["Generative Models & Autonomous Agents", "High Performance Computing for AI", "Quantum Machine Learning"],
        "default_skills": ["Transformer Architectures", "Distributed GPU Training", "Reinforcement Learning", "Algorithm Optimization"]
    },
    {
        "code": "SKILL-BC",
        "name": "Presidency University Verified Skill Certification",
        "degree_type": "Skill Certificate",
        "school": "Centre for Emerging Technologies & Blockchain Research",
        "duration_years": 1,
        "specializations": ["Decentralized Systems & Smart Contract Architecture", "Cyber Threat Intelligence", "Full Stack Cloud Native"],
        "default_skills": ["Solidity", "Cryptographic Hashing", "Zero-Knowledge Proofs", "Consensus Algorithms", "Web3 Integration"]
    }
]


def seed_all():
    """Seed the database with catalog programs, master keys, users, and demonstration credentials."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Ensure University Master Key exists
    univ_keys = get_or_create_university_keys()

    # 2. Seed Degrees Catalog
    for deg in DEGREES_DATA:
        cursor.execute("SELECT id FROM degrees_catalog WHERE code = ?", (deg["code"],))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO degrees_catalog (code, name, degree_type, school, duration_years, specializations, default_skills)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                deg["code"],
                deg["name"],
                deg["degree_type"],
                deg["school"],
                deg["duration_years"],
                json.dumps(deg["specializations"]),
                json.dumps(deg["default_skills"])
            ))
    conn.commit()

    # 3. Seed Demo Users
    users_to_seed = [
        {
            "username": "admin",
            "email": "admin@presidencyuniversity.in",
            "password": "admin123",
            "role": "admin",
            "full_name": "Dr. A. K. Banerjee",
            "identifier": "PU-REG-001",
            "department": "Office of Registrar & Examination Directorate",
            "sub_role": "Registrar & Controller of Examinations",
        },
        {
            "username": "prof_sharma",
            "email": "sharma.cs@presidencyuniversity.in",
            "password": "teacher123",
            "role": "teacher",
            "full_name": "Prof. Rajesh Sharma",
            "identifier": "PU-FAC-204",
            "department": "School of Computer Science & Information Science",
            "sub_role": "Professor & Head of Department",
        },
        {
            "username": "prof_ananya",
            "email": "ananya.mgmt@presidencyuniversity.in",
            "password": "teacher123",
            "role": "teacher",
            "full_name": "Dr. Ananya Sen",
            "identifier": "PU-FAC-310",
            "department": "School of Management",
            "sub_role": "Associate Professor & Dean of Academics",
        },
        {
            "username": "arjun_reddy",
            "email": "arjun.20211cse@presidencyuniversity.in",
            "password": "student123",
            "role": "student",
            "full_name": "Arjun Reddy",
            "identifier": "20211CSE0452",
            "department": "School of Computer Science & Information Science",
            "sub_role": "Graduating Student",
        },
        {
            "username": "priya_nair",
            "email": "priya.20221bba@presidencyuniversity.in",
            "password": "student123",
            "role": "student",
            "full_name": "Priya Nair",
            "identifier": "20221BBA0189",
            "department": "School of Management",
            "sub_role": "Enrolled Student",
        }
    ]

    seeded_users = {}
    for u in users_to_seed:
        cursor.execute("SELECT * FROM users WHERE username = ?", (u["username"],))
        existing = cursor.fetchone()
        if existing:
            seeded_users[u["username"]] = dict(existing)
        else:
            pwd_hash, salt = hash_password(u["password"])
            priv_pem, pub_pem = generate_ecdsa_keypair()
            did = generate_did(u["role"], u["identifier"])
            now_iso = datetime.now().isoformat()

            cursor.execute("""
            INSERT INTO users (
                username, email, password_hash, salt, role, full_name,
                identifier, department, sub_role, did, public_key_pem,
                private_key_pem, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                u["username"], u["email"], pwd_hash, salt, u["role"],
                u["full_name"], u["identifier"], u["department"],
                u["sub_role"], did, pub_pem, priv_pem, now_iso
            ))
            user_id = cursor.lastrowid
            seeded_users[u["username"]] = {
                "id": user_id,
                "username": u["username"],
                "role": u["role"],
                "full_name": u["full_name"],
                "identifier": u["identifier"],
                "did": did,
                "private_key_pem": priv_pem,
                "public_key_pem": pub_pem
            }
    conn.commit()

    # 4. Seed Demonstrative Credentials
    # Check if Arjun's credential already exists
    cursor.execute("SELECT id FROM credentials WHERE student_usn = '20211CSE0452'")
    if not cursor.fetchone():
        arjun = seeded_users["arjun_reddy"]
        prof = seeded_users["prof_sharma"]
        cred_id = "PU-2025-BTECH-00452"
        now_time = datetime.now()

        credential_data = {
            "credential_id": cred_id,
            "student_usn": arjun["identifier"],
            "student_name": arjun["full_name"],
            "degree_type": "B.Tech",
            "major_specialization": "Artificial Intelligence & ML",
            "cgpa": "9.24",
            "completion_year": 2025,
            "honors": "First Class with Distinction (Honours)",
            "skills": ["PyTorch", "Deep Learning", "Distributed Systems", "Data Structures", "Docker & Kubernetes"],
            "institution": "Presidency University"
        }

        # Step A: Compute canonical leaf hash
        leaf_hash = compute_credential_leaf_hash(credential_data)

        # Step B: Teacher endorsement signature
        teacher_sig = sign_payload(prof["private_key_pem"], leaf_hash)

        # Step C: Merkle tree construction with a batch of leaves
        # We simulate 4 student leaves in this batch for realistic proof paths
        dummy_leaf_1 = "a1" * 32
        dummy_leaf_2 = "b2" * 32
        dummy_leaf_3 = "c3" * 32
        batch_leaves = [leaf_hash, dummy_leaf_1, dummy_leaf_2, dummy_leaf_3]

        merkle_tree = MerkleTree(batch_leaves)
        merkle_root = merkle_tree.get_root()
        arjun_proof = merkle_tree.get_proof(0)

        # Step D: University Authority signs the Merkle Root with Master Private Key
        univ_signature = sign_payload(univ_keys["private_key_pem"], merkle_root)

        # Step E: Commit Batch to Ledger
        batch_id = "PU-BATCH-2025-001"
        cursor.execute("""
        INSERT INTO batches (
            batch_id, merkle_root, signature, university_public_key, university_did,
            total_credentials, block_number, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_id, merkle_root, univ_signature, univ_keys["public_key_pem"],
            univ_keys["did"], 4, 101, now_time.isoformat()
        ))

        # Step F: Insert Arjun's verified & sealed credential
        cursor.execute("""
        INSERT INTO credentials (
            credential_id, student_id, student_name, student_usn, student_did,
            degree_type, major_specialization, cgpa, completion_year, honors,
            credits_earned, skills, teacher_id, teacher_name, teacher_did,
            teacher_endorsement_sig, status, leaf_hash, merkle_proof, batch_id,
            block_number, created_at, issued_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cred_id, arjun["id"], arjun["full_name"], arjun["identifier"], arjun["did"],
            "B.Tech", "Artificial Intelligence & ML", 9.24, 2025, "First Class with Distinction (Honours)",
            164, json.dumps(credential_data["skills"]), prof["id"], prof["full_name"], prof["did"],
            teacher_sig, "university_sealed", leaf_hash, json.dumps(arjun_proof), batch_id,
            101, now_time.strftime("%Y-%m-%d %H:%M:%S"), now_time.strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()

        log_audit("SYSTEM", "admin", "CREDENTIAL_SEALED", f"Issued and sealed degree {cred_id} in Batch {batch_id} (Block #101).")

    # Check if Priya's pending draft credential exists
    cursor.execute("SELECT id FROM credentials WHERE student_usn = '20221BBA0189'")
    if not cursor.fetchone():
        priya = seeded_users["priya_nair"]
        prof_ananya = seeded_users["prof_ananya"]
        cred_id_priya = "PU-2026-BBA-00189"
        now_time = datetime.now()

        priya_data = {
            "credential_id": cred_id_priya,
            "student_usn": priya["identifier"],
            "student_name": priya["full_name"],
            "degree_type": "BBA",
            "major_specialization": "Business Analytics & Intelligence",
            "cgpa": "8.85",
            "completion_year": 2026,
            "honors": "First Class with Distinction",
            "skills": ["Business Intelligence", "Financial Modeling", "Tableau & PowerBI", "Market Research Analysis"],
            "institution": "Presidency University"
        }
        leaf_hash_priya = compute_credential_leaf_hash(priya_data)
        teacher_sig_priya = sign_payload(prof_ananya["private_key_pem"], leaf_hash_priya)

        cursor.execute("""
        INSERT INTO credentials (
            credential_id, student_id, student_name, student_usn, student_did,
            degree_type, major_specialization, cgpa, completion_year, honors,
            credits_earned, skills, teacher_id, teacher_name, teacher_did,
            teacher_endorsement_sig, status, leaf_hash, merkle_proof, batch_id,
            block_number, created_at, issued_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cred_id_priya, priya["id"], priya["full_name"], priya["identifier"], priya["did"],
            "BBA", "Business Analytics & Intelligence", 8.85, 2026, "First Class with Distinction",
            128, json.dumps(priya_data["skills"]), prof_ananya["id"], prof_ananya["full_name"], prof_ananya["did"],
            teacher_sig_priya, "teacher_endorsed", leaf_hash_priya, None, None,
            None, now_time.strftime("%Y-%m-%d %H:%M:%S"), None
        ))
        conn.commit()

        log_audit(prof_ananya["full_name"], "teacher", "CREDENTIAL_ENDORSED", f"Endorsed degree {cred_id_priya} for {priya['full_name']}. Pending University Batch Sealing.")

    conn.close()
    print("Presidency University database seeded successfully!")


if __name__ == "__main__":
    seed_all()
