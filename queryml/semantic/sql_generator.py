from __future__ import annotations

from dataclasses import dataclass, field

from queryml.semantic.models import MeasureType, QMLSchema


@dataclass
class QueryRequest:
    dataset: str
    dimensions: list[str] = field(default_factory=list)
    measures: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    order_by: str | None = None
    order_direction: str = "desc"
    limit: int | None = None


class SQLGenerator:
    """Generate governed SQL from semantic model requests."""

    def __init__(self, schema: QMLSchema):
        self.schema = schema

    def generate(self, request: QueryRequest) -> str:
        dataset = self.schema.datasets.get(request.dataset)
        if not dataset:
            raise ValueError(f"Dataset '{request.dataset}' not found")

        primary_source = self.schema.sources[dataset.source]

        # Resolve which sources contain the requested fields
        needed_sources = set()
        select_parts = []
        group_by_parts = []

        # Build dimension SELECT clauses
        for dim_name in request.dimensions:
            source, dim = self._find_dimension(dataset, dim_name)
            needed_sources.add(source.name)
            qualified = f"{source.table}.{dim.resolved_column}"
            select_parts.append(f"{qualified} AS {dim_name}")
            group_by_parts.append(qualified)

        # Build measure SELECT clauses
        for measure_name in request.measures:
            source, measure = self._find_measure(dataset, measure_name)
            needed_sources.add(source.name)

            if measure.type == MeasureType.ratio:
                num_col = f"{source.table}.{measure.numerator}"
                den_col = f"{source.table}.{measure.denominator}"
                select_parts.append(
                    f"SUM({num_col})::FLOAT / NULLIF(SUM({den_col}), 0) AS {measure_name}"
                )
                select_parts.append(f"SUM({num_col}) AS _{measure_name}_numerator")
                select_parts.append(f"SUM({den_col}) AS _{measure_name}_denominator")
            else:
                agg_sql = self._aggregate_sql(measure.type, source.table, measure)
                select_parts.append(f"{agg_sql} AS {measure_name}")

        if not select_parts:
            raise ValueError("Query must request at least one dimension or measure")

        # FROM clause
        from_clause = primary_source.table

        # JOIN clauses — only join sources that are needed
        join_clauses = []
        for join_name, join in dataset.joins.items():
            if join_name in needed_sources and join_name != dataset.source:
                join_source = self.schema.sources[join_name]
                join_type = join.type.value.upper()
                join_clauses.append(
                    f"{join_type} JOIN {join_source.table} ON {join.on}"
                )

        # WHERE clause
        where_parts = []
        # Measure-level filters
        for measure_name in request.measures:
            _, measure = self._find_measure(dataset, measure_name)
            if measure.filters:
                for col, val in measure.filters.items():
                    where_parts.append(f"{col} = '{val}'")
        # Request-level filters
        for dim_name, val in request.filters.items():
            source, dim = self._find_dimension(dataset, dim_name)
            qualified = f"{source.table}.{dim.resolved_column}"
            where_parts.append(f"{qualified} = '{val}'")

        # Build SQL
        sql = f"SELECT {', '.join(select_parts)}"
        sql += f"\nFROM {from_clause}"
        for jc in join_clauses:
            sql += f"\n{jc}"
        if where_parts:
            sql += f"\nWHERE {' AND '.join(where_parts)}"
        if group_by_parts:
            sql += f"\nGROUP BY {', '.join(group_by_parts)}"

        if request.order_by:
            direction = request.order_direction.upper()
            if direction not in ("ASC", "DESC"):
                direction = "DESC"
            sql += f"\nORDER BY {request.order_by} {direction}"

        if request.limit:
            sql += f"\nLIMIT {request.limit}"

        return sql

    def _find_dimension(self, dataset, dim_name):
        """Find which source contains a dimension, searching primary source then joins."""
        primary = self.schema.sources[dataset.source]
        if dim_name in primary.dimensions:
            return primary, primary.dimensions[dim_name]
        for join_name in dataset.joins:
            source = self.schema.sources[join_name]
            if dim_name in source.dimensions:
                return source, source.dimensions[dim_name]
        raise ValueError(
            f"Dimension '{dim_name}' not found in dataset '{dataset.name}'"
        )

    def _find_measure(self, dataset, measure_name):
        """Find which source contains a measure, searching primary source then joins."""
        primary = self.schema.sources[dataset.source]
        if measure_name in primary.measures:
            return primary, primary.measures[measure_name]
        for join_name in dataset.joins:
            source = self.schema.sources[join_name]
            if measure_name in source.measures:
                return source, source.measures[measure_name]
        raise ValueError(
            f"Measure '{measure_name}' not found in dataset '{dataset.name}'"
        )

    @staticmethod
    def _aggregate_sql(measure_type: MeasureType, table: str, measure) -> str:
        col = f"{table}.{measure.resolved_column}"
        match measure_type:
            case MeasureType.count:
                return "COUNT(*)"
            case MeasureType.sum:
                return f"SUM({col})"
            case MeasureType.avg:
                return f"AVG({col})"
            case MeasureType.min:
                return f"MIN({col})"
            case MeasureType.max:
                return f"MAX({col})"
            case MeasureType.count_distinct:
                return f"COUNT(DISTINCT {col})"
            case _:
                raise ValueError(f"Unsupported measure type: {measure_type}")
