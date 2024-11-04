from typing import Optional, Union, List
import datetime
from src.api.api_models.bases import BaseModel


class Height(BaseModel):
    feet: int
    inches: int


class User(BaseModel):
    userId: str
    password: Optional[str] = None
    firstName: str
    middleName: Optional[str] = None
    lastName: str
    suffix: Optional[str] = None
    email: Optional[str] = None
    phoneNumber: Optional[str] = None
    dob: str = str(datetime.date.today())
    eyeColor: Optional[str] = None
    height: Optional[Height] = None
    gender: Optional[str] = None
    timeZone: Optional[str] = 'EST'
    headShot: Optional[str] = None
    photoId: Optional[str] = None
    photoIdPhoto: Optional[str] = None
    otherIdPhoto: Optional[str] = None
    otherId: Optional[str] = None
    active: bool = True
    textNotifications: Optional[bool] = False
    emailNotifications: Optional[bool] = True
    expirationDate: Union[datetime.datetime, None] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[int] = None


class Prerequisite(BaseModel):
    courseId: Optional[str]
    courseName: Optional[str]


class Course(BaseModel):
    coursePicture: str
    courseId: str
    courseName: str
    briefDescription: Optional[str]
    description: Optional[str]
    price: float
    prerequisites: List[Prerequisite]
    languages: List[str]
    instructionTypes: List[str]
    active: bool
    maxStudents: int
    isFull: bool
    waitlist: bool
    waitlistLimit: int
    startDate: str
    enrollable: bool
    instructors: List[dict]
    email: str
    phoneNumber: str
    allowCash: bool
    registrationStatus: Optional[str] = None
    # only show if enrolled
    address: Optional[str]
    remoteLink: Optional[str]
