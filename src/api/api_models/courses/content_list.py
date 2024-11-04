from typing import List, Optional

from src.api.api_models.bases import BaseOutput, BaseModel
from src.api.api_models.pagination import PaginationOutput


class Content(BaseModel):
    contentId: str
    contentName: str
    published: Optional[bool]


class ContentPayload(BaseModel):
    content: List[Optional[Content]]
    pagination: Optional[PaginationOutput]


class Output(BaseOutput):
    payload: ContentPayload
