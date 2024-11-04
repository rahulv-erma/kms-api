from src.api.api_models.bases import BaseInput
from pydantic import BaseModel
from typing import List, Optional


class Output(BaseModel):
    ...


class Input(BaseInput):
    courseId: Optional[str] = None
    certificateName: Optional[str] = None
    userIds: List[str]
    expirationDate: Optional[str] = None
