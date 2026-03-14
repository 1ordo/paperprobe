from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class PaperOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str | None
    authors: str | None
    year: int | None
    doi: str | None
    filename: str
    file_type: str
    status: str
    page_count: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaperUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
