# Admin Guide

This guide covers administration workflows that are currently implemented in Adapt.

## Initial Setup

Create a superuser:

```bash
adapt addsuperuser /path/to/docroot --username admin
```

Create permissions and groups for resources:

```bash
adapt admin create-permissions /path/to/docroot __all__
```

Optional flags control the prefixes of the automatically-created combined
permission groups:

```bash
adapt admin create-permissions /path/to/docroot __all__ \
  --all-group all_resources \
  --read-group read_resources
```

- `--all-group`: prefix for the combined group that receives all read and write permissions (default: `all_resources`)
- `--read-group`: prefix for the combined group that receives read-only permissions (default: `read_resources`)

The command sorts the selected resource names, joins them with underscores,
and adds the result as a suffix. For example, if you select
`products inventory`, the command creates the combined groups
`all_resources_inventory_products` and `read_resources_inventory_products`.
The command also creates the individual groups `products_readonly`,
`products_readwrite`, `inventory_readonly`, and `inventory_readwrite`.

Or target specific resources:

```bash
adapt admin create-permissions /path/to/docroot products inventory
```

## Admin UI

Admin UI route:

- `/admin/`

Requires superuser authentication.

The Users tab includes an Activate or Deactivate button for each other user.
An administrator cannot deactivate the account that is in use.

## Admin API Surface

All admin routes are under `/admin` and require superuser access.

Users:

- `GET /admin/users`
- `POST /admin/users`
- `PUT /admin/users/{user_id}/password`
- `PUT /admin/users/{user_id}/status`
- `DELETE /admin/users/{user_id}`

Send `{"is_active": false}` to deactivate a user. Send
`{"is_active": true}` to activate the user.

Groups:

- `GET /admin/groups`
- `GET /admin/groups/{group_id}`
- `POST /admin/groups`
- `DELETE /admin/groups/{group_id}`
- `POST /admin/groups/{group_id}/users/{user_id}`
- `DELETE /admin/groups/{group_id}/users/{user_id}`

Permissions:

- `GET /admin/permissions`
- `POST /admin/permissions`
- `DELETE /admin/permissions/{perm_id}`
- `GET /admin/groups/{group_id}/permissions`
- `POST /admin/groups/{group_id}/permissions/{perm_id}`
- `DELETE /admin/groups/{group_id}/permissions/{perm_id}`

Locks:

- `GET /admin/locks`
- `DELETE /admin/locks/{lock_id}`
- `POST /admin/locks/clean`

Cache:

- `GET /admin/cache`
- `DELETE /admin/cache`
- `DELETE /admin/cache/{key}` (requires `resource` query parameter)

API keys:

- `GET /admin/api-keys`
- `POST /admin/api-keys`
- `DELETE /admin/api-keys/{key_id}`

Audit:

- `GET /admin/audit-logs`

## Admin CLI

Resource and permission generation:

```bash
adapt admin list-resources /path/to/docroot
adapt admin create-permissions /path/to/docroot __all__
adapt admin list-groups /path/to/docroot
adapt admin list-users /path/to/docroot
```

User management:

```bash
adapt admin create-user /path/to/docroot --username newuser --password secret
adapt admin change-password /path/to/docroot --username newuser
adapt admin deactivate-user /path/to/docroot --username newuser
adapt admin activate-user /path/to/docroot --username newuser
adapt admin delete-user /path/to/docroot --username olduser
```

The password-change command prompts for the new password by default. For
noninteractive use, add `--password` and `--password-confirm`.

The command applies the password-strength check. If a weak password is
required, use `--allow-weak-password`. A successful change revokes all browser
sessions for the user.

Deactivation revokes all browser sessions for the user. The API keys for the
user remain stored, but they cannot authenticate while the user is inactive.

Group management:

```bash
adapt admin create-group /path/to/docroot --name analysts
adapt admin delete-group /path/to/docroot --name analysts
adapt admin add-to-group /path/to/docroot --username newuser --group analysts
adapt admin remove-from-group /path/to/docroot --username newuser --group analysts
```

## Operations and Monitoring

Useful checks:

```bash
adapt check /path/to/docroot
adapt list-endpoints /path/to/docroot
```

`adapt check` loads the configuration, initializes storage, and counts
discovered resources. It also reports TLS and top-level route-collision
warnings.

`adapt list-endpoints` builds the configured plugin routers and prints their
mounted resource paths. It includes sub-resources such as Excel sheets and
omits discovered files whose plugins do not mount a route.

Admin API examples:

```bash
curl -H "X-API-Key: <superuser-key>" http://localhost:8000/admin/users
curl -H "X-API-Key: <superuser-key>" http://localhost:8000/admin/audit-logs
curl -H "X-API-Key: <superuser-key>" http://localhost:8000/admin/locks
```

## Best Practices

- Use group-based permission assignment rather than one-off manual grants.
- Use `create-permissions __all__` after you add new resources.
- Rotate and revoke API keys routinely.
- Use TLS and secure cookies for non-local deployments.

Manual navigation: [Previous: API Reference](api_reference.md) | [Index](index.md) | [Next: Security](security.md)
