from typing import List, Optional
from src.api.api_models.bases import BaseOutput, BaseInput


class UpdateBundleInput(BaseInput):
    bundleId: str
    bundleName: Optional[str] = None
    active: Optional[bool] = None
    maxStudents: Optional[int] = None
    waitlist: Optional[bool] = None
    price: Optional[float] = None
    allowCash: Optional[bool] = None
    courseIds: Optional[List[str]] = None
    isFull: Optional[bool] = None


class Output(BaseOutput):
    ...
