"""JSON contract shared by Python and HTTP callers."""
from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator

NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class Detection(BaseModel):
    confidence: Annotated[FiniteFloat, Field(ge=0, le=1)]
    bbox: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode='after')
    def ordered_box(self):
        x1,y1,x2,y2 = self.bbox
        if x1 < 0 or y1 < 0 or x2 < x1 or y2 < y1:
            raise ValueError('Invalid xyxy box')
        return self


class Product(BaseModel):
    class_id: NonnegativeInt
    class_name: str
    product_id: str
    count: NonnegativeInt
    detections: list[Detection]

    @model_validator(mode='after')
    def consistent_count(self):
        if self.count != len(self.detections):
            raise ValueError('Count must equal detection count')
        return self


class Prediction(BaseModel):
    model_id: str
    checkpoint_sha256: str
    image_width: Annotated[int, Field(gt=0)]
    image_height: Annotated[int, Field(gt=0)]
    count_meaning: Literal['visible_items'] = 'visible_items'
    identity_level: Literal['source_product_class'] = 'source_product_class'
    products: list[Product]
    total_count: NonnegativeInt
    annotated_image: str | None = None

    @model_validator(mode='after')
    def consistent_total(self):
        if self.total_count != sum(p.count for p in self.products):
            raise ValueError('Total must equal sum of class counts')
        if len({p.class_id for p in self.products}) != len(self.products):
            raise ValueError('Class IDs must be unique')
        return self
