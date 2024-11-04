from src.api.api_models.bases import BaseOutput, BaseInput


class Input(BaseInput):
    courseId: str
    seriesNumber: int
    startTime: str
    duration: int


class Output(BaseOutput):
    ...
