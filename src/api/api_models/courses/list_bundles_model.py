from typing import Optional, List
from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models import pagination


class Bundle(BaseModel):
    bundlePicture: str
    bundleId: str
    bundleName: str
    active: bool
    complete: bool
    totalClasses: int
    courseType: str
    startDate: str


class BundlePayload(BaseOutput):
    bundles: List[Optional[Bundle]]
    pagination: Optional[pagination.PaginationOutput]


class Output(BaseOutput):
    payload: BundlePayload
