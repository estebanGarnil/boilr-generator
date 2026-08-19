import json
from hashlib import sha256

from boilr_generator.core.generation_plan import (
    GenerationPlan,
    PlannedDirectory,
    PlannedFile,
    PlannedPathState,
    PlannedRemoval,
)


def test_generation_plan_serializes_filesystem_contract(
    resolved_project,
    tmp_path,
):
    output_path = tmp_path / "output"
    existing_path = output_path / "existing.txt"
    directory_path = output_path / "nested"
    destination_path = directory_path / "generated.txt"

    existing_content = b"existing content"
    planned_content = b"planned content"

    plan = GenerationPlan(
        resolved_project=resolved_project,
        output_path=output_path,
        initial_output_state=[
            PlannedPathState(
                path=output_path,
                relative_path=".",
                exists=True,
                kind="directory",
                mode=0o755,
            ),
            PlannedPathState(
                path=existing_path,
                relative_path="existing.txt",
                exists=True,
                kind="file",
                content_size=len(existing_content),
                content_sha256=sha256(
                    existing_content
                ).hexdigest(),
                mode=0o644,
            ),
        ],
        directories=[
            PlannedDirectory(
                path=directory_path,
                relative_path="nested",
                reason="parent",
                module="django",
            )
        ],
        files=[
            PlannedFile(
                source_path=None,
                destination_path=destination_path,
                relative_destination_path=(
                    "nested/generated.txt"
                ),
                operation="generate",
                action="create",
                content=planned_content,
                module=None,
                mode=0o640,
            )
        ],
        removals=[
            PlannedRemoval(
                path=existing_path,
                relative_path="existing.txt",
                module="django",
                reason="replace",
                kind="file",
            )
        ],
        clean_output=True,
    )

    data = plan.to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["output_path"] == str(output_path)
    assert data["clean_output"] is True

    root_state = data["initial_output_state"][0]
    file_state = data["initial_output_state"][1]

    assert root_state == {
        "path": str(output_path),
        "relative_path": ".",
        "exists": True,
        "kind": "directory",
        "content_size": None,
        "content_sha256": None,
        "mode": 0o755,
        "link_target": None,
    }
    assert file_state["path"] == str(existing_path)
    assert file_state["content_size"] == len(
        existing_content
    )
    assert file_state["content_sha256"] == sha256(
        existing_content
    ).hexdigest()

    directory = data["directories"][0]

    assert directory == {
        "path": str(directory_path),
        "relative_path": "nested",
        "reason": "parent",
        "module": "django",
    }

    serialized_file = data["files"][0]

    assert "content" not in serialized_file
    assert serialized_file["source_path"] is None
    assert serialized_file["destination_path"] == str(
        destination_path
    )
    assert serialized_file["content_size"] == len(
        planned_content
    )
    assert serialized_file["content_sha256"] == sha256(
        planned_content
    ).hexdigest()
    assert serialized_file["mode"] == 0o640

    removal = data["removals"][0]

    assert removal == {
        "path": str(existing_path),
        "relative_path": "existing.txt",
        "module": "django",
        "reason": "replace",
        "kind": "file",
    }


def test_generation_plan_summary_counts_contract_operations(
    resolved_project,
    tmp_path,
):
    output_path = tmp_path / "output"

    files = [
        PlannedFile(
            source_path=None,
            destination_path=output_path / "create.txt",
            relative_destination_path="create.txt",
            operation="generate",
            action="create",
            content=b"a",
        ),
        PlannedFile(
            source_path=None,
            destination_path=output_path / "overwrite.txt",
            relative_destination_path="overwrite.txt",
            operation="generate",
            action="overwrite",
            content=b"bb",
        ),
        PlannedFile(
            source_path=None,
            destination_path=output_path / "skip.txt",
            relative_destination_path="skip.txt",
            operation="copy",
            action="skip",
            content=b"ccc",
        ),
    ]

    plan = GenerationPlan(
        resolved_project=resolved_project,
        output_path=output_path,
        initial_output_state=[
            PlannedPathState(
                path=output_path,
                relative_path=".",
                exists=False,
            )
        ],
        directories=[
            PlannedDirectory(
                path=output_path,
                relative_path=".",
                reason="output",
            ),
            PlannedDirectory(
                path=output_path / "nested",
                relative_path="nested",
                reason="parent",
            ),
        ],
        files=files,
        removals=[
            PlannedRemoval(
                path=output_path / "old.txt",
                relative_path="old.txt",
                reason="clean",
                kind="file",
            ),
            PlannedRemoval(
                path=output_path / "old-directory",
                relative_path="old-directory",
                reason="replace",
                kind="directory",
            ),
        ],
        docker_services=["backend"],
        env_variables=["FIRST", "SECOND"],
    )

    assert plan.summary == {
        "modules_count": len(
            resolved_project.modules
        ),
        "initial_paths_count": 1,
        "directories_to_create": 2,
        "files_count": 3,
        "files_to_create": 1,
        "files_to_overwrite": 1,
        "files_to_skip": 1,
        "removals_count": 2,
        "clean_removals_count": 1,
        "replace_removals_count": 1,
        "docker_services_count": 1,
        "env_variables_count": 2,
        "content_bytes": 6,
        "content_bytes_to_write": 3,
    }