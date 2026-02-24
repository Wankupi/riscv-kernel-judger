from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Annotated
import uuid

import redis
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status

from common.config import config
from common.redis import RedisTaskQueue
from common.task import Task


class SubmissionStore:
    def __init__(self, upload_dir: Path) -> None:
        self.upload_dir: Path = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, file: UploadFile, submission_id: str) -> Path:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        stored_path: Path = self.upload_dir / f"{submission_id}.img"
        assert file.size is not None, "assume UploadFile.size is set for simplicity"
        if file.size > config.server.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="file too large",
            )
        with stored_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        return stored_path


store: SubmissionStore = SubmissionStore(upload_dir=config.server.upload_dir)
queue: RedisTaskQueue = RedisTaskQueue()
app: FastAPI = FastAPI(title="RISCV Kernel Judger Frontend")


def make_submission_id() -> str:
    ts: str = datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")
    suffix: str = uuid.uuid4().hex[:4]
    return f"{ts}-{suffix}"


@app.get("/queue")
async def get_queue_size() -> dict[str, int]:
    try:
        return {"queue_size": await queue.size()}
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="queue is unavailable",
        ) from exc


@app.post("/submit")
async def submit(
    file: Annotated[UploadFile, File()],
    time_limit: Annotated[int, Form()],
) -> dict[str, str]:
    if time_limit <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid time_limit")

    submission_id: str = make_submission_id()

    try:
        stored_path: Path = await store.save_upload(file=file, submission_id=submission_id)
    finally:
        await file.close()

    task: Task = Task(
        id=submission_id,
        file_path=stored_path,
        time_limit=time_limit,
    )

    try:
        await queue.enqueue(task)
    except redis.RedisError as exc:
        if stored_path.exists():
            stored_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="queue is unavailable",
        ) from exc

    return {"id": submission_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.server.host, port=config.server.port)
