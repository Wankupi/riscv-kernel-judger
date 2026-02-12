from pathlib import Path
from pydantic.dataclasses import dataclass
from .config import config

@dataclass
class Task:
    id: str
    file_path: Path
    time_limit: int = config.runner.default_time_limit
