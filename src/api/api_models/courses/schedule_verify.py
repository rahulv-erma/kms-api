from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel
from src.api.api_models import pagination


class Input(BaseInput):
    courseIds: List[str]


class Schedule(BaseModel):
    startTime: str
    endTime: str
    courseName: str
    courseId: str


class Payload(BaseModel):
    schedule: List[Optional[Schedule]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: Optional[Payload]
