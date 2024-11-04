from pydantic import BaseModel
from typing import Optional, Union


class BaseInput(BaseModel):
    ...


class BaseOutput(BaseModel):
    message: Optional[str]
    payload: Optional[Union[dict, list]]
    success: bool
