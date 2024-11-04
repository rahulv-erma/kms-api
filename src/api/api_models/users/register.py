from typing import Optional
from src.api.api_models.bases import BaseOutput, BaseModel


class Height(BaseModel):
    feet: int = 0
    inches: int = 0


class User(BaseModel):
    firstName: str
    middleName: Optional[str] = None
    lastName: str
    suffix: Optional[str] = None
    email: str
    phoneNumber: str
    dob: str
    password: Optional[str] = None
    timeZone: Optional[str] = 'EST'
    photoId: Optional[str] = None
    otherId: Optional[str] = None
    textNotifications: Optional[bool] = False
    emailNotifications: Optional[bool] = True
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[int] = None
    height: Optional[Height] = None
    gender: Optional[str] = None
    eyeColor: Optional[str] = None


class Input(User):
    ...


class Payload(BaseModel):
    user: Optional[User]
    sessionId: Optional[str]
    userId: Optional[str]


class Output(BaseOutput):
    payload: Payload
