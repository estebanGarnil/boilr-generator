from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ProjectInfo(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(min_length=1, strict=True)
    type: str = Field(min_length=1, strict=True)
    version: str = Field(
        default="1.0.0",
        min_length=1,
        strict=True,
    )


class ProjectModule(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    key: str = Field(min_length=1, strict=True)
    variables: dict[str, Any] = Field(
        default_factory=dict
    )
    options: dict[str, Any] = Field(
        default_factory=dict
    )


class ProjectManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: ProjectInfo
    modules: list[ProjectModule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_modules(
        self,
    ) -> "ProjectManifest":
        keys = [
            module.key
            for module in self.modules
        ]

        if len(keys) != len(set(keys)):
            raise ValueError(
                "Duplicate modules are not allowed."
            )

        return self

    def get_module(
        self,
        key: str,
    ) -> ProjectModule | None:
        return next(
            (
                module
                for module in self.modules
                if module.key == key
            ),
            None,
        )

    def has_module(self, key: str) -> bool:
        return self.get_module(key) is not None

    def list_module_keys(self) -> list[str]:
        return [
            module.key
            for module in self.modules
        ]