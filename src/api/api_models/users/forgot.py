from src.api.api_models.bases import BaseOutput, BaseInput


class Output(BaseOutput):
    ...


class Input(BaseInput):
    email: str


class Input2(BaseInput):
    newPassword: str
