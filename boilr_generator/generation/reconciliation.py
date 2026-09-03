"""Transactional application of project-state reconciliation plans."""

from pathlib import Path

from boilr_generator.exceptions import (
    StaleGenerationPlanError,
    StateTransactionError,
)
from boilr_generator.generation.filesystem import (
    capture_output_state,
)
from boilr_generator.state.observation import (
    classify_tracked_resources,
)
from boilr_generator.state.reconciliation import (
    ReconciliationPlan,
    build_reconciliation_plan,
)
from boilr_generator.state.serialization import (
    fingerprint_model,
)
from boilr_generator.state.storage import (
    ProjectStateStorage,
)


def _stale_plan_error(
    *,
    output_path: Path,
    plan: ReconciliationPlan,
    actual_state_sha256: str,
    reason: str,
) -> StaleGenerationPlanError:
    """Build one structured stale-reconciliation error."""
    return StaleGenerationPlanError(
        "The reconciliation plan no longer matches the project.",
        field_path="reconciliation.state",
        context={
            "output_path": str(output_path),
            "expected_state_sha256": (
                plan.base_state_sha256
            ),
            "actual_state_sha256": actual_state_sha256,
            "reason": reason,
        },
        suggestion=(
            "Inspect the project again and build a new "
            "reconciliation plan."
        ),
    )


def _transaction_error(
    *,
    output_path: Path,
    operation: str,
    error: Exception | None = None,
) -> StateTransactionError:
    """Build one structured reconciliation transaction error."""
    context = {
        "output_path": str(output_path),
        "operation": operation,
    }

    if error is not None:
        context["error"] = str(error)

    return StateTransactionError(
        "Unable to apply the project-state reconciliation.",
        field_path="reconciliation.state",
        context=context,
        suggestion=(
            "Inspect .boilr/state.json and "
            ".boilr/state.pending.json before retrying."
        ),
    )


def apply_reconciliation_plan(
    output_path: str | Path,
    plan: ReconciliationPlan,
) -> Path:
    """Atomically commit a validated reconciliation plan.

    Generated project files are never moved or rewritten. Only the
    persisted resource paths in ``.boilr/state.json`` are updated.
    """
    output_path = Path(output_path)
    storage = ProjectStateStorage(output_path)

    try:
        pending_exists = (
            storage.pending_state_path.exists()
        )
    except OSError as error:
        raise _transaction_error(
            output_path=output_path,
            operation="check_pending",
            error=error,
        ) from error

    if pending_exists:
        raise _transaction_error(
            output_path=output_path,
            operation="check_pending",
        )

    try:
        current_state = storage.read()
    except (OSError, ValueError) as error:
        raise _transaction_error(
            output_path=output_path,
            operation="read_state",
            error=error,
        ) from error

    if current_state is None:
        raise _transaction_error(
            output_path=output_path,
            operation="read_state",
        )

    current_state_sha256 = fingerprint_model(
        current_state
    )

    if current_state != plan.current_state:
        raise _stale_plan_error(
            output_path=output_path,
            plan=plan,
            actual_state_sha256=(
                current_state_sha256
            ),
            reason="committed_state_changed",
        )

    if not plan.moves:
        if plan.desired_state != plan.current_state:
            raise _stale_plan_error(
                output_path=output_path,
                plan=plan,
                actual_state_sha256=(
                    current_state_sha256
                ),
                reason="inconsistent_noop_plan",
            )

        return storage.state_path

    observed_state = capture_output_state(
        output_path
    )
    observation = classify_tracked_resources(
        current_state,
        observed_state,
    )
    accepted_moves = {
        move.resource_id: move.to_path
        for move in plan.moves
    }

    try:
        rebuilt_plan = build_reconciliation_plan(
            current_state,
            observation,
            accepted_moves,
        )
    except ValueError as error:
        raise _stale_plan_error(
            output_path=output_path,
            plan=plan,
            actual_state_sha256=(
                current_state_sha256
            ),
            reason=str(error),
        ) from error

    if (
        rebuilt_plan.moves != plan.moves
        or rebuilt_plan.desired_state
        != plan.desired_state
    ):
        raise _stale_plan_error(
            output_path=output_path,
            plan=plan,
            actual_state_sha256=(
                current_state_sha256
            ),
            reason="reconciliation_inputs_changed",
        )

    try:
        storage.begin(plan.desired_state)
    except OSError as error:
        raise _transaction_error(
            output_path=output_path,
            operation="begin",
            error=error,
        ) from error

    try:
        return storage.commit(
            plan.desired_state
        )
    except OSError as error:
        raise _transaction_error(
            output_path=output_path,
            operation="commit",
            error=error,
        ) from error