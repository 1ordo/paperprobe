from pydantic import BaseModel


class CosminStandardOut(BaseModel):
    id: int
    standard_number: int
    question_text: str
    section_group: str | None
    rating_very_good: str | None
    rating_adequate: str | None
    rating_doubtful: str | None
    rating_inadequate: str | None
    na_allowed: bool
    has_sub_criteria: bool
    sub_criteria_json: dict | None
    sort_order: int

    model_config = {"from_attributes": True}


class CosminSubBoxOut(BaseModel):
    id: int
    sub_box_code: str
    name: str
    section_group: str | None
    sort_order: int
    standards: list[CosminStandardOut] = []

    model_config = {"from_attributes": True}


class CosminBoxOut(BaseModel):
    id: int
    box_number: int
    name: str
    description: str | None
    prerequisite: str | None
    sub_boxes: list[CosminSubBoxOut] = []

    model_config = {"from_attributes": True}
