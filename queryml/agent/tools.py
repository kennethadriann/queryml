from __future__ import annotations

import json
from typing import Any

from queryml.engine.duckdb_engine import DuckDBEngine
from queryml.semantic.models import QMLSchema
from queryml.semantic.sql_generator import QueryRequest, SQLGenerator


class AgentTools:
    """Tools the agent can call during investigation."""

    def __init__(self, schema: QMLSchema, engine: DuckDBEngine, project_name: str):
        self.schema = schema
        self.engine = engine
        self.project = schema.projects[project_name]
        self.sql_gen = SQLGenerator(schema)

    def list_datasets(self) -> str:
        """Return available datasets with descriptions."""
        datasets = []
        for ds_name in self.project.datasets:
            ds = self.schema.datasets[ds_name]
            datasets.append({
                "name": ds.name,
                "label": ds.label,
                "description": ds.description,
            })
        return json.dumps(datasets, indent=2)

    def describe_dataset(self, dataset: str) -> str:
        """Return full schema of a dataset."""
        ds = self.schema.datasets.get(dataset)
        if not ds:
            return json.dumps({"error": f"Dataset '{dataset}' not found"})

        # Collect all dimensions and measures from primary source + joins
        dimensions = []
        measures = []

        sources_to_check = [ds.source] + list(ds.joins.keys())
        for source_name in sources_to_check:
            source = self.schema.sources.get(source_name)
            if not source:
                continue
            for dim in source.dimensions.values():
                dimensions.append({
                    "name": dim.name,
                    "type": dim.type.value,
                    "hint": dim.hint,
                    "description": dim.description,
                    "source": source_name,
                })
            for m in source.measures.values():
                measures.append({
                    "name": m.name,
                    "type": m.type.value,
                    "hint": m.hint,
                    "context": m.context,
                    "description": m.description,
                    "source": source_name,
                })

        return json.dumps({
            "name": ds.name,
            "label": ds.label,
            "description": ds.description,
            "dimensions": dimensions,
            "measures": measures,
            "joins": list(ds.joins.keys()),
        }, indent=2)

    def query_data(
        self,
        dataset: str,
        dimensions: list[str] | None = None,
        measures: list[str] | None = None,
        filters: dict[str, str] | None = None,
        order_by: str | None = None,
        order_direction: str = "desc",
        limit: int | None = None,
    ) -> str:
        """Execute a governed query through the semantic model."""
        # Merge project default filters with request filters
        merged_filters = dict(self.project.default_filters)
        if filters:
            merged_filters.update(filters)

        request = QueryRequest(
            dataset=dataset,
            dimensions=dimensions or [],
            measures=measures or [],
            filters=merged_filters,
            order_by=order_by,
            order_direction=order_direction,
            limit=limit,
        )

        try:
            sql = self.sql_gen.generate(request)
            result = self.engine.execute(sql)
            result["sql"] = sql
            result["row_count"] = len(result["rows"])
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_metric_context(self, dataset: str, measure: str) -> str:
        """Return context/benchmark metadata for a measure."""
        ds = self.schema.datasets.get(dataset)
        if not ds:
            return json.dumps({"error": f"Dataset '{dataset}' not found"})

        # Search primary + joined sources
        sources_to_check = [ds.source] + list(ds.joins.keys())
        for source_name in sources_to_check:
            source = self.schema.sources.get(source_name)
            if source and measure in source.measures:
                m = source.measures[measure]
                return json.dumps({
                    "name": m.name,
                    "type": m.type.value,
                    "hint": m.hint,
                    "context": m.context,
                    "description": m.description,
                })

        return json.dumps({"error": f"Measure '{measure}' not found in dataset '{dataset}'"})

    def dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Dispatch a tool call by name."""
        match tool_name:
            case "list_datasets":
                return self.list_datasets()
            case "describe_dataset":
                return self.describe_dataset(**tool_input)
            case "query_data":
                return self.query_data(**tool_input)
            case "get_metric_context":
                return self.get_metric_context(**tool_input)
            case _:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})


# Tool definitions in Bedrock Converse format
TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "list_datasets",
            "description": "List all available datasets with their names, labels, and descriptions. Call this first to understand what data is available.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "describe_dataset",
            "description": "Get the full schema of a dataset — all dimensions (fields to group/filter by) and measures (metrics to calculate) with their hints and context. Call this to understand what you can query.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "type": "string",
                            "description": "Name of the dataset to describe",
                        }
                    },
                    "required": ["dataset"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "query_data",
            "description": "Execute a data query through the semantic model. Specify dimensions to group by, measures to calculate, optional filters, ordering, and limit. Results are returned as columns and rows.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "type": "string",
                            "description": "Name of the dataset to query",
                        },
                        "dimensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dimension names to group by",
                        },
                        "measures": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Measure names to calculate",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Filter conditions as {dimension_name: value}",
                        },
                        "order_by": {
                            "type": "string",
                            "description": "Column name to order results by",
                        },
                        "order_direction": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "Sort direction (default: desc)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return",
                        },
                    },
                    "required": ["dataset"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_metric_context",
            "description": "Get benchmark context and interpretation guidance for a specific measure. Call this to understand what good/bad values look like.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "type": "string",
                            "description": "Name of the dataset",
                        },
                        "measure": {
                            "type": "string",
                            "description": "Name of the measure to get context for",
                        },
                    },
                    "required": ["dataset", "measure"],
                }
            },
        }
    },
]
