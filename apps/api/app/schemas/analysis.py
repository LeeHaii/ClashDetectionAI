from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ElementMetadata(BaseModel):
    element_id: str | None = None
    layer: str | None = None
    size: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ParsedClash(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    row_index: int
    clash_id: str
    image_reference: str | None = None
    embedded_image: bytes | None = None
    embedded_media_type: str | None = None
    distance_raw: str | None = None
    distance_m: float | None = None
    grid: str | None = None
    clash_point: str | None = None
    elements: list[ElementMetadata]
    source_metadata: dict[str, str] = Field(default_factory=dict)


class RowError(BaseModel):
    row_index: int
    message: str


class ParseResult(BaseModel):
    parser_version: str
    clashes: list[ParsedClash] = Field(default_factory=list)
    errors: list[RowError] = Field(default_factory=list)


ClashType = Literal["Inserted", "Intersected", "Penetrated through"]
Orientation = Literal["Horizontal", "Vertical", "Diagonal"]
CrossSectionShape = Literal["Circular", "Rectangular", "Irregular shape"]
CrossSectionSize = Literal["Small", "Medium", "Large"]


class VisualAnalysis(BaseModel):
    clash: bool
    clash_type: ClashType | None = None
    orientation: Orientation | None = None
    cross_sectional_shape: CrossSectionShape | None = None
    cross_sectional_size: CrossSectionSize | None = None
    explanation: str | None = None


class NormalizedAnalysis(VisualAnalysis):
    clash_name: str
    elements: list[ElementMetadata]
    severity: Literal["None", "Low", "Medium", "High"]
    recommended_action: str | None = None
    report_id: str | None = None
    clash_item_id: str | None = None
    model_name: str
    adapter_version: str
    prompt_version: str
    parser_version: str
    severity_rule_version: str
