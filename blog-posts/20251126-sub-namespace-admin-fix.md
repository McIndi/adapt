# Sub-namespace Support in Admin Commands

Date: November 26, 2025

## Overview

Fixed a critical bug where administrative commands failed to properly handle sub-namespaces created by plugins like ExcelPlugin. This prevented users from accessing Excel sheets and other multi-resource files even after creating permissions. The fix ensures admin commands work correctly with all resource types, including those with sub-namespaces.

## Background

Adapt's plugin system allows single files to generate multiple resources. For example, the ExcelPlugin creates separate resources for each worksheet in an Excel workbook. Each sheet becomes a distinct API endpoint and UI with its own permissions.

The routing system correctly handles sub-namespaces by constructing URLs like `/api/workbook/People` and `/api/workbook/Products` for different sheets. However, the administrative commands were only aware of base resource names, creating a mismatch between permission creation and permission checking.

## The Problem

When users ran admin commands on files with sub-namespaces:

```bash
# This would only create permissions for "workbook"
$ adapt admin create-permissions /data __all__

# But routes expected permissions for "workbook/People", "workbook/Products"
# Result: Users got 403 Forbidden when accessing Excel sheets
```

The `list-resources` command showed:
```
Discovered resources:
  workbook
```

But the actual accessible resources were:
- `workbook/People`
- `workbook/Products`

## Root Cause Analysis

The issue was in `adapt/admin/resources.py`. The `list_resources` function returned only base paths:

```python
# Before: Only returned base names
return [str(r.relative_path.with_suffix("")) for r in resources]
```

But the routing system in `adapt/routes.py` constructs full namespaces:

```python
namespace = resource.relative_path.with_suffix("").as_posix()
if "sub_namespace" in resource.metadata:
    namespace += f"/{resource.metadata['sub_namespace']}"
```

This created a disconnect: permissions were created for "workbook" but checked for "workbook/Sheet1".

## The Fix

Updated `list_resources` to return the same namespace identifiers used by the routing system:

```python
def list_resources(root: Path) -> List[str]:
    config = AdaptConfig(root=root)
    resources = discover_resources(root, config)
    resource_names = []
    for r in resources:
        namespace = r.relative_path.with_suffix("").as_posix()
        if "sub_namespace" in r.metadata:
            namespace += f"/{r.metadata['sub_namespace']}"
        resource_names.append(namespace)
    return resource_names
```

## Changes Made

### 1. Fixed Resource Discovery for Admin Commands

**Rationale**: Admin commands must work with the same resource identifiers that the routing system uses for permissions.

**Implementation**:
- Modified `list_resources()` to include sub_namespaces in returned resource names
- Ensured consistency between resource discovery and permission management

**Files Modified**:
- `adapt/admin/resources.py`

## Benefits

- **Complete Resource Coverage**: Admin commands now handle all resource types, including Excel sheets, database tables, and other sub-namespaced resources
- **Proper Permission Management**: Users can now successfully create permissions for and access all discovered resources
- **Consistent Behavior**: Resource listing matches actual accessible endpoints
- **Plugin Compatibility**: All existing and future plugins that use sub_namespaces work correctly with admin commands

## Usage Examples

```bash
# Now correctly shows all sub-namespaces
$ adapt admin list-resources /data
Discovered resources:
  workbook/People
  workbook/Products
  data
  reports/summary

# Creates permissions for all resources including sub-namespaces
$ adapt admin create-permissions /data __all__
Created permission read on workbook/People
Created permission write on workbook/People
Created permission read on workbook/Products
Created permission write on workbook/Products
...

# Shows permissions for all resources
$ adapt admin list-groups /data
Group: workbook/People_readonly
  Permissions:
    - read on workbook/People
...
```

## Testing

All existing tests pass, and the fix has been verified with:
- Excel workbooks with multiple sheets
- Files with and without sub-namespaces
- Full permission lifecycle (create, assign, check)

This fix ensures that Adapt's administrative capabilities work seamlessly with its plugin architecture, providing users with complete control over access to all their data resources.