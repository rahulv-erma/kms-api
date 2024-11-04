from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models.pagination import PaginationOutput


class Form(BaseModel):
    formId: str
    formName: str
    formType: str
    active: bool


class formPayload(BaseModel):
    forms: Optional[List[Form]]
    pagination: PaginationOutput


class Output(BaseOutput):
    payload: formPayload
