import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
    )
    frontend = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/streamlit_app.py", "--server.port", "8501"],
        cwd=ROOT,
    )
    print("Backend:  http://127.0.0.1:8000/docs")
    print("Frontend: http://127.0.0.1:8501")

    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (frontend, backend):
            if process.poll() is None:
                process.terminate()
        for process in (frontend, backend):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
