"""
ARQ Worker Settings for IncuBrix B-roll Video Engine.
Re-exported from worker.worker for docker-compose compatibility.
"""
from worker.worker import WorkerSettings  # noqa: F401

__all__ = ["WorkerSettings"]

if __name__ == "__main__":
    import asyncio
    from arq import run_worker
    asyncio.run(run_worker(WorkerSettings))
