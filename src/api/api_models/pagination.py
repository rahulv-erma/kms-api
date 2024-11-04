from typing import Optional
from pydantic import BaseModel


class PaginationOutput(BaseModel):
    curPage: Optional[int]
    totalPages: Optional[int]
    pageSize: Optional[int]
