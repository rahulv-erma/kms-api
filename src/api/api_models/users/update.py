from typing import Optional
from src.api.api_models.global_models import User
from src.api.api_models.bases import BaseInput, BaseOutput, BaseModel


class Height(BaseModel):
    feet: int = 0
    inches: int = 0


class Input(BaseInput):
    firstName: Optional[str] = None
    middleName: Optional[str] = None
    lastName: Optional[str] = None
    suffix: Optional[str] = None
    email: Optional[str] = None
    phoneNumber: Optional[str] = None
    dob: Optional[str] = None
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
    headShot: Optional[str] = None
    otherIdPhoto: Optional[str] = None
    photoIdPhoto: Optional[str] = None


class Payload(BaseModel):
    user: User


class Output(BaseOutput):
    payload: Payload
