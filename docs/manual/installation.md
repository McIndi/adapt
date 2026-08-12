# Installation

## System Requirements

- Python 3.11 or higher
- `pip`
- SQLite (bundled with Python)

## Install from PyPI

```bash
pip install adapt-server

# With development dependencies:
pip install adapt-server[dev]
```

## Install from Source

```bash
git clone https://github.com/McIndi/adapt.git
cd adapt
pip install -e .
```

The source checkout can contain changes that are newer than the published
`adapt-server` release on PyPI. If you compare behavior with this documentation,
identify which source or package version you use.
See [Known Limitations](known_limitations.md#package-versions).

## First Run

```bash
mkdir my-adapt-server
cd my-adapt-server
# Add some files here, e.g. data.csv, readme.md, etc.
adapt addsuperuser . --username admin
adapt serve .
```

Open `http://localhost:8000`.

## Core CLI Commands

```bash
adapt serve <directory> [options]
adapt check <directory>
adapt addsuperuser <directory> --username <username>
adapt list-endpoints <directory>
adapt reindex <directory> [--force]
```

## Admin CLI Commands

```bash
adapt admin list-resources <directory>
adapt admin create-permissions <directory> <resource>...
adapt admin list-groups <directory>
adapt admin list-users <directory>
adapt admin create-user <directory> --username <username> [--password <password>] [--superuser]
adapt admin change-password <directory> --username <username> [--password <password>]
adapt admin delete-user <directory> --username <username>
adapt admin create-group <directory> --name <group>
adapt admin delete-group <directory> --name <group>
adapt admin add-to-group <directory> --username <username> --group <group>
adapt admin remove-from-group <directory> --username <username> --group <group>
```

## `serve` Options

```bash
adapt serve <directory> [OPTIONS]

Options:
  --host TEXT        Host to bind to
  --port INTEGER     Port to bind to
  --tls-cert PATH    Path to TLS certificate file
  --tls-key PATH     Path to TLS private key file
  --reload           Restart after Python file changes in the document root
  --readonly         Start server in read-only mode
  --debug            Enable debug logging
```

Notes:

- You must provide `--tls-cert` and `--tls-key` together.
- `--readonly` blocks write operations.
- `--reload` watches Python files in the document root. Uvicorn restarts Adapt
  after a change.
- `adapt serve` sets `secure_cookies` from its direct TLS configuration. It
  sets the value to `true` only when you configure both TLS files. This
  overrides the value in `conf.json`.

## Other Core Command Options

Create a superuser with an interactive password prompt:

```bash
adapt addsuperuser <directory> --username <username>
```

For non-interactive use, provide `--password` and `--password-confirm`.
The `--allow-weak-password` flag bypasses the weak-password safety prompt.

Rebuild the full-text search index:

```bash
adapt reindex <directory> [--force]
```

The `--force` flag indexes resources even if their file metadata is unchanged.

`adapt list-endpoints <directory>` builds the configured plugin routers and
prints the resource paths they mount. The output includes
sub-resources such as Excel sheets and both extensionless and with-extension
resource namespaces. The command does not list files that do not mount routes.

## Configuration File

Adapt uses `DOCROOT/.adapt/conf.json`. Adapt creates it automatically on first run.

Supported top-level keys:

- `plugin_registry`
- `host`
- `port`
- `tls_cert`
- `tls_key`
- `secure_cookies`
- `search_on_startup`
- `readonly`
- `debug`
- `mcp_enabled`
- `upload`
- `logging`

Environment overrides:

- `ADAPT_HOST`
- `ADAPT_PORT`
- `ADAPT_READONLY`
- `ADAPT_DEBUG`
- `ADAPT_MCP_ENABLED`
- `ADAPT_UPLOAD_ENABLED`
- `ADAPT_UPLOAD_MAX_SIZE_BYTES`
- `ADAPT_UPLOAD_ALLOWED_EXTENSIONS`
- `ADAPT_UPLOAD_DENIED_EXTENSIONS`
- `ADAPT_UPLOAD_STRICT_MIME_SNIFFING`
- `ADAPT_UPLOAD_ALLOWED_MIME_TYPES`
- `ADAPT_UPLOAD_COLLISION_POLICY`

`ADAPT_PORT` accepts an integer from 1 through 65535. The Boolean
variables accept `1`, `true`, `yes`, or `on` for true. They accept `0`,
`false`, `no`, or `off` for false. Boolean values are case-insensitive and can
have surrounding spaces.

Upload-specific variables:

- `ADAPT_UPLOAD_ENABLED` uses the same Boolean parsing as other `ADAPT_*` flags.
- `ADAPT_UPLOAD_MAX_SIZE_BYTES` must be a positive integer.
- `ADAPT_UPLOAD_ALLOWED_EXTENSIONS` and `ADAPT_UPLOAD_DENIED_EXTENSIONS` use
  comma-separated extension values such as `.txt,.md`.
- `ADAPT_UPLOAD_STRICT_MIME_SNIFFING` enables MIME-sniff validation.
- `ADAPT_UPLOAD_ALLOWED_MIME_TYPES` uses comma-separated MIME values such as
  `text/plain,application/json`.
- `ADAPT_UPLOAD_COLLISION_POLICY` accepts `overwrite` (default) or `reject`.

Effective precedence for serve behavior:

1. Defaults
2. `conf.json`
3. Environment variables
4. `adapt serve` CLI arguments

## Recommended Upload Constraints

For production systems, keep uploads disabled, unless you need file ingestion
from a browser or an API. When you enable uploads, set explicit limits and an
extension policy.

Example `DOCROOT/.adapt/conf.json` snippet:

```json
{
  "upload": {
    "enabled": true,
    "max_size_bytes": 10485760,
    "allowed_extensions": [".csv", ".xlsx", ".md", ".txt"],
    "denied_extensions": [".exe", ".dll", ".bat", ".ps1"],
    "strict_mime_sniffing": true,
    "allowed_mime_types": ["text/plain", "text/markdown", "application/json"],
    "collision_policy": "overwrite"
  }
}
```

Operational guidance:

- Prefer a restrictive `allowed_extensions` list over a broad denylist.
- Set `max_size_bytes` based on expected file sizes and storage budget.
- Keep `readonly=true` for maintenance windows to block all uploads.
- Monitor upload audit actions (`upload_success`, `upload_denied`,
  `upload_failed`) from `/admin/audit-logs`.

Granting upload access to non-superusers:

- In the admin UI permission form, leave the `Resource` field blank (or enter
  `__root__`) and set `Action` to `write`.
- Through the admin API, create a permission with `resource` set to `""`,
  `"__root__"`, or `"<root>"` and assign it to a group.

## TLS Setup

```bash
adapt serve . --tls-cert /path/to/cert.pem --tls-key /path/to/key.pem
```

## Created Directory Structure

Adapt creates a `.adapt/` directory in the docroot:

```text
your-data-directory/
├── data.csv
└── .adapt/
    ├── conf.json
    ├── adapt.db
    ├── data.schema.json
    └── data.index.html
```

## Verify Installation

```bash
adapt check .
```

This command creates or uses `.adapt/adapt.db` and initializes its storage.
It loads the configuration, discovers resources, and prints the resource
count. It also reports TLS file problems and top-level route collisions.
It does not migrate resource schemas or print each discovered resource.

Manual navigation: [Previous: Overview](overview.md) | [Index](index.md) | [Next: Quick Start](quick_start.md)

## Helm (Kubernetes)

The Adapt Helm chart is at `charts/adapt/` in the repository.

### Persistence modes

By default, `/data` uses `emptyDir`. The pod loses its data when it restarts.
Enable persistence to keep document content and `.adapt/` state across restarts
and rescheduling.

**Ephemeral (default):**

```bash
helm install adapt ./charts/adapt
```

**Dynamic PVC — cluster provisions the volume automatically:**

```bash
helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set persistence.size=20Gi \
  --set persistence.storageClass=standard
```

The chart creates a `PersistentVolumeClaim` named `<release>-adapt`. If the
release name contains `adapt`, the claim name is `<release>`.
If `storageClass` is empty, the cluster uses its default StorageClass.

**Existing PVC — cluster admin creates the volume beforehand:**

```bash
helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set persistence.existingClaim=my-adapt-pvc
```

The chart does not create a `PersistentVolumeClaim` object in this mode.

### Persistence values reference

| Value | Default | Description |
|---|---|---|
| `persistence.enabled` | `false` | Enable durable storage |
| `persistence.existingClaim` | `""` | Name of a pre-created PVC to mount |
| `persistence.storageClass` | `""` | StorageClass name. Uses the cluster default if empty |
| `persistence.accessModes` | `[ReadWriteOnce]` | PVC access modes |
| `persistence.size` | `10Gi` | Storage request size |
| `persistence.mountPath` | `""` (uses `adapt.rootPath`) | Mount path inside the container |
| `persistence.annotations` | `{}` | Extra annotations on the PVC |

### Upload settings

Uploads are off by default. When you want file ingestion from a browser or an
API, enable uploads with environment configuration values in the chart.

Example `values.yaml` fragment:

```yaml
env:
  - name: ADAPT_UPLOAD_ENABLED
    value: "true"
  - name: ADAPT_UPLOAD_MAX_SIZE_BYTES
    value: "10485760"
  - name: ADAPT_UPLOAD_ALLOWED_EXTENSIONS
    value: ".csv,.md,.txt"
  - name: ADAPT_UPLOAD_STRICT_MIME_SNIFFING
    value: "true"
```

When you enable uploads, authenticated users with `write` permission on the
document-root boundary see the upload card on `/`. These users can upload
directly from the landing page. The same users can also call
`POST /api/uploads` with API credentials.

### Admin prerequisites

- Before you use dynamic mode, provide a StorageClass with enough quota.
- For `ReadWriteOnce` volumes, keep `replicaCount=1` (the chart default).
  When the storage driver supports concurrent writers, use an `RWX`-capable
  StorageClass and increase `replicaCount`.
- Adapt reads and writes `.adapt/adapt.db` (SQLite). Two pods that share an
  `RWO` volume cause write conflicts. `RWX` block volumes can cause
  corruption. Network filesystems (NFS, CephFS, Azure Files) with correct
  locking are the supported multi-replica path.

### Bootstrapping a superuser

By default, a fresh install has no users. Create a superuser manually with:

```bash
kubectl exec -it deploy/<release>-adapt -- \
  adapt addsuperuser /data --username admin
```

If the release name contains `adapt`, use `deploy/<release>` instead.
The `-it` flag is required because `addsuperuser` prompts for the password.
For scripts, use `--password`, `--password-confirm`, and
`--allow-weak-password` as applicable.

Set `bootstrapAdmin.enabled=true` to run that same command automatically.
A `post-install,post-upgrade` Helm hook Job runs the command and gets
credentials from a Kubernetes Secret. This replaces the manual step:

```bash
helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set bootstrapAdmin.enabled=true \
  --set bootstrapAdmin.username=admin
```

**Requires `persistence.enabled=true`.** The bootstrap Job runs in its own
pod. It can share the account database with the main deployment only through
a PVC. If you use `emptyDir` (the default), the two pods get independent,
disconnected volumes, and the created user is invisible to the running
server. The chart does not silently skip this configuration: if you set
`bootstrapAdmin.enabled=true` without persistence, `helm install` and
`helm template` fail.

If you leave `bootstrapAdmin.existingSecret` unset, the chart generates a
Secret named `<release>-adapt-bootstrap-admin` with a random password on the
first install. If the release name contains `adapt`, the name becomes
`<release>-bootstrap-admin`. Run `helm get notes <release>` to get the correct
command. On every later `helm upgrade`, the chart reuses the same Secret value.
It does not generate a new password, so the Secret always matches the password
in the created account. Retrieve it with:

```bash
kubectl get secret <release>-adapt-bootstrap-admin -o jsonpath='{.data.password}' | base64 -d && echo
```

To supply your own credentials, for example from a secrets manager, create a
Secret with `username` and `password` keys. Point
`bootstrapAdmin.existingSecret` at it. Use `existingSecretUsernameKey` and
`existingSecretPasswordKey` to use different key names.

Caveat: If you run `helm uninstall` and reinstall against the same retained
PVC, the admin account from the first install still exists with its original
password. The command `addsuperuser` does nothing for a username that
already exists, so a newly generated Secret value does not apply. If you need
that guarantee across reinstalls, use `bootstrapAdmin.existingSecret` with a
known password. You can also reset the password with
`adapt admin change-password`.

### Exposing the service

`service.type` defaults to `ClusterIP`. Reach it with `kubectl port-forward`
or your own Ingress. For a directly-reachable address without an Ingress
controller, for example on bare-metal or single-node clusters like k3s, set
it to `NodePort`. You can also pin the port so it stays stable across
reinstalls:

```bash
helm install adapt ./charts/adapt \
  --set service.type=NodePort \
  --set service.nodePort=30080
```

Kubernetes applies `service.nodePort` only when `service.type` is `NodePort`
or `LoadBalancer`. Leave it blank to let Kubernetes assign one from its
30000-32767 range.

### Local development overlay

`charts/adapt/values-dev.yaml` bundles persistence, `bootstrapAdmin`, and a
pinned `NodePort` (`30080`) together. Use it to start a durable,
directly-browsable instance for local VM or k3s development, instead of
setting the individual flags above:

```bash
helm upgrade --install adapt ./charts/adapt -f charts/adapt/values-dev.yaml \
  --set image.repository=<your-local-image> --set image.tag=<tag>
```

The overlay uses the `local-path` StorageClass from k3s. For kind or minikube,
add `--set persistence.storageClass=standard`. For Docker Desktop, use
`--set persistence.storageClass=hostpath`. For other clusters, set the value
to an available StorageClass.

