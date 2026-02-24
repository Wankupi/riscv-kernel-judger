import redis.asyncio as redis
from typing import Any
from pydantic import TypeAdapter, ValidationError
from common.config import config
from common.task import Task

TASK_ADAPTER: TypeAdapter[Task] = TypeAdapter(Task)


class RedisTaskQueue:
    def __init__(self) -> None:
        self.queue_key: str = config.redis.queue_key
        self._client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=True,
        )

    async def enqueue(self, task: Task) -> None:
        payload: str = TASK_ADAPTER.dump_json(task).decode("utf-8")
        await self._client.rpush(self.queue_key, payload)

    async def dequeue(self) -> Task | None:
        raw_item: list[str] | None = await self._client.blpop([self.queue_key])
        if raw_item is None or len(raw_item) < 2:
            return None
        try:
            payload: str = raw_item[1]
            return TASK_ADAPTER.validate_json(payload)
        except ValidationError as exc:
            raise ValueError("invalid queued task payload") from exc

    async def size(self) -> int:
        return int(await self._client.llen(self.queue_key))
