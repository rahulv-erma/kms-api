from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput


class Input(BaseInput):
    bundleName: str
    active: bool = False
    maxStudents: Optional[int] = 20
    waitlist: bool = False
    price: float
    allowCash: bool
    courseIds: List[str]
    # prerequisits: Optional[List[str]] = None
    # description: Optional[str]
    # briefDescription: Optional[str]


class Output(BaseOutput):
    ...
