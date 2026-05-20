from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EconomicEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    country: str
    title: str
    impact: str
    actual: float | None
    estimate: float | None
    previous: float | None
    unit: str | None
    event_time: datetime


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    category: str | None
    headline: str
    summary: str | None
    url: str | None
    image_url: str | None
    relevance: float | None
    published_at: datetime
