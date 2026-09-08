# Troubleshooting

This guide covers common problems and verified troubleshooting steps for the current Adapt implementation.

## Server Startup Problems

### Port Already in Use

```bash
netstat -ano | findstr :8000
adapt serve . --port 8001
```

### Invalid Configuration

```bash
adapt check .
```

Look at `.adapt/conf.json` for invalid keys or JSON syntax errors.

### TLS Startup Error

If one TLS flag is provided without the other, startup fails.

Use both together:

```bash
adapt serve . --tls-cert /path/to/cert.pem --tls-key /path/to/key.pem
```

## Authentication Problems

### Login Fails

- Make sure that the username exists
- Make sure that the password is correct
- Make sure that the user is active

Useful checks:

```bash
adapt admin list-users .
sqlite3 .adapt/adapt.db "SELECT username, is_active FROM users;"
```

If the user is inactive, activate the user:

```bash
adapt admin activate-user . --username <username>
```

### API Key Returns 401

- Make sure that the header has this format: `X-API-Key: <key>`
- Make sure that the key is active and not expired
- Make sure that the key owner is active

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/auth/me
```

## Authorization Problems (`403`)

- Make sure that the group membership is correct
- Make sure that the resource permission names are correct
- Make sure that you use the correct action, `read` or `write`

Useful checks:

```bash
adapt admin list-groups .
adapt admin list-resources .
```

Generated API, schema, and UI routes require authentication plus the
corresponding resource permission. `create-permissions` creates individual
groups named `<resource>_readonly` and `<resource>_readwrite`. Combined group
names include a suffix made from all selected resources.

### Cookie-Authenticated Mutation Returns `403`

When an unsafe request uses the `adapt_session` cookie, it must also send the
`adapt_csrf` cookie value in the `X-CSRF-Token` header. This rule remains
true if the request also includes an API key. For command-line mutations,
use an API key without a session cookie to avoid CSRF handling.

## Resource Discovery Problems

### Files Not Appearing

- Make sure that the plugin registry contains the file extension.
- Make sure that the selected plugin detects the file.
- Make sure that the file is under docroot.
- Restart the server after you add files.

Supported built-in extensions are:

- Datasets: `.csv`, `.xlsx`, `.xls`, `.parquet`
- Rendered content: `.html`, `.md`
- Python handlers: `.py`
- Generic text and document files served by `FilePlugin`: `.txt`, `.pdf`,
  `.json`, `.xml`, `.svg`
- Generic image files served by `FilePlugin`: `.png`, `.jpg`, `.jpeg`, `.gif`,
  `.webp`
- Streamed media: `.mp4`, `.mp3`, `.avi`, `.mkv`, `.webm`, `.ogg`, `.wav`

Adapt discovers and reads legacy `.xls` files. These resources are read-only.
Convert a legacy workbook to `.xlsx` before you modify it through Adapt.
Unregistered extensions need a plugin mapping before Adapt can discover them.
See [Known Limitations](known_limitations.md#legacy-excel-files).

### Companion Files Missing

Run discovery check:

```bash
adapt check .
```

Companion files are generated under `.adapt/` for supported resource types.

## Dataset Write Problems

### `405 Method Not Allowed`

The server can be in read-only mode. A legacy `.xls` resource is also
read-only.

```bash
adapt serve . --readonly
```

### `409 Conflict`

When another operation holds the resource lock, Adapt returns `409`. Adapt
also returns this response when it exhausts all lock acquisition retries.

Inspect `/admin/locks` and the server log. Then retry the write after the
competing operation finishes.

### Write Payload Rejected

Dataset mutations require action envelope payloads on `/api/<resource>/`.

Example:

```json
{"action":"update","data":{"_row_id":1,"name":"Updated"}}
```

## Admin API Troubleshooting

Use implemented admin routes under `/admin`, for example:

- `/admin/users`
- `/admin/groups`
- `/admin/permissions`
- `/admin/locks`
- `/admin/cache`
- `/admin/api-keys`
- `/admin/audit-logs`

## Plugin Troubleshooting

### Custom Plugin Not Loading

Make sure that the class path format in `plugin_registry` is correct:

```json
{
  "plugin_registry": {
    ".ext": "module.path.ClassName"
  }
}
```

Current loader expects dotted class paths, not `module:path` syntax.

Make sure that the custom plugin `detect(path)` method returns `True` for the
file. When detection rejects the file, Adapt does not call `load(path)`.

### Import Errors

Do a manual test of the import:

```bash
python -c "from module.path import ClassName"
```

## Useful Diagnostic Commands

```bash
adapt check .
adapt list-endpoints .
adapt admin list-resources .
adapt reindex .
```

`adapt check` initializes storage and reports a discovered-resource count. It
also reports TLS file problems and top-level route collisions. It does not
migrate resource schemas or list each resource.

`adapt list-endpoints` builds the configured plugin routers and prints their
mounted resource paths. It includes sub-resources such as Excel sheets. It
does not invent API, schema, or UI paths for files that mount no routes.

`adapt reindex` rebuilds the full-text search index. Add `--force` to index
resources whose file metadata is unchanged.

## When to Collect Logs

When you report an issue, capture these logs:

- startup failure output
- traceback for 500 errors
- request path and response code
- relevant configuration from `.adapt/conf.json`

## Deployment Troubleshooting (Container and Kubernetes)

See [Deployment](deployment.md) for the full container and Helm chart
documentation. This section covers the failures those paths hit most often.

### Pod `CrashLoopBackOff` with `ADAPT_PORT must be an integer`

Older chart versions injected Kubernetes service-link variables. A Helm
release named `adapt` then set `ADAPT_PORT` to a URL, and the server
rejected it. Chart `0.5.2` sets `enableServiceLinks: false` on the server
and bootstrap pods. Upgrade to chart `0.5.2` or later if you still see
this error. See [Kubernetes (Helm) → Install](kubernetes.md#install).

### Pod `CrashLoopBackOff` on a PVC the container cannot write

The container runs as UID 1000. If the mounted PVC is owned `root:root`
(common with drivers that ignore `fsGroup`), Adapt cannot create `.adapt/`
and the pod crash-loops. The chart sets `podSecurityContext.fsGroup: 1000`
by default, which most CSI drivers honor; for the drivers that ignore it,
use `persistence.annotations` (driver-specific) or pre-chown an
`existingClaim` to UID/GID 1000 before mounting it.

### `docker run` bind mount: `Permission denied: '/data/.adapt'`

Same root cause as above, on a plain Docker/Podman bind mount instead of a
PVC. Fix it on the host:

```bash
sudo chown 1000:1000 ./docroot
```

See [Container](container.md#the-uid-1000-ownership-requirement).

### Liveness restarts during startup indexing

A large document root with `search_on_startup` enabled can take longer to
index than the default liveness window, causing Kubernetes to restart the
pod before it finishes starting. The chart's `probes.startup` block exists
for this — increase `probes.startup.failureThreshold` (default allows about
5 minutes) if your document root is large enough to need more.

### Copied files return `404` immediately after `kubectl cp`

Adapt discovers resources once, at process startup — not continuously. A
file copied into a running pod is not reachable until the pod restarts:

```bash
kubectl rollout restart deployment/<release>-adapt
```

See [Kubernetes (Helm) → Getting documents into the document root](kubernetes.md#getting-documents-into-the-document-root).

### `bootstrapAdmin.enabled=true` rejected without persistence

This is intentional: `charts/adapt/templates/admin-bootstrap-job.yaml` fails
the render with `fail()` rather than silently bootstrapping a user into a
throwaway `emptyDir` the main pod cannot see. Set
`persistence.enabled=true` alongside `bootstrapAdmin.enabled=true`.

### Failed bootstrap Job blocks reinstall

Helm retains a failed hook Job for diagnosis instead of cleaning it up
automatically. A retained failed Job (and its pod holding an `RWO` volume)
can block a reinstall or leave the PVC `Terminating`. Delete it first
(substitute your own release name for `myadapt`):

```bash
kubectl delete job myadapt-bootstrap-admin
kubectl get pods -l job-name=myadapt-bootstrap-admin
```

If a pod from that Job is still present, delete it too, to release the
volume — substitute the pod name printed by the command above:

```bash
kubectl delete pod myadapt-bootstrap-admin-abc12
```

### Bootstrap or server Job stuck `ContainerCreating`

An `RWO` volume is bound to whichever node its first mounting pod was
scheduled on. If the bootstrap Job or a rescheduled server pod lands on a
different node, it stays `ContainerCreating` waiting for the volume to
detach and reattach. This is a real multi-node constraint independent of
replica count — see the `RWX`/multi-replica guidance in
[Kubernetes (Helm) → Admin prerequisites](kubernetes.md#admin-prerequisites).

### Empty landing page after a default install

Installing with defaults (`persistence.enabled=false`,
`bootstrapAdmin.enabled=false`) gives you an empty, account-less, ephemeral
instance — there are no documents, no users, and any state is lost on the
next pod restart. `helm get notes <release>` says so explicitly. This is
expected; follow the [day-1 walkthrough](kubernetes.md#day-1-walkthrough)
for a populated, logged-in instance.

Manual navigation: [Previous: Architecture](architecture.md) | [Index](index.md) | [Next: Known Limitations](known_limitations.md)
