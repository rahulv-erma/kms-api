from typing import Optional

from src.api.api_models.bases import BaseOutput, BaseInput


class Output(BaseOutput):
    success: bool


class Input(BaseInput):
    userId: str
    registrationStatus: Optional[str] = None
    paid: Optional[bool] = None
    notes: Optional[str] = None
