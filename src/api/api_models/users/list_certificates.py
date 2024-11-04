from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models.pagination import PaginationOutput


class Certificate(BaseModel):
    userId: str
    headShot: str
    firstName: str
    lastName: str
    certificateNumber: str
    certificateName: str


class Payload(BaseModel):
    certificates: Optional[List[Certificate]] = []
    pagination: PaginationOutput


class Output(BaseOutput):
    payload: Payload
