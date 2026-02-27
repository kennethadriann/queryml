from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator


class DimensionType(str, Enum):
    string = "string"
    number = "number"
    date = "date"
    boolean = "boolean"


class MeasureType(str, Enum):
    count = "count"
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    count_distinct = "count_distinct"
    ratio = "ratio"


class JoinType(str, Enum):
    left = "left"
    inner = "inner"
    full = "full"


class Relationship(str, Enum):
    one_to_one = "one_to_one"
    one_to_many = "one_to_many"
    many_to_one = "many_to_one"
    many_to_many = "many_to_many"


class Dimension(BaseModel):
    name: str
    type: DimensionType
    column: Optional[str] = None  # defaults to name
    hint: Optional[str] = None
    description: Optional[str] = None

    @property
    def resolved_column(self) -> str:
        return self.column or self.name


class Measure(BaseModel):
    name: str
    type: MeasureType
    column: Optional[str] = None
    hint: Optional[str] = None
    context: Optional[str] = None
    description: Optional[str] = None
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    filters: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def validate_ratio(self):
        if self.type == MeasureType.ratio:
            if not self.numerator or not self.denominator:
                raise ValueError(
                    f"Measure '{self.name}' is ratio type — numerator and denominator required"
                )
        return self

    @property
    def resolved_column(self) -> str:
        return self.column or self.name


class Source(BaseModel):
    name: str
    table: str
    description: Optional[str] = None
    dimensions: dict[str, Dimension] = {}
    measures: dict[str, Measure] = {}


class Join(BaseModel):
    source_name: str
    on: str
    type: JoinType = JoinType.left
    relationship: Relationship = Relationship.one_to_many


class Dataset(BaseModel):
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    source: str  # primary source name
    joins: dict[str, Join] = {}


class Project(BaseModel):
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    datasets: list[str] = []
    default_filters: dict[str, str] = {}
    system_context: Optional[str] = None


class QMLSchema(BaseModel):
    version: str = "1.0"
    connection: str
    sources: dict[str, Source] = {}
    datasets: dict[str, Dataset] = {}
    projects: dict[str, Project] = {}
