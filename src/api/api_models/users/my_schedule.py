from typing import List, Optional

from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Schedule(BaseModel):
    courseId: str
    seriesNumber: int
    courseName: str
    startTime: str
    endTime: str
    duration: float
    complete: bool


class SchedulePayload(BaseModel):
    schedule: List[Optional[Schedule]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: SchedulePayload
