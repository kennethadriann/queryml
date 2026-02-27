from pathlib import Path

import duckdb
import pytest

from queryml.semantic.parser import parse_qml
from queryml.semantic.sql_generator import SQLGenerator, QueryRequest
from queryml.engine.duckdb_engine import DuckDBEngine

SCHEMA_PATH = Path(__file__).parent.parent / "projects" / "ecommerce" / "schema.qml"
PROJECT_DIR = Path(__file__).parent.parent / "projects" / "ecommerce"


@pytest.fixture
def schema():
    return parse_qml(SCHEMA_PATH)


@pytest.fixture
def gen(schema):
    return SQLGenerator(schema)


@pytest.fixture
def engine():
    eng = DuckDBEngine("duckdb:///data/ecommerce.db", base_path=PROJECT_DIR)
    yield eng
    eng.close()


def test_simple_dimension_query(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region"],
        measures=["total_revenue"],
    ))
    assert "SELECT" in sql
    assert "orders.region" in sql
    assert "SUM(orders.revenue)" in sql
    assert "GROUP BY" in sql


def test_multiple_dimensions(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region", "customer_segment"],
        measures=["order_count"],
    ))
    assert "orders.region" in sql
    assert "orders.customer_segment" in sql
    assert "COUNT(*)" in sql


def test_ratio_measure_with_explainability(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region"],
        measures=["return_rate"],
    ))
    assert "NULLIF" in sql
    assert "_return_rate_numerator" in sql
    assert "_return_rate_denominator" in sql


def test_join_added_when_needed(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["category"],
        measures=["total_revenue"],
    ))
    assert "JOIN products" in sql
    assert "orders.product_id = products.product_id" in sql


def test_join_not_added_when_unnecessary(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region"],
        measures=["total_revenue"],
    ))
    assert "JOIN" not in sql


def test_filter_applied(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["customer_segment"],
        measures=["total_revenue"],
        filters={"region": "West"},
    ))
    assert "WHERE" in sql
    assert "orders.region = 'West'" in sql


def test_order_and_limit(gen):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region"],
        measures=["total_revenue"],
        order_by="total_revenue",
        order_direction="desc",
        limit=5,
    ))
    assert "ORDER BY total_revenue DESC" in sql
    assert "LIMIT 5" in sql


def test_execute_query(gen, engine):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region"],
        measures=["total_revenue", "order_count"],
        order_by="total_revenue",
        order_direction="desc",
    ))
    result = engine.execute(sql)
    assert len(result["columns"]) == 3  # region, total_revenue, order_count
    assert len(result["rows"]) > 0
    # Check regions exist
    regions = [row[0] for row in result["rows"]]
    assert set(regions) <= {"West", "East", "Central", "South"}


def test_execute_ratio_query(gen, engine):
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["region"],
        measures=["return_rate"],
        order_by="return_rate",
        order_direction="desc",
    ))
    result = engine.execute(sql)
    # Should have: region, return_rate, _return_rate_numerator, _return_rate_denominator
    assert len(result["columns"]) == 4
    for row in result["rows"]:
        rate, num, den = row[1], row[2], row[3]
        if den > 0:
            assert abs(rate - num / den) < 0.001


def test_cross_source_query(gen, engine):
    """Query with dimensions from joined source."""
    sql = gen.generate(QueryRequest(
        dataset="sales_overview",
        dimensions=["category"],
        measures=["total_revenue"],
        order_by="total_revenue",
        order_direction="desc",
    ))
    result = engine.execute(sql)
    categories = [row[0] for row in result["rows"]]
    assert set(categories) <= {"Electronics", "Clothing", "Home", "Office Supplies"}


def test_unknown_dataset(gen):
    with pytest.raises(ValueError, match="not found"):
        gen.generate(QueryRequest(dataset="nonexistent", dimensions=["x"]))


def test_unknown_dimension(gen):
    with pytest.raises(ValueError, match="not found"):
        gen.generate(QueryRequest(
            dataset="sales_overview",
            dimensions=["nonexistent_dim"],
        ))
