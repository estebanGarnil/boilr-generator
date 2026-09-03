"""Read-only observation of generated projects."""

from pathlib import Path

from boilr_generator.generation.filesystem import (
    capture_output_state,
)
from boilr_generator.state.observation import (
    ProjectObservation,
    classify_tracked_resources,
)
from boilr_generator.state.storage import (
    ProjectStateStorage,
)


def observe_project(
    output_path: str | Path,
) -> ProjectObservation | None:
    """Observe one project from its last committed state.

    Return ``None`` when the output does not contain a committed
    ``.boilr/state.json`` file. A pending transaction is deliberately
    ignored: the last committed state remains the reference baseline.
    """
    output_path = Path(output_path)
    storage = ProjectStateStorage(output_path)
    project_state = storage.read()

    if project_state is None:
        return None

    observed_state = capture_output_state(output_path)

    return classify_tracked_resources(
        project_state,
        observed_state,
    )