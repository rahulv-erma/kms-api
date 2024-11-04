from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Course(BaseModel):
    coursePicture: str
    courseId: str
    courseName: str
    startDate: str
    briefDescription: Optional[str] = None
    totalClasses: int
    courseType: str
    active: Optional[bool]
    complete: Optional[bool]


class CoursesPayload(BaseOutput):
    courses: List[Optional[Course]]
    pagination: Optional[pagination.PaginationOutput]


class CoursesOutput(BaseOutput):
    payload: CoursesPayload
