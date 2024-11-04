from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel


class Output(BaseOutput):
    ...


class Choices(BaseModel):
    description: str
    choicePosition: int
    active: bool
    isCorrect: bool = False


class Questions(BaseModel):
    questionNumber: int
    description: str
    pointValue: int
    answerType: str
    active: bool
    choices: Optional[List[Choices]] = None


class Input(BaseInput):
    formName: str
    active: bool
    passingPoints: int
    attempts: Optional[int] = 1
    questions: List[Questions]
    duration: Optional[int] = None
