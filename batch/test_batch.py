"""
Tests the batch runner against a running test server.
"""
import asyncio
import os
import sys
import threading
import time
from pathlib import Path

# Add QGIS bin to DLL search path if on Windows
if sys.platform == "win32":
    qgis_bin = r"C:\Program Files\QGIS 3.40.1\bin"
    if os.path.exists(qgis_bin) and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(qgis_bin)
        except Exception:
            pass

os.environ["MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
sys.path.insert(0, ".")

import uvicorn
from app.main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="warning")

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

print("Server thread started on port 8899, waiting 1s...")
time.sleep(1.5)

# Run batch runner against port 8899
from batch.batch_runner import main_async
import argparse

args = argparse.Namespace(
    input="./tests/inputs",
    output="./batch_results",
    base_url="http://127.0.0.1:8899",
    poll_interval=0.5,
    timeout=60.0,
)

exit_code = asyncio.run(main_async(args))
print(f"Batch runner finished with code: {exit_code}")
sys.exit(exit_code)
