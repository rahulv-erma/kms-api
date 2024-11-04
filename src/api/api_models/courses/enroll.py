from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel


class Output(BaseOutput):
    ...


class InstructorInput(BaseInput):
    instructors: List[str]


class StudentPayload(BaseModel):
    userId: Optional[str] = None
    registrationStatus: str
    denialReason: Optional[str] = None
    userPaid: Optional[bool] = False
    usingCash: Optional[bool] = False
    notes: Optional[str] = None


class SelfRegistration(BaseModel):
    userPaid: bool = False
    usingCash: bool = False


class StudentCourseInput(BaseInput):
    students: List[StudentPayload]


class StudentBundleInput(BaseInput):
    students: List[StudentPayload]
