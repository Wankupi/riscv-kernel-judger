from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Annotated
import uuid
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile, status
import redis
from pydantic.dataclasses import dataclass

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


@dataclass
class QueueStatus:
    queue_size: int


@app.get("/queue")
async def get_queue_size() -> QueueStatus:
    try:
        return QueueStatus(queue_size=await queue.size())
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="queue is unavailable",
        ) from exc


@dataclass
class SubmitResponse:
    id: str


@app.post("/submit")
async def submit(
    file: Annotated[UploadFile, File()],
    time_limit: Annotated[int, Form()],
) -> SubmitResponse:
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

    return SubmitResponse(id=submission_id)


@app.get("/result/{task_id}")
async def get_result(task_id: str) -> Response:
    # if redis stream exists, stream from redis; otherwise, try to read from file
    # otherwise, return 404
    key: str = f"{config.redis.task_key}:{task_id}"
    result_path: Path = config.runner.result_dir / f"{task_id}.txt"

    # tricky logic to determine the state of the task:
    started = result_path.exists()
    finished = not bool(await queue.exists(key))

    assert (not finished or started) and "invalid state: finished but not started"

    if finished:
        return FileResponse(
            result_path, media_type="text/plain; charset=utf-8", filename=f"{task_id}.txt"
        )

    async def stream_redis() -> AsyncIterator[bytes]:
        async for chunk in queue.sub_result(task_id=task_id):
            yield chunk

    return StreamingResponse(stream_redis(), media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.server.host, port=config.server.port)
