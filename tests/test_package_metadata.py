from importlib.metadata import distribution, version


def test_distribution_identity_preserves_public_interfaces():
    package = distribution("boilr-generator")

    assert package.metadata["Name"] == "boilr-generator"
    assert version("boilr-generator") == package.version

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