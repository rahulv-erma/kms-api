from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Event(BaseModel):
    courseId: str
    courseName: str
    startTime: str
    duration: int
    seriesNumber: int
    complete: bool


class SchedulePayload(BaseOutput):
    schedule: List[Optional[Event]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: SchedulePayload
