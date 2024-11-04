from src.api.api_models.bases import BaseOutput, BaseInput


class Input(BaseInput):
    courseId: str
    bundle: bool = False
    contentType: str
    contentId: str = None


class Output(BaseOutput):
    ...
