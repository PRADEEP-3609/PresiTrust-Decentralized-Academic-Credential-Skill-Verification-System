"""
PresiTrust: Presidency University - Academic Credential & Skill Verification System
System Launcher
"""

import sys
import os
import uvicorn
from seed_data import seed_all

def main():
    print("=" * 75)
    print("  PRESITRUST - PRESIDENCY UNIVERSITY, BENGALURU")
    print("  Decentralized Academic Credential & Skill Verification Ledger")
    print("=" * 75)
    print("\n[1/2] Initializing Cryptographic Ledger & Database...")
    seed_all()
    print("[SUCCESS] PresiTrust Database, Cryptographic Keys, and Catalog Ready.")

    print("\n[2/2] Launching Application Server...")
    print("  ➜ Portal URL:              http://127.0.0.1:8000")
    print("  ➜ Interactive API Docs:    http://127.0.0.1:8000/docs")
    print("  ➜ Public Verification:     http://127.0.0.1:8000 (Open by default)")
    print("\n" + "-" * 75)
    print("  DEMONSTRATION & EVALUATOR CREDENTIALS:")
    print("  - Admin (Registrar):       admin        / admin123")
    print("  - Faculty (Professor):     prof_sharma  / teacher123")
    print("  - Student (Graduating):    arjun_reddy  / student123")
    print("  * You can also dynamically register ANY new account with dynamic roles!")
    print("-" * 75 + "\n")

    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
