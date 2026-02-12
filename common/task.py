from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    file_path: Path
    time_limit: int = Field(ge=1)
