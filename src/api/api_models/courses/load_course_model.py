from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models.global_models import Course


class Student(BaseModel):
    headShot: str
    userId: str
    firstName: str
    lastName: str
    dob: str
    enrollmentStatus: str
    paid: Optional[bool] = False
    usingCash: Optional[bool] = False


class Schedule(BaseModel):
    courseId: str
    courseName: str
    startDate: str
    duration: str
    seriesNumber: int
    complete: bool


class CoursesPayload(BaseModel):
    course: Course
    schedule: Optional[List[Schedule]]
    students: Optional[List[Student]]


class Output(BaseOutput):
    payload: CoursesPayload
