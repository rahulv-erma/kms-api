from typing import List, Optional
from src.api.api_models.bases import BaseModel
from src.api.api_models.courses import list_courses_model, bundle
from src.api.api_models.pagination import PaginationOutput


class Output(BaseModel):
    courses: List[list_courses_model.Course]
    bundles: List[bundle.Input]
    coursePagination: Optional[PaginationOutput]
    bundlePagination: Optional[PaginationOutput]
