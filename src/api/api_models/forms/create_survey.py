from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel


class Choices(BaseModel):
    description: str
    choicePosition: int
    active: bool


class Questions(BaseModel):
    questionNumber: int
    description: str
    answerType: str
    active: bool
    choices: Optional[List[Choices]] = None


class Output(BaseOutput):
    ...


class Input(BaseInput):
    formName: str
    active: bool
    questions: List[Questions]
