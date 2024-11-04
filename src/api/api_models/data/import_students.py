from typing import Optional, List, Union
from src.api.api_models.bases import BaseOutput, BaseModel, BaseInput


class Student(BaseModel):
    reason: Optional[str] = None
    failed: Optional[bool] = None
    userId: str
    headShot: Optional[str] = None
    firstName: Optional[str] = None
    middleName: Optional[str] = None
    lastName: Optional[str] = None
    suffix: Optional[str] = None
    email: Optional[str] = None
    phoneNumber: Optional[str] = None
    dob: Optional[str] = None
    eyeColor: Optional[str] = None
    houseNumber: Optional[str] = None
    streetName: Optional[str] = None
    aptSuite: Optional[Union[int, str]] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[Union[int, str]] = None
    gender: Optional[str] = None
    height: Optional[str] = None


class Payload(BaseModel):
    fileName: Optional[str] = None
    students: Optional[List[Student]]


class Output(BaseOutput):
    payload: Optional[Payload]


class Input(BaseInput):
    fileName: Optional[str] = None
    students: List[Student]
