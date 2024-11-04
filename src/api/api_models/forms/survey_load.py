from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel


class Choice(BaseModel):
    answerId: str
    description: str
    choicePosition: int
    active: bool


class Question(BaseModel):
    questionId: str
    questionNumber: int
    description: str
    answerType: str
    active: bool
    choices: Optional[List[Choice]]


class Survey(BaseModel):
    formId: str
    formName: str
    active: bool
    questions: Optional[List[Question]]


class formPayload(BaseModel):
    form: Optional[Survey]


class Output(BaseOutput):
    payload: formPayload
