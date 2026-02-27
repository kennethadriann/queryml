import json
import logging
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

from queryml.agent.orchestrator import InvestigationStep, investigate
from queryml.agent.tools import AgentTools
from queryml.engine.duckdb_engine import DuckDBEngine
from queryml.semantic.parser import parse_qml

load_dotenv()
logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(__file__).parent / "projects"


def discover_projects() -> dict[str, Path]:
    """Find all projects with a schema.qml file."""
    projects = {}
    for project_dir in PROJECTS_DIR.iterdir():
        schema_path = project_dir / "schema.qml"
        if project_dir.is_dir() and schema_path.exists():
            projects[project_dir.name] = schema_path
    return projects


def load_project(project_dir_name: str):
    """Load a project: parse schema, connect to DB, return everything needed."""
    schema_path = PROJECTS_DIR / project_dir_name / "schema.qml"
    project_base = PROJECTS_DIR / project_dir_name

    schema = parse_qml(schema_path)
    engine = DuckDBEngine(schema.connection, base_path=project_base)

    # Validate tables exist
    expected_tables = [s.table for s in schema.sources.values()]
    missing = engine.validate_tables(expected_tables)
    if missing:
        raise RuntimeError(f"Missing tables in database: {missing}")

    # Find the first project defined in the schema
    project_name = next(iter(schema.projects))
    tools = AgentTools(schema, engine, project_name)

    return schema, engine, tools, project_name


@cl.on_chat_start
async def start():
    available = discover_projects()
    if not available:
        await cl.Message(content="No projects found. Add a project directory with a `schema.qml` to `projects/`.").send()
        return

    # Default to first available project
    project_dir_name = next(iter(available))

    try:
        schema, engine, tools, project_name = load_project(project_dir_name)
    except Exception as e:
        await cl.Message(content=f"Failed to load project: {e}").send()
        return

    project = schema.projects[project_name]
    cl.user_session.set("schema", schema)
    cl.user_session.set("engine", engine)
    cl.user_session.set("tools", tools)
    cl.user_session.set("project_name", project_name)

    await cl.Message(
        content=f"Welcome to **{project.label}**!\n\n{project.description}\n\nAsk me anything about your data."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    schema = cl.user_session.get("schema")
    tools = cl.user_session.get("tools")
    project_name = cl.user_session.get("project_name")

    if not schema or not tools:
        await cl.Message(content="No project loaded. Please restart the chat.").send()
        return

    # Track steps for display
    step_count = 0

    async def on_step(step: InvestigationStep):
        nonlocal step_count
        if step.type == "tool_call":
            step_count += 1
            # Format tool call as a visible step
            name = step.tool_name
            inputs = step.tool_input or {}

            if name == "query_data":
                dims = inputs.get("dimensions", [])
                measures = inputs.get("measures", [])
                filters = inputs.get("filters", {})
                label = f"Querying {inputs.get('dataset', '?')}"
                details = []
                if measures:
                    details.append(f"measures: {', '.join(measures)}")
                if dims:
                    details.append(f"by: {', '.join(dims)}")
                if filters:
                    details.append(f"where: {filters}")
                desc = " | ".join(details) if details else ""
            elif name == "describe_dataset":
                label = f"Describing {inputs.get('dataset', '?')}"
                desc = ""
            elif name == "list_datasets":
                label = "Listing datasets"
                desc = ""
            elif name == "get_metric_context":
                label = f"Getting context for {inputs.get('measure', '?')}"
                desc = ""
            else:
                label = name
                desc = json.dumps(inputs)

            async with cl.Step(name=label, type="tool") as s:
                s.output = desc

        elif step.type == "tool_result":
            # Parse result to show row count for queries
            try:
                result = json.loads(step.tool_result)
                if "row_count" in result:
                    async with cl.Step(name="Results", type="tool") as s:
                        s.output = f"{result['row_count']} rows returned"
            except (json.JSONDecodeError, TypeError):
                pass

    try:
        answer = await investigate(
            question=message.content,
            schema=schema,
            project_name=project_name,
            tools=tools,
            on_step=on_step,
        )

        footer = f"\n\n---\n*Investigation: {step_count} tool calls*"
        await cl.Message(content=answer + footer).send()

    except Exception as e:
        logger.exception("Investigation failed")
        await cl.Message(
            content=f"Something went wrong during the investigation: {e}\n\nPlease try again or rephrase your question."
        ).send()
