from typing import List

from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models.global_models import User


class Role(BaseModel):
    roleId: str
    roleName: str
    roleDesc: str


class MePayload(BaseModel):
    user: User
    roles: List[Role]


class Output(BaseOutput):
    payload: MePayload
