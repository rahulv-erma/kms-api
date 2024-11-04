from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel


class Output(BaseOutput):
    success: bool


class Answer(BaseModel):
    choicePosition: Optional[int]
    description: Optional[str]
    response: Optional[str]


class Questions(BaseModel):
    questionId: str
    questionNumber: int
    description: int
    answerType: str
    answer: Answer


class Input(BaseInput):
    questions: List[Questions]
