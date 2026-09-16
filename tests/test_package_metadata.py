from importlib.metadata import distribution, version

REPOSITORY_URL = (
    "https://github.com/estebanGarnil/boilr-generator"
)

EXPECTED_PROJECT_URLS = {
    f"Homepage, {REPOSITORY_URL}",
    f"Documentation, {REPOSITORY_URL}/tree/main/docs",
    f"Repository, {REPOSITORY_URL}",
    f"Issues, {REPOSITORY_URL}/issues",
}

EXPECTED_CLASSIFIERS = {
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Code Generators",
}


def test_distribution_identity_preserves_public_interfaces():
    package = distribution("boilr-generator")
    metadata = package.metadata

    assert metadata["Name"] == "boilr-generator"
    assert version("boilr-generator") == package.version
    assert metadata["Requires-Python"] == ">=3.11"

    assert EXPECTED_PROJECT_URLS <= set(
        metadata.get_all("Project-URL") or []
    )
    assert EXPECTED_CLASSIFIERS <= set(
        metadata.get_all("Classifier") or []
    )

    console_scripts = [
        entry_point
        for entry_point in package.entry_points
        if (
            entry_point.group == "console_scripts"
            and entry_point.name == "boilr"
        )
    ]

    assert len(console_scripts) == 1
    assert (
        console_scripts[0].value
        == "boilr_generator.cli:app"
    )