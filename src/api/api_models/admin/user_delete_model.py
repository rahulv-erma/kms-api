from typing import List
from src.api.api_models.bases import BaseOutput, BaseInput


class Input(BaseInput):
    userIds: List[str]


class Output(BaseOutput):
    ...
