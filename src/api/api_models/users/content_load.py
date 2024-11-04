from typing import Optional
from src.api.api_models.bases import BaseOutput, BaseInput


class Input(BaseInput):
    id: Optional[str]
    contentType: str = "headShot" or "sstId"


class Output(BaseOutput):
    ...
