from typing import List, Optional

from src.api.api_models.bases import BaseModel, BaseOutput
from src.api.api_models import pagination


class Course(BaseModel):
    coursePicture: str
    courseId: str
    courseName: str
    briefDescription: str
    totalClasses: int
    courseType: str
    complete: Optional[bool]


class CoursePayload(BaseModel):
    courses: List[Optional[Course]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: CoursePayload
