from __future__ import annotations

from pathlib import Path

import yaml

from queryml.semantic.models import (
    Dataset,
    Dimension,
    Join,
    Measure,
    Project,
    QMLSchema,
    Source,
)


def parse_qml(path: str | Path) -> QMLSchema:
    """Parse a .qml YAML file into a validated QMLSchema."""
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid .qml file: expected a YAML mapping, got {type(raw).__name__}")

    sources = _parse_sources(raw.get("sources", {}))
    datasets = _parse_datasets(raw.get("datasets", {}))
    projects = _parse_projects(raw.get("projects", {}))

    schema = QMLSchema(
        version=raw.get("version", "1.0"),
        connection=raw["connection"],
        sources=sources,
        datasets=datasets,
        projects=projects,
    )

    _validate_references(schema)
    return schema


def _parse_sources(raw_sources: dict) -> dict[str, Source]:
    sources = {}
    for name, data in raw_sources.items():
        dims = {}
        for dim_name, dim_data in (data.get("dimensions") or {}).items():
            dims[dim_name] = Dimension(name=dim_name, **dim_data)

        measures = {}
        for m_name, m_data in (data.get("measures") or {}).items():
            measures[m_name] = Measure(name=m_name, **m_data)

        sources[name] = Source(
            name=name,
            table=data["table"],
            description=data.get("description"),
            dimensions=dims,
            measures=measures,
        )
    return sources


def _parse_datasets(raw_datasets: dict) -> dict[str, Dataset]:
    datasets = {}
    for name, data in raw_datasets.items():
        joins = {}
        for join_source, join_data in (data.get("joins") or {}).items():
            # PyYAML parses the bare key `on` as boolean True — map it back
            normalized = {}
            for k, v in join_data.items():
                key = "on" if k is True else str(k)
                normalized[key] = v
            joins[join_source] = Join(source_name=join_source, **normalized)

        datasets[name] = Dataset(
            name=name,
            label=data.get("label"),
            description=data.get("description"),
            source=data["source"],
            joins=joins,
        )
    return datasets


def _parse_projects(raw_projects: dict) -> dict[str, Project]:
    projects = {}
    for name, data in raw_projects.items():
        projects[name] = Project(
            name=name,
            label=data.get("label"),
            description=data.get("description"),
            datasets=data.get("datasets", []),
            default_filters=data.get("default_filters", {}),
            system_context=data.get("system_context"),
        )
    return projects


def _validate_references(schema: QMLSchema) -> None:
    """Validate all cross-references in the schema."""
    # Datasets must reference valid sources
    for ds_name, ds in schema.datasets.items():
        if ds.source not in schema.sources:
            raise ValueError(
                f"Dataset '{ds_name}' references source '{ds.source}' which is not defined"
            )
        for join_source in ds.joins:
            if join_source not in schema.sources:
                raise ValueError(
                    f"Dataset '{ds_name}' joins source '{join_source}' which is not defined"
                )

    # Projects must reference valid datasets
    for proj_name, proj in schema.projects.items():
        for ds_ref in proj.datasets:
            if ds_ref not in schema.datasets:
                raise ValueError(
                    f"Project '{proj_name}' references dataset '{ds_ref}' which is not defined"
                )
