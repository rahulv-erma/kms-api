from typing import Optional
from src.api.api_models.bases import BaseInput, BaseOutput


class Output(BaseOutput):
    ...


class Input(BaseInput):
    courseName: Optional[str] = None
    courseBundle: Optional[str] = None
