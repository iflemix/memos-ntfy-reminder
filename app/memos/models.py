from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class Memo:
    id: str
    content: str
    create_time: datetime
    state: Literal["NORMAL", "ARCHIVED"]

    @classmethod
    def from_payload(cls, data: dict) -> "Memo":
        return cls(
            id=data["name"],
            content=data["content"],
            create_time=datetime.fromisoformat(data["createTime"]),
            state=data["state"],
        )


@dataclass(frozen=True, slots=True)
class GetMemoResult:
    status: Literal["ok", "not_found", "error"]
    memo: Memo | None = None
