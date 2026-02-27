from pathlib import Path

import pytest

from queryml.semantic.parser import parse_qml
from queryml.semantic.models import MeasureType, DimensionType

SCHEMA_PATH = Path(__file__).parent.parent / "projects" / "ecommerce" / "schema.qml"


def test_parse_ecommerce_schema():
    schema = parse_qml(SCHEMA_PATH)
    assert schema.version == "1.0"
    assert "duckdb" in schema.connection


def test_sources_parsed():
    schema = parse_qml(SCHEMA_PATH)
    assert "orders" in schema.sources
    assert "products" in schema.sources
    assert "customers" in schema.sources
    assert schema.sources["orders"].table == "orders"


def test_dimensions_parsed():
    schema = parse_qml(SCHEMA_PATH)
    orders = schema.sources["orders"]
    assert "order_date" in orders.dimensions
    assert orders.dimensions["order_date"].type == DimensionType.date
    assert orders.dimensions["region"].hint is not None


def test_measures_parsed():
    schema = parse_qml(SCHEMA_PATH)
    orders = schema.sources["orders"]
    assert "total_revenue" in orders.measures
    assert orders.measures["total_revenue"].type == MeasureType.sum
    assert orders.measures["total_revenue"].column == "revenue"


def test_ratio_measure():
    schema = parse_qml(SCHEMA_PATH)
    return_rate = schema.sources["orders"].measures["return_rate"]
    assert return_rate.type == MeasureType.ratio
    assert return_rate.numerator == "is_returned"
    assert return_rate.denominator == "order_count_raw"


def test_datasets_parsed():
    schema = parse_qml(SCHEMA_PATH)
    assert "sales_overview" in schema.datasets
    ds = schema.datasets["sales_overview"]
    assert ds.source == "orders"
    assert "products" in ds.joins
    assert "customers" in ds.joins


def test_projects_parsed():
    schema = parse_qml(SCHEMA_PATH)
    assert "ecommerce" in schema.projects
    proj = schema.projects["ecommerce"]
    assert "sales_overview" in proj.datasets
    assert proj.system_context is not None


def test_column_defaults_to_name():
    schema = parse_qml(SCHEMA_PATH)
    order_id = schema.sources["orders"].dimensions["order_id"]
    assert order_id.resolved_column == "order_id"


def test_invalid_source_reference(tmp_path):
    bad_qml = tmp_path / "bad.qml"
    bad_qml.write_text("""
version: "1.0"
connection: duckdb:///test.db
sources:
  orders:
    table: orders
datasets:
  bad_dataset:
    source: nonexistent
""")
    with pytest.raises(ValueError, match="references source 'nonexistent'"):
        parse_qml(bad_qml)


def test_invalid_dataset_reference(tmp_path):
    bad_qml = tmp_path / "bad.qml"
    bad_qml.write_text("""
version: "1.0"
connection: duckdb:///test.db
sources:
  orders:
    table: orders
datasets:
  good_dataset:
    source: orders
projects:
  bad_project:
    datasets:
      - nonexistent_dataset
""")
    with pytest.raises(ValueError, match="references dataset 'nonexistent_dataset'"):
        parse_qml(bad_qml)
