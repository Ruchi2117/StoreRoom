"""Validate human review data; inference remains separate."""
from datetime import datetime
from uuid import UUID
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.inference.config import load_config
from src.inference.results import Prediction, Detection

# Shared model mapping, not a second catalog. Counts are safe in browser JSON.
NAMES = load_config().names
Count = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    class_id: Annotated[int, Field(strict=True, ge=0, lt=len(NAMES))]
    class_name: str
    predicted_count: Count
    confirmed_count: Count

    @model_validator(mode='after')
    def known_identity(self):
        if self.class_name != NAMES[self.class_id]:
            raise ValueError('Class name does not match class ID')
        return self


class ReviewItems(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: Annotated[list[ReviewItem], Field(max_length=len(NAMES))]

    @model_validator(mode='after')
    def unique_classes(self):
        if len({item.class_id for item in self.items}) != len(self.items):
            raise ValueError('Each class may appear only once')
        return self


class ReviewRequest(ReviewItems):
    prediction_id: UUID


class EvidencePrediction(Prediction):
    prediction_id: UUID


class StoredDetection(Detection):
    class_id: int
    class_name: str


class ConfirmedReview(ReviewItems):
    status: Literal['confirmed'] = 'confirmed'
    count_meaning: Literal['visible_items'] = 'visible_items'
    persisted: Literal[True] = True
    scan_id: UUID
    created_at: datetime
    confirmed_at: datetime  # Compatibility with v0.3 clients; same as created_at.
    prediction_id: UUID | None = None
    original_image_url: str | None = None
    annotated_image_url: str | None = None
    original_prediction: Prediction | None = None
    detections: list[StoredDetection] = Field(default_factory=list)


class ScanSummary(BaseModel):
    scan_id: UUID
    created_at: datetime
    item_count: int  # Number of represented classes, not packages.


class ScanHistory(BaseModel):
    scans: list[ScanSummary]
