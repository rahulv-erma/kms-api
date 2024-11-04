from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel


class Choice(BaseModel):
    description: str
    choicePosition: int
    active: bool
    isCorrect: bool


class Question(BaseModel):
    questionId: str
    questionNumber: int
    description: str
    pointValue: int
    answerType: str
    active: bool
    choices: Optional[List[Choice]]


class Quiz(BaseModel):
    formId: str
    formName: str
    active: bool
    passingPoints: int
    questions: Optional[List[Question]]
    attempts: Optional[int] = 1
    duration: Optional[int] = None


class formPayload(BaseModel):
    form: Optional[Quiz]


class Output(BaseOutput):
    payload: formPayload
