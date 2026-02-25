# type: ignore
import redis.asyncio as redis
from typing import Any, AsyncIterator
from pydantic import TypeAdapter, ValidationError
from common.config import config
from common.task import Task

TASK_ADAPTER: TypeAdapter[Task] = TypeAdapter(Task)


class RedisTaskQueue(redis.Redis):
    async def enqueue(self, task: Task) -> None:
        payload: str = TASK_ADAPTER.dump_json(task).decode("utf-8")
        await self.rpush(config.redis.queue_key, payload)

    async def dequeue(self) -> Task | None:
        raw_item: list[str] | None = await self.blpop([config.redis.queue_key])
        if raw_item is None or len(raw_item) < 2:
            return None
        try:
            payload: str = raw_item[1]
            return TASK_ADAPTER.validate_json(payload)
        except ValidationError as exc:
            raise ValueError("invalid queued task payload") from exc

    async def size(self) -> int:
        return int(await self.llen(config.redis.queue_key))

    async def pub_result(self, task_id: str, result: bytes) -> None:
        key = f"{config.redis.task_key}:{task_id}"
        await self.xadd(key, {"chunk": result})

    async def pub_result_done(self, task_id: str) -> None:
        key = f"{config.redis.task_key}:{task_id}"
        await self.xadd(key, {"chunk": b"", "done": 1})
        await self.expire(key, 5)

    async def sub_result(self, task_id: str, start_id: str = "0-0") -> AsyncIterator[bytes]:
        key: str = f"{config.redis.task_key}:{task_id}"
        last_id: str = start_id
        while True:
            streams: list[Any] = await self.xread({key: last_id}, block=5000, count=128)
            if not streams:
                return
            for _, entries in streams:
                for entry_id, fields in entries:
                    last_id = entry_id
                    chunk_value: Any = fields.get(b"chunk", fields.get("chunk", b""))
                    done_value: bool = fields.get(b"done", fields.get("done", 0))
                    chunk: bytes = (
                        chunk_value.encode("utf-8")
                        if isinstance(chunk_value, str)
                        else bytes(chunk_value)
                    )
                    if chunk:
                        yield chunk
                    done_flag: bool = done_value in (b"1", "1", 1)
                    if done_flag:
                        return
