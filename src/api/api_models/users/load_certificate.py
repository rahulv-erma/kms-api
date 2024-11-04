from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel


class Certificate(BaseModel):
    userId: str
    certificateName: str
    certificateNumber: str
    completionDate: str
    expirationDate: str
    student: str
    instructor: str


class Payload(BaseModel):
    certificates: Optional[List[Certificate]] = []


class Output(BaseOutput):
    payload: Payload
