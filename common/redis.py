import redis
from pydantic import TypeAdapter, ValidationError
from common.config import config
from common.task import Task

TASK_ADAPTER: TypeAdapter[Task] = TypeAdapter(Task)


class RedisTaskQueue:
    def __init__(self) -> None:
        self.queue_key: str = config.redis.queue_key
        self._client: redis.Redis = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=True,
        )

    def enqueue(self, task: Task) -> None:
        payload: str = TASK_ADAPTER.dump_json(task).decode("utf-8")
        self._client.rpush(self.queue_key, payload)

    def dequeue(self) -> Task | None:
        raw_item: tuple[str, str] = self._client.blpop([self.queue_key])  # type: ignore
        assert type(raw_item) is tuple
        try:
            payload: str = raw_item[1]
            return TASK_ADAPTER.validate_json(payload)
        except ValidationError as exc:
            raise ValueError("invalid queued task payload") from exc

    def size(self) -> int:
        return int(self._client.llen(self.queue_key))
