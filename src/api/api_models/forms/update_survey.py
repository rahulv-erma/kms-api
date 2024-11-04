from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput, BaseModel


class Output(BaseOutput):
    ...


class Choices(BaseModel):
    answerId: Optional[str] = None
    description: Optional[str]
    choicePosition: Optional[int]
    active: Optional[bool]


class Questions(BaseModel):
    questionId: Optional[str] = None
    questionNumber: Optional[int]
    description: Optional[str]
    answerType: Optional[str] = None
    active: Optional[bool]
    choices: Optional[List[Choices]] = None


class Input(BaseInput):
    formId: str
    formName: Optional[str]
    active: Optional[bool]
    questions: Optional[List[Questions]]
