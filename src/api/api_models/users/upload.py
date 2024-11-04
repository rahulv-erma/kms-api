from typing import Optional, List

from src.api.api_models.bases import BaseOutput, BaseModel


class Payload(BaseModel):
    failed: Optional[bool]
    reason: Optional[str]
    userId: Optional[str]
    headShot: Optional[str]
    photoIdPhoto: Optional[str]
    otherIdPhoto: Optional[str]


class BulkPayload(BaseModel):
    headShots: Optional[List[Payload]]


class BulkOutput(BaseOutput):
    payload: Optional[List[BulkPayload]]


class Output(BaseOutput):
    payload: Optional[Payload]
