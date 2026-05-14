from typing import Any

from boilr_generator.core import ResolvedModule
from boilr_generator.resolver.exceptions import ResolverError


class RequirementValidationError(ResolverError):
    """Raised when module requirements are not satisfied."""

class CompatibilityValidationError(ResolverError):
    """Raised when modules are not compatible."""    

class VariableValidationError(ResolverError):
    """Raised when module variables are invalid."""

class VariableTypeValidationError(ResolverError):
    """Raised when a variable has an invalid type."""


class ProjectValidator: 
    def validate_requirements(self, modules: list[ResolvedModule]) -> None:
        for module in modules:
            self._validate_module_requirements(module, modules)

    def _validate_compatibility(
            self, 
            modules: list[ResolvedModule]  
    ) -> None:
        for module in modules: 
            for other in modules:
                if module == other: 
                    continue
                if not module.manifest.compatibility.is_compatible(
                    other.type,
                    other.key,
                ):
                    raise CompatibilityValidationError(
                        f"Module '{module.key}' is not compatible with "
                        f"'{other.key}' (type: {other.type})."
                    )        

    def _validate_module_requirements(
            self, 
            module: ResolvedModule, 
            all_modules: list[ResolvedModule],
    ) -> None: 
        for requirement in module.manifest.requirements.mandatory: 
            matching_modules = [
                candidate 
                for candidate in all_modules
                if candidate.type == requirement.type
            ]

            if not matching_modules: 
                raise RequirementValidationError(
                    f"Module '{module.key}' requires a module of type "
                    f"'{requirement.type}', but none was found."
                )
            
            if requirement.unique and len(matching_modules) > 1:
                raise RequirementValidationError(
                    f"Module '{module.key}' requires a unique module of type "
                    f"'{requirement.type}', but {len(matching_modules)} were found."
                )
    
    def validate_variables(self, modules: list[ResolvedModule]) -> None:
        for module in modules:
            self._validate_module_variables(module)
        
    def _validate_module_variables(self, module: ResolvedModule) -> None:
        for name, definition in module.manifest.variables.items():
            if definition.required and name not in module.variables:
                raise VariableValidationError(
                    f"Module '{module.key}' requires variable '{name}', "
                    "but it was not provided and has no default."
                )
            
    def validate_variable_types(self, modules: list[ResolvedModule]) -> None:
        for module in modules: 
            self._validate_module_variable_types(module)
    
    def _validate_module_variable_types(self, module: ResolvedModule) -> None:
        for name, value in module.variables.items():
            definition = module.manifest.variables.get(name)

            if not definition:
                continue  # variable inconnue → on ignore pour l'instant

            expected_type = definition.type

            if not self._check_type(value, expected_type):
                raise VariableTypeValidationError(
                    f"Variable '{name}' in module '{module.key}' "
                    f"must be of type '{expected_type}', got '{type(value).__name__}'."
                )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)

        if expected_type == "int":
            return isinstance(value, int)

        if expected_type == "boolean":
            return isinstance(value, bool)

        if expected_type == "list":
            return isinstance(value, list)

        return True
