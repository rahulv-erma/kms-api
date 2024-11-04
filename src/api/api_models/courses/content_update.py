from typing import List

from src.api.api_models.bases import BaseOutput, BaseInput


class UpdateInput(BaseInput):
    fileIds: List[str]
    publish: bool


class DeleteInput(BaseInput):
    fileIds: List[str]


class Output(BaseOutput):
    ...
