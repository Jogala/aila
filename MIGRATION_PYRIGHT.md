# MyPy to Pyright Migration Plan

## Discovery Summary

### Current MyPy Usage Found

#### Configuration Files
- **pyproject.toml:39** - `mypy = "*"` in dev dependencies
- **pyproject.toml:55** - `.mypy_cache` in ruff exclude list  
- **pyproject.toml:94-173** - Complete `[tool.mypy]` configuration section
- **pyproject.toml:118** - `mypy_path = "."`
- **pyproject.toml:131** - `"^.mypy_cache/"` in exclude patterns
- **pyproject.toml:141-163** - Multiple `[[tool.mypy.overrides]]` sections for third-party libraries
- **pyproject.toml:166** - `plugins = ["pydantic.mypy"]` - **IMPORTANT: Pydantic plugin usage**
- **pyproject.toml:168** - `[tool.pydantic-mypy]` configuration section

#### Development Environment
- **.vscode/extensions.json:6** - `"ms-python.mypy-type-checker"` VS Code extension recommendation

#### Documentation
- **README.md:121** - `mypy aila/` command in development section

#### Code Comments
- **aila/llm_interface.py:53** - `# type: ignore` comment
- **aila/llm_interface.py:60** - `# type: ignore` comment

#### Dependencies
- **poetry.lock** - Multiple entries for mypy (1.17.1) and mypy-extensions (1.1.0)

#### Git/Docker Ignore Files
- **.gitignore:84-87** - MyPy cache ignore patterns
- **.dockerignore:87-90** - MyPy cache ignore patterns

### MyPy Configuration Analysis

The current mypy setup is quite comprehensive:
- **Strict mode enabled** with extensive type checking
- **Pydantic plugin** used for enhanced model validation
- **Multiple third-party library overrides** for missing type stubs
- **Focused on "aila" package** with exclusions for tests/scripts

## Migration Plan

### 1. Pyright Configuration Replacement

**Replace:** `[tool.mypy]` section in pyproject.toml  
**With:** `[tool.pyright]` section using equivalent settings:

```toml
[tool.pyright]
# Equivalent to mypy's strict mode
typeCheckingMode = "strict"
pythonVersion = "3.12"

# Include/exclude patterns (mirroring mypy config)
include = ["aila"]
exclude = [
    "build",
    "dist", 
    ".venv",
    "venv",
    ".mypy_cache",
    "__pycache__",
    "tests",
    "scripts",
    "cache",
    "data", 
    "results"
]

# Pyright-specific settings for equivalent behavior
reportMissingImports = false  # Due to third-party library handling
reportPrivateUsage = false
reportConstantRedefinition = false
reportIncompatibleMethodOverride = true
reportMissingTypeStubs = false  # Due to third-party libraries
reportUnusedImport = true
reportUnusedClass = true
reportUnusedFunction = true
reportUnusedVariable = true
reportDuplicateImport = true
```

### 2. Pydantic Plugin Migration

**Challenge:** Pyright doesn't have a direct equivalent to `pydantic.mypy` plugin.

**Solution:** 
- Remove `plugins = ["pydantic.mypy"]` and `[tool.pydantic-mypy]` sections
- Pyright has built-in understanding of Pydantic v2 models without needing plugins
- The current Pydantic v2 usage should work correctly with Pyright's native support

### 3. Third-Party Library Handling

**Current:** Multiple `[[tool.mypy.overrides]]` for libraries without stubs  
**Replacement:** Pyright's `reportMissingImports = false` handles this globally

**Libraries currently overridden:**
- anthropic.*
- openai.*
- PyPDF2.*
- docx.*
- uvicorn.*
- fastapi.*

### 4. Type Ignore Comments

**Current:** 2 instances of `# type: ignore` (no mypy-specific codes)  
**Action:** Keep as-is - Pyright respects generic `# type: ignore` comments

### 5. Dependencies to Remove

- `mypy = "*"` from `[tool.poetry.group.dev.dependencies]`
- mypy and mypy-extensions from poetry.lock (via dependency removal)

### 6. VS Code Integration

**Replace:** `"ms-python.mypy-type-checker"` extension  
**With:** Pylance (already installed as `"ms-python.vscode-pylance"`)  
**Add:** VS Code settings for Pyright type checking mode

### 7. Documentation Updates

- **README.md:121** - Change `mypy aila/` to `pyright`
- Update development section to reflect new type checking workflow

### 8. Cache and Ignore Patterns

**Update patterns from `.mypy_cache` to `.pyright_cache` in:**
- .gitignore
- .dockerignore  
- pyproject.toml ruff exclude list

## Behavioral Changes Expected

### Advantages
- **Faster type checking** - Pyright is generally faster than mypy
- **Better VS Code integration** - Native Pylance support
- **Modern Python features** - Better support for recent type system features

### Potential Differences
- **Stricter narrowing** - Pyright may be more strict about type narrowing
- **Different error messages** - Error reporting style will change
- **No pydantic plugin** - Relying on built-in Pydantic v2 support instead

### Risk Assessment
- **Low risk** - No runtime behavior changes
- **Type coverage maintained** - Pyright should catch same or more issues
- **Pydantic compatibility** - v2 has good built-in Pyright support

## Implementation Steps

1. Configure Pyright in pyproject.toml
2. Remove mypy from dependencies
3. Update VS Code extensions
4. Update ignore patterns
5. Update documentation
6. Test and validate configuration
7. Create atomic commits

## Validation Criteria

- [ ] `pyright` command runs without configuration errors
- [ ] Type checking coverage maintained or improved
- [ ] All `# type: ignore` comments still respected
- [ ] Pydantic models properly type-checked
- [ ] Development workflow updated successfully