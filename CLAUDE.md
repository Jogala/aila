# Python Coding Standards

## Type Annotations
- Use modern Python type hints (3.9+ syntax)
- Use built-in collection types: `list`, `dict`, `set`, `tuple`
- Use union operator `|` instead of `Union` from typing
- Example: `def func() -> list[str] | None:` not `def func() -> Optional[List[str]]:`
- Always add type hints to function parameters and return types
- Add type hints to variable assignments where type isn't obvious