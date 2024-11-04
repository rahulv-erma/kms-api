from typing import List, Optional

from src.api.api_models.bases import BaseOutput, BaseInput


class Output(BaseOutput):
    ...


class Input(BaseInput):
    courseIds: Optional[List[str]] = None
    bundleIds: Optional[List[str]] = None
