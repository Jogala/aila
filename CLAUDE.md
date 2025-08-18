# Coding Guidelines

## Python Coding Standards

### General Guidelines
- Keep it simple stupid (KISS)
- Always use pydantic BaseModel for classes to keep syntax simple
- Make pydantic models immutable as a default practice via:
`model_config = pydantic.ConfigDict(frozen=True)`
- Prefer Functional Programming over Object-Oriented Programming (OOP)
- I like Functional Strategy with an Immutable Configuration Object
- Do not introduce hidden temporal coupling

### Type Annotations
- Use modern Python type hints (3.9+ syntax)
- Use built-in collection types: `list`, `dict`, `set`, `tuple`
- Use union operator `|` instead of `Union` from typing
- Example: `def func() -> list[str] | None:` not `def func() -> Optional[List[str]]:`
- Always add type hints to function parameters and return types
- Add type hints to variable assignments where type isn't obvious


