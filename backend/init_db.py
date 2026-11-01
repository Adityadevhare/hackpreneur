"""
Database initialization module for HACKPRENEUR.
Database migrations are version-controlled and applied via Alembic.
Run: alembic upgrade head
"""
import subprocess
import sys
from pathlib import Path


def init():
    backend_dir = Path(__file__).resolve().parent
    print("Applying Alembic migrations...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir)
    )
    if result.returncode == 0:
        print("HACKPRENEUR database initialized successfully via Alembic!")
    else:
        print("Alembic migration failed.")


if __name__ == "__main__":
    init()
