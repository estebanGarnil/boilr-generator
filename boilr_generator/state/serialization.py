"""Deterministic in-memory serialization for project state."""

import json
from hashlib import sha256

from pydantic import BaseModel

from boilr_generator.state.schemas import ProjectState


def serialize_project_state(
    state: ProjectState,
) -> bytes:
    """Serialize a validated state to deterministic UTF-8 JSON."""
    value = state.model_dump(mode="json")

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
    )

    return f"{serialized}\n".encode()


def deserialize_project_state(
    content: bytes | str,
) -> ProjectState:
    """Deserialize and validate one project state document."""
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    return ProjectState.model_validate_json(content)


def fingerprint_model(
    model: BaseModel,
) -> str:
    """Fingerprint a normalized validated Pydantic model."""
    value = model.model_dump(
        mode="json",
        by_alias=True,
    )

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return sha256(
        serialized.encode("utf-8")
    ).hexdigest()