from __future__ import annotations

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "amazon.nova-pro-v1:0"


def get_model_id() -> str:
    return os.environ.get("NOVA_MODEL_ID", DEFAULT_MODEL_ID)


def get_client():
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def invoke_nova(
    messages: list[dict],
    system: str,
    tools: list[dict],
    client=None,
) -> dict:
    """Call Amazon Nova via the Bedrock Converse API.

    Returns the full Converse API response dict.
    """
    if client is None:
        client = get_client()

    kwargs = {
        "modelId": get_model_id(),
        "messages": messages,
        "system": [{"text": system}],
    }
    if tools:
        kwargs["toolConfig"] = {"tools": tools}

    response = client.converse(**kwargs)
    return response


def extract_response(response: dict) -> tuple[str | None, list[dict]]:
    """Extract text and tool_use blocks from a Converse API response.

    Returns (text_content, tool_use_list).
    """
    output = response.get("output", {})
    message = output.get("message", {})
    content = message.get("content", [])

    text = None
    tool_uses = []
    for block in content:
        if "text" in block:
            text = block["text"]
        elif "toolUse" in block:
            tool_uses.append(block["toolUse"])

    return text, tool_uses


def make_tool_result(tool_use_id: str, result: str) -> dict:
    """Build a toolResult content block for the Converse API."""
    return {
        "toolResult": {
            "toolUseId": tool_use_id,
            "content": [{"text": result}],
        }
    }
