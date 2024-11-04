from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models.pagination import PaginationOutput


class User(BaseModel):
    userId: str
    headShot: str
    firstName: str
    lastName: str
    email: str
    phoneNumber: str
    dob: str


class Payload(BaseModel):
    users: Optional[List[User]] = []
    pagination: PaginationOutput


class Output(BaseOutput):
    payload: Payload
