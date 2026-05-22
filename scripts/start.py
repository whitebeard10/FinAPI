import subprocess
import time
import sys
import os

def wait_for_postgres():
    print("Waiting for postgres...")
    postgres_server = os.getenv("POSTGRES_SERVER", "db")
    while True:
        try:
            # Try to connect to postgres port using nc or just return True if we want to skip complex check
            result = subprocess.run(["nc", "-z", postgres_server, "5432"], capture_output=True)
            if result.returncode == 0:
                print("PostgreSQL started")
                break
        except Exception:
            pass
        time.sleep(0.5)

def run_migrations():
    print("Running database migrations...")
    result = subprocess.run(["alembic", "upgrade", "head"])
    if result.returncode != 0:
        print("Migration failed")
        sys.exit(1)

def start_app():
    print("Starting application...")
    # exec replacement
    os.execvp("uvicorn", ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"])

if __name__ == "__main__":
    wait_for_postgres()
    run_migrations()
    start_app()
