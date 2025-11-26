# CLI Administration and Code Organization Improvements

Date: November 26, 2025

## Overview

This update introduces a new administrative CLI command for managing groups and permissions, adds comprehensive test coverage for all admin commands, refactors the admin command module into a cleaner directory structure, and standardizes CLI argument patterns across the application. These changes improve the developer experience, code maintainability, and administrative capabilities of the Adapt server.

## Background

As Adapt has evolved from a simple file server to a full-featured platform with authentication, authorization, and user management, the need for robust administrative tools has grown. The existing CLI provided basic operational commands but lacked comprehensive administrative functionality for managing the permission system that powers Adapt's security model.

Additionally, the codebase had some inconsistencies in CLI argument handling and code organization that could be improved for better maintainability and user experience.

## Changes Made

### 1. New Admin CLI Command: `list-groups`

**Rationale**: Administrators need visibility into the permission system to understand group structures, assigned permissions, and user memberships. This command provides a comprehensive view of the entire authorization hierarchy.

**Implementation**:
- Added `adapt admin list-groups <root>` command that displays all groups with their descriptions
- Shows associated permissions for each group (action on resource format)
- Lists users assigned to each group
- Handles empty states gracefully with appropriate messaging
- Groups are sorted alphabetically for consistent output

**Files Modified**:
- `adapt/commands/admin/list_groups.py` (new)
- `adapt/commands/admin/__init__.py`
- `adapt/cli.py`

### 2. Comprehensive Test Coverage for Admin CLI Commands

**Rationale**: The admin CLI commands are critical for system administration and needed robust testing to ensure reliability. Previously, these commands had no automated tests.

**Implementation**:
- Added `test_run_list_groups_empty()` - tests command with no groups in database
- Added `test_run_list_groups_with_data()` - tests command with populated groups, permissions, and users
- Added `test_run_list_resources()` - tests resource discovery listing
- Added `test_run_create_permissions()` - tests permission and group creation workflow
- All tests use pytest's `capsys` fixture to capture and verify stdout output
- Tests create realistic test data and verify database state changes

**Files Modified**:
- `tests/test_admin.py`

### 3. Refactored Admin Commands into Directory Structure

**Rationale**: The single `admin.py` file was growing and mixing concerns. Separating each command into its own file improves code organization, makes commands easier to develop independently, and follows the existing pattern used in other command modules.

**Implementation**:
- Created `adapt/commands/admin/` directory structure
- Split `admin.py` into separate command files:
  - `list_resources.py` - resource discovery functionality
  - `create_permissions.py` - permission and group creation logic
  - `list_groups.py` - group listing functionality
- Created `__init__.py` with command dispatcher and imports
- Maintained all existing functionality and interfaces

**Files Modified**:
- `adapt/commands/admin/__init__.py` (new)
- `adapt/commands/admin/list_resources.py` (new)
- `adapt/commands/admin/create_permissions.py` (new)
- `adapt/commands/admin/list_groups.py` (new)
- `adapt/cli.py` (updated imports)
- Removed `adapt/commands/admin.py`

### 4. Standardized CLI Argument Patterns

**Rationale**: Inconsistent argument patterns across CLI commands created confusion for users. Some commands used positional arguments for root directory while others used named `--root` flags. Standardizing on positional arguments improves usability since root is the primary parameter for most commands.

**Implementation**:
- Changed `addsuperuser` from `--root` to positional `root` argument
- Changed `admin create-permissions` from `--root` to positional `root` (now first positional before resources)
- Changed `admin list-groups` from `--root` to positional `root`
- Maintained backward compatibility with optional positional arguments defaulting to "."
- Updated help text and command documentation

**Files Modified**:
- `adapt/cli.py`

## Benefits

- **Enhanced Administration**: Administrators now have complete visibility into the permission system with the new `list-groups` command
- **Improved Reliability**: Comprehensive test coverage ensures admin commands work correctly and prevents regressions
- **Better Code Organization**: Directory-based module structure makes the codebase more maintainable and easier to extend
- **Consistent User Experience**: Standardized CLI argument patterns reduce confusion and improve usability
- **Future-Proof**: Clean separation of concerns makes adding new admin commands straightforward

## Usage Examples

```bash
# List all groups with permissions and users
adapt admin list-groups /path/to/data

# Create permissions for specific resources
adapt admin create-permissions /path/to/data users.csv products.xlsx

# Create permissions for all resources with custom group names
adapt admin create-permissions /path/to/data __all__ --all-group full_access --read-group read_only

# List discovered resources
adapt admin list-resources /path/to/data
```

These improvements make Adapt more powerful for administrators while maintaining the simplicity that makes it easy to use for basic file serving scenarios.