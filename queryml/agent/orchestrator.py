from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from queryml.agent.bedrock import extract_response, invoke_nova, make_tool_result
from queryml.agent.tools import TOOL_DEFINITIONS, AgentTools
from queryml.semantic.models import QMLSchema

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 15


@dataclass
class InvestigationStep:
    """A single step in the agent's investigation — for UI display."""
    type: str  # "tool_call" or "tool_result" or "answer"
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_result: str | None = None
    text: str | None = None


def build_system_prompt(schema: QMLSchema, project_name: str) -> str:
    project = schema.projects[project_name]

    # Build dataset summary
    dataset_lines = []
    for ds_name in project.datasets:
        ds = schema.datasets[ds_name]
        dataset_lines.append(f"- **{ds.name}** ({ds.label}): {ds.description}")

    datasets_summary = "\n".join(dataset_lines)

    return f"""{project.system_context or ''}

## Available Datasets
{datasets_summary}

## Instructions
You are an analytics investigator. Your job is to explore data systematically to answer the user's question.

1. Start by listing or describing datasets to understand what's available.
2. Query data to find patterns, anomalies, or answers.
3. Don't stop at the first query — drill deeper when something looks unusual.
4. Use get_metric_context to understand benchmarks and thresholds.
5. Compare results against benchmarks from metric context.
6. When you've gathered enough evidence, synthesize your findings into a clear answer.

Always explain your reasoning. Reference specific numbers. Provide actionable recommendations when possible.
""".strip()


async def investigate(
    question: str,
    schema: QMLSchema,
    project_name: str,
    tools: AgentTools,
    on_step: Callable[[InvestigationStep], Any] | None = None,
    client=None,
) -> str:
    """Run a multi-step investigation to answer a question.

    Args:
        question: The user's question.
        schema: Parsed QML schema.
        project_name: Which project to use.
        tools: AgentTools instance for dispatching tool calls.
        on_step: Optional callback for each investigation step (for UI).
        client: Optional Bedrock client (for testing).

    Returns:
        The agent's final text answer.
    """
    system_prompt = build_system_prompt(schema, project_name)
    messages = [{"role": "user", "content": [{"text": question}]}]
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        response = invoke_nova(
            messages=messages,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            client=client,
        )

        text, tool_uses = extract_response(response)
        stop_reason = response.get("stopReason", "")

        # If the model returned text and no tool calls, we're done
        if text and not tool_uses:
            if on_step:
                await on_step(InvestigationStep(type="answer", text=text))
            return text

        # If we have tool calls, process them
        if tool_uses:
            # Add assistant message with all content blocks
            assistant_content = []
            if text:
                assistant_content.append({"text": text})
            for tu in tool_uses:
                assistant_content.append({"toolUse": tu})
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and collect results
            tool_results_content = []
            for tu in tool_uses:
                tool_name = tu["name"]
                tool_input = tu.get("input", {})
                tool_use_id = tu["toolUseId"]
                tool_call_count += 1

                if on_step:
                    await on_step(InvestigationStep(
                        type="tool_call",
                        tool_name=tool_name,
                        tool_input=tool_input,
                    ))

                result = tools.dispatch(tool_name, tool_input)

                if on_step:
                    await on_step(InvestigationStep(
                        type="tool_result",
                        tool_name=tool_name,
                        tool_result=result,
                    ))

                tool_results_content.append(make_tool_result(tool_use_id, result))

            messages.append({"role": "user", "content": tool_results_content})
        else:
            # No text and no tool calls — shouldn't happen, but handle gracefully
            return text or "I wasn't able to complete the investigation. Please try rephrasing your question."

    return "Investigation reached the maximum number of steps. Here's what I found so far: I was unable to fully complete the analysis within the step limit. Please try a more specific question."
