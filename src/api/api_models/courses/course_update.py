from typing import List, Optional
from src.api.api_models.bases import BaseModel, BaseOutput


class UpdateCourseInput(BaseModel):
    courseId: str
    courseName: Optional[str] = None
    briefDescription: Optional[str] = None
    description: Optional[str] = None
    languages: Optional[List[str]] = None
    instructors: Optional[List[str]] = None
    price: Optional[float] = None
    instructionTypes: Optional[List[str]] = None
    remoteLink: Optional[str] = None
    phoneNumber: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    maxStudents: Optional[int] = None
    isFull: Optional[bool] = None
    enrollable: Optional[bool] = None
    waitlist: Optional[bool] = None
    waitlistLimit: Optional[int] = None
    prerequisites: Optional[List[str]] = None
    allowCash: Optional[bool] = None
    active: Optional[bool] = None,
    courseCode: Optional[str] = None


class Output(BaseOutput):
    ...
