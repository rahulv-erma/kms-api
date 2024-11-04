from typing import Optional, List, Union
from src.api.api_models.bases import BaseOutput, BaseModel


class CourseOutput(BaseModel):
    courseName: Optional[str] = None
    reason: Optional[str] = None


class SeriesOutput(BaseModel):
    courseName: Optional[str] = None
    reason: Optional[str] = None


class BundleOutput(BaseModel):
    bundleName: str
    courseName: Optional[str] = None
    reason: Optional[str] = None


class Payload(BaseModel):
    succeeded: int
    bundles: Optional[List[BundleOutput]] = None
    courses: Optional[List[CourseOutput]] = None
    series: Optional[List[SeriesOutput]] = None


class Output(BaseOutput):
    payload: Optional[Payload] = None


class Schedule(BaseModel):
    date: str
    startTime: str
    endTime: str


class Course(BaseModel):
    courseName: str
    description: Optional[str] = None
    language: str
    schedule: List[Schedule]
    onlineClassLink: Optional[str] = None
    password: Optional[Union[str, int]] = None
    street: Optional[str] = None
    rmFl: Optional[Union[str, int]] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[int] = None
    instructorNames: Optional[List[str]] = None
    price: Union[int, float]
    code: Optional[str] = None


class BundleContent(BaseModel):
    name: str
    price: Union[int, float]
    description: Optional[str] = None


class Bundle(BaseModel):
    bundle: BundleContent
    courses: List[Course]


class Input(BaseModel):
    courses: Optional[List[Course]] = None
    bundles: Optional[List[Bundle]] = None
    series: Optional[List[Course]] = None
