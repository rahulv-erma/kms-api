from typing import Optional, List

from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Input(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    _id: Optional[str] = None


class User(BaseModel):
    userId: str
    firstName: str
    lastName: str
    dob: str
    email: str
    phoneNumber: str
    headShot: str


class StudentsPayload(BaseModel):
    students: List[Optional[User]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: StudentsPayload
