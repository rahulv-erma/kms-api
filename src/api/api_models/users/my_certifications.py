from typing import Optional, List

from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Certification(BaseModel):
    userId: str
    certificateName: str
    certificateNumber: str
    student: str
    instructor: str
    completionDate: str
    expirationDate: Optional[str] = None


class CertificationsPayload(BaseModel):
    certifications: List[Optional[Certification]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: CertificationsPayload
