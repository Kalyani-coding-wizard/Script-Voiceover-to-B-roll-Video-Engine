"""
ARQ Worker Settings for IncuBrix B-roll Video Engine.
"""
from arq.connections import RedisSettings

from worker.tasks.pipeline import run_pipeline


class WorkerSettings:
    functions = [run_pipeline]
    redis_settings = RedisSettings.from_dsn(
        __import__("os").getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    max_jobs = int(__import__("os").getenv("WORKER_CONCURRENCY", "2"))
    job_timeout = 3600  # 1 hour max per job
    keep_result = 86400  # 24 h
    retry_jobs = False  # pipeline handles its own retries
    health_check_interval = 30
    health_check_key = "arq:health-check"


if __name__ == "__main__":
    import asyncio
    from arq import run_worker

    asyncio.run(run_worker(WorkerSettings))
