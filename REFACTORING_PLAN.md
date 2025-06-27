# Auth0 User Management Tool - Refactoring Plan

## Overview
This document outlines a comprehensive refactoring plan to improve maintainability, developer experience, and code organization for the Auth0 User Management Tool.

## Current State Analysis
- **Total Python files**: 13 files, 3,607 lines
- **Largest files**: 
  - `user_operations.py` (1,203 lines) - exceeds 50-line guideline by 24x
  - `cleanup_csv.py` (804 lines) - exceeds 50-line guideline by 16x
  - `main.py` (296 lines) - complex operation routing
- **Structure**: Flat file organization with all modules in root
- **Dependencies**: Legacy requirements.txt setup

## Target Architecture

```
deletepy/
├── src/
│   ├── deletepy/
│   │   ├── __init__.py
│   │   ├── cli/                 # Command-line interface
│   │   │   ├── __init__.py
│   │   │   ├── main.py          # Entry point
│   │   │   ├── commands.py      # Command routing
│   │   │   └── validators.py    # Argument validation
│   │   ├── core/                # Core functionality
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # Auth0 authentication
│   │   │   ├── config.py        # Configuration management
│   │   │   └── exceptions.py    # Custom exceptions
│   │   ├── operations/          # Business operations
│   │   │   ├── __init__.py
│   │   │   ├── user_ops.py      # Core user operations
│   │   │   ├── batch_ops.py     # Batch processing
│   │   │   ├── export_ops.py    # Export functionality
│   │   │   └── domain_ops.py    # Domain checking
│   │   ├── utils/               # Utilities
│   │   │   ├── __init__.py
│   │   │   ├── file_utils.py    # File operations
│   │   │   ├── display_utils.py # Progress/output formatting
│   │   │   └── csv_utils.py     # CSV processing
│   │   └── models/              # Data models
│   │       ├── __init__.py
│   │       ├── user.py          # User data models
│   │       └── config.py        # Configuration models
├── tests/                       # Test suite
├── scripts/                     # Development/deployment scripts
├── docs/                        # Documentation
├── pyproject.toml              # Modern Python packaging with dependencies
└── README.md
```

---

## Phase 1: Foundation Setup

### Step 1.1: Create New Directory Structure
**Estimated time**: 30 minutes

```bash
# Create new package structure
mkdir -p src/deletepy/{cli,core,operations,utils,models}
touch src/deletepy/__init__.py
touch src/deletepy/{cli,core,operations,utils,models}/__init__.py

# Create additional directories
mkdir -p {scripts,docs}
```

### Step 1.2: Setup Modern Python Packaging
**Estimated time**: 45 minutes

1. Create `pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "auth0-user-manager"
version = "1.0.0"
description = "Auth0 User Management Tool for bulk operations"
dependencies = [
    "requests>=2.32.0",
    "python-dotenv>=1.1.0",
    "click>=8.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.11.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0",
]

[project.scripts]
auth0-manager = "deletepy.cli.main:main"

[tool.ruff]
line-length = 88
target-version = "py39"

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
```

2. Create development tooling files:
   - `.pre-commit-config.yaml`
   - `Makefile`
   - Update `.gitignore`

### Step 1.3: Move Existing Configuration Files
**Estimated time**: 15 minutes

1. Move `config.py` to `src/deletepy/core/config.py`
2. Move `auth.py` to `src/deletepy/core/auth.py`
3. Update imports in both files

---

## Phase 2: Core Module Refactoring

### Step 2.1: Extract User Operations Core Functions
**Estimated time**: 2 hours

**From `user_operations.py` (1,203 lines) create:**

1. **`src/deletepy/operations/user_ops.py`** (~300 lines)
   - `delete_user()`
   - `block_user()`
   - `get_user_details()`
   - `get_user_email()`
   - `get_user_id_from_email()`

2. **`src/deletepy/operations/batch_ops.py`** (~400 lines)
   - `revoke_user_grants()`
   - `revoke_user_sessions()`
   - `check_unblocked_users()`
   - Batch processing utilities

3. **`src/deletepy/operations/export_ops.py`** (~300 lines)
   - `export_users_last_login_to_csv()`
   - `find_users_by_social_media_ids()`
   - Export-related functions

4. **`src/deletepy/operations/domain_ops.py`** (~200 lines)
   - Move domain checking logic from `email_domain_checker.py`
   - Domain validation functions

### Step 2.2: Extract CSV Processing Utilities
**Estimated time**: 1.5 hours

**From `cleanup_csv.py` (804 lines) create:**

1. **`src/deletepy/utils/csv_utils.py`** (~400 lines)
   - Core CSV processing functions
   - Column detection and validation
   - Data cleaning utilities

2. **`src/deletepy/utils/file_utils.py`** (~200 lines)
   - File reading/writing operations
   - Backup and restore functions
   - File validation

3. **`src/deletepy/cli/csv_commands.py`** (~200 lines)
   - CSV-specific CLI commands
   - User interaction for CSV processing

### Step 2.3: Extract Utilities
**Estimated time**: 1 hour

**From `utils.py` (506 lines) create:**

1. **`src/deletepy/utils/file_utils.py`** (merge with existing)
   - File reading generators
   - Path validation

2. **`src/deletepy/utils/display_utils.py`** (~200 lines)
   - Progress display functions
   - Color output utilities
   - User interaction helpers

3. **`src/deletepy/cli/validators.py`** (~100 lines)
   - Argument validation functions
   - Auth0 ID validation

---

## Phase 3: CLI Modernization

### Step 3.1: Implement Click-based CLI
**Estimated time**: 2 hours

1. **`src/deletepy/cli/main.py`** - New entry point with Click
2. **`src/deletepy/cli/commands.py`** - Command handlers extracted from current `main.py`
3. Replace argument parsing with Click decorators
4. Implement command groups for better organization

### Step 3.2: Create Operation Handlers
**Estimated time**: 1.5 hours

Extract operation logic from `main.py` into dedicated handler classes:

```python
# src/deletepy/cli/commands.py
class OperationHandler:
    def handle_doctor(self, args): ...
    def handle_check_unblocked(self, args): ...
    def handle_check_domains(self, args): ...
    def handle_export_last_login(self, args): ...
    def handle_find_social_ids(self, args): ...
    def handle_user_operations(self, args): ...
```

---

## Phase 4: Data Models and Type Safety

### Step 4.1: Create Data Models
**Estimated time**: 1 hour

1. **`src/deletepy/models/user.py`**:
```python
@dataclass
class User:
    user_id: str
    email: Optional[str] = None
    connection: Optional[str] = None
    identities: List[Dict] = field(default_factory=list)
    blocked: bool = False
    last_login: Optional[datetime] = None
```

2. **`src/deletepy/models/config.py`**:
```python
@dataclass
class Auth0Config:
    domain: str
    client_id: str
    client_secret: str
    environment: str
```

### Step 4.2: Add Type Hints
**Estimated time**: 2 hours

1. Add comprehensive type hints to all functions
2. Create Protocol interfaces for better abstraction
3. Configure mypy for strict type checking

---

## Phase 5: Exception Handling and Logging

### Step 5.1: Custom Exception Hierarchy
**Estimated time**: 45 minutes

Create `src/deletepy/core/exceptions.py`:
```python
class Auth0ManagerError(Exception):
    """Base exception for Auth0 Manager"""

class AuthConfigError(Auth0ManagerError):
    """Authentication configuration errors"""

class UserOperationError(Auth0ManagerError):
    """User operation errors"""

class FileOperationError(Auth0ManagerError):
    """File operation errors"""
```

### Step 5.2: Structured Logging
**Estimated time**: 1 hour

1. Replace print statements with proper logging
2. Add configurable log levels
3. Implement structured logging for better debugging

---

## Phase 6: Testing and Documentation

### Step 6.1: Update Test Suite
**Estimated time**: 3 hours

1. Update all existing tests for new module structure
2. Maintain 100% test coverage
3. Add integration tests for new CLI structure
4. Update `conftest.py` for new package layout

### Step 6.2: Update Documentation
**Estimated time**: 1 hour

1. Update `CLAUDE.md` with new structure
2. Update README.md with new installation/usage instructions
3. Add docstrings to all public functions
4. Create API documentation

---

## Phase 7: Migration and Cleanup

### Step 7.1: Update Import Statements
**Estimated time**: 1 hour

1. Update all import statements throughout the codebase
2. Add `__init__.py` exports for clean public API
3. Test all functionality with new imports

### Step 7.2: Backward Compatibility
**Estimated time**: 30 minutes

1. Keep old entry point working temporarily
2. Add deprecation warnings
3. Create migration guide

### Step 7.3: Cleanup
**Estimated time**: 30 minutes

1. Remove old files after confirming everything works
2. Update CI/CD if applicable
3. Clean up any temporary files

---

## Implementation Timeline

| Phase | Estimated Time | Dependencies |
|-------|---------------|--------------|
| Phase 1: Foundation Setup | 1.5 hours | None |
| Phase 2: Core Module Refactoring | 4.5 hours | Phase 1 |
| Phase 3: CLI Modernization | 3.5 hours | Phase 2 |
| Phase 4: Data Models and Type Safety | 3 hours | Phase 2 |
| Phase 5: Exception Handling and Logging | 1.75 hours | Phase 2 |
| Phase 6: Testing and Documentation | 4 hours | Phase 2-5 |
| Phase 7: Migration and Cleanup | 2 hours | All previous |

**Total Estimated Time**: ~20 hours

## Benefits After Refactoring

### Maintainability
- ✅ Files under 50 lines (following project guidelines)
- ✅ Single responsibility principle
- ✅ Clear separation of concerns
- ✅ Easier to locate and modify specific functionality

### Developer Experience
- ✅ Modern Python packaging with `pyproject.toml`
- ✅ Type safety with comprehensive type hints
- ✅ Better CLI with Click framework
- ✅ Automated code quality with pre-commit hooks
- ✅ Clear project structure

### Testing and Quality
- ✅ Isolated components easier to unit test
- ✅ Better error handling and logging
- ✅ Consistent code style and formatting
- ✅ Automated quality checks

### Performance
- ✅ Lazy loading reduces startup time
- ✅ Modular imports only load needed components
- ✅ Better memory management with focused modules

## Risk Mitigation

1. **Extensive Testing**: Run full test suite after each phase
2. **Incremental Migration**: Keep old code until new code is verified
3. **Backup Strategy**: Git branches for each phase
4. **Documentation**: Update docs immediately with changes
5. **Rollback Plan**: Clear rollback procedure for each phase

## Success Criteria

- [ ] All existing functionality preserved
- [ ] Test coverage maintained at 100%
- [ ] All files under 50 lines
- [ ] Type checking passes with mypy
- [ ] Code quality checks pass with ruff
- [ ] CLI remains backward compatible (with deprecation warnings)
- [ ] Documentation updated and accurate
- [ ] Performance maintained or improved