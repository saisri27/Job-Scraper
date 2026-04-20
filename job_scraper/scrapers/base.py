from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    company: str
    title: str
    url: str
    role: str
    location: str = ""
    posted_date: Optional[str] = None

    @property
    def dedup_key(self) -> str:
        raw = f"{self.company}|{self.title.strip().lower()}|{self.url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()


class BaseScraper(ABC):
    company: str = ""

    @abstractmethod
    async def fetch(self) -> list[Job]: ...
