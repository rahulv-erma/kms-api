from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Role(BaseModel):
    roleName: str
    roleId: str
    description: str


class ListPayload(BaseModel):
    roles: List[Optional[Role]]
    pagination: Optional[pagination.PaginationOutput]


class ListOutput(BaseOutput):
    payload: ListPayload
