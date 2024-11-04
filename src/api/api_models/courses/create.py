from typing import List, Optional, Union
from src.api.api_models.bases import BaseInput, BaseModel


class Payload(BaseModel):
    courseId: str


class Output(BaseModel):
    payload: Optional[Payload]


class Address(BaseModel):
    address: str
    city: str
    state: str
    zipcode: int


class Height(BaseModel):
    feet: int
    inches: int


class General(BaseModel):
    courseName: str
    briefDescription: Optional[str]
    description: Optional[str]
    requirements: Optional[List[str]] = []
    languages: List[str] = ["English"]
    instructors: Optional[List[str]] = []
    price: float
    instructionTypes: List[str] = []
    remoteLink: Optional[str] = None
    phoneNumber: str
    email: str
    address: Optional[str] = None
    duration: int = 60
    maxStudents: Optional[int] = 20
    enrollable: Optional[bool] = False
    waitlist: bool = True
    waitlistLimit: Optional[int] = 20
    prerequisites: Optional[List[str]] = None
    allowCash: bool = False
    courseCode: Optional[str] = None


class Frequency(BaseModel):
    frequency: Optional[int] = None
    days: Optional[List[Union[str, int]]] = None
    months: Optional[List[str]] = None
    dates: Optional[List[str]] = None


class ClassFrequency(BaseModel):
    days: Optional[Frequency] = None
    weeks: Optional[Frequency] = None
    months: Optional[Frequency] = None
    years: Optional[Frequency] = None


class Series(BaseModel):
    firstClassDtm: str
    classesInSeries: int
    classFrequency: ClassFrequency


class Content(BaseModel):
    contentName: str
    content: str


class Expiration(BaseModel):
    years: Optional[int] = 0
    months: Optional[int] = 0


class Certificate(BaseModel):
    certificateName: Optional[str] = None
    expiration: Optional[Expiration] = None
    certificate: Optional[bool] = True


class Input(BaseInput):
    general: General
    series: Series
    quizzes: Optional[List[str]] = None
    surveys: Optional[List[str]] = None
    certification: Certificate
    active: bool = False
