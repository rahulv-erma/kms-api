from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel
from src.api.api_models.global_models import User


class loginPayload(BaseModel):
    user: User
    sessionId: str


class Output(BaseOutput):
    payload: loginPayload


class Input(BaseInput):
    email: str
    password: str
