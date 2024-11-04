from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Bundle(BaseModel):
    bundlePicture: str
    bundleId: str
    bundleName: str
    active: bool
    complete: bool
    totalClasses: int
    courseType: str


class Course(BaseModel):
    coursePicture: str
    courseId: str
    courseName: str
    briefDescription: str
    totalClasses: int
    courseType: str
    active: Optional[bool]
    complete: Optional[bool]


class BundlePayload(BaseOutput):
    bundels: List[Optional[Bundle]]
    pagination: Optional[pagination.PaginationOutput]


class BundleOutput(BaseOutput):
    payload: BundlePayload


class CoursesPayload(BaseOutput):
    courses: List[Optional[Course]]
    pagination: Optional[pagination.PaginationOutput]


class CourseOutput(BaseOutput):
    payload: CoursesPayload


class Input(BaseModel):
    ...
