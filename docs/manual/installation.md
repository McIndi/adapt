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
git clone https://github.com/McInci/adapt.git
cd adapt
pip install -e .
```

The source checkout can contain changes that are newer than the published
`adapt-server` release on PyPI. Identify which source or package version you use
when you compare behavior with this documentation.
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

- `--tls-cert` and `--tls-key` must be provided together.
- `--readonly` blocks write operations.
- `--reload` watches Python files in the document root. Uvicorn restarts Adapt
  after a change.
- `adapt serve` sets `secure_cookies` from its direct TLS configuration. It
  sets the value to `true` only when both TLS files are configured. This
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
prints the resource paths they actually mount. The output includes
sub-resources such as Excel sheets and both extensionless and with-extension
resource namespaces. Files that do not mount routes are not listed.

## Configuration File

Adapt uses `DOCROOT/.adapt/conf.json`. It is created automatically on first run.

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
- `logging`

Environment overrides:

- `ADAPT_HOST`
- `ADAPT_PORT`
- `ADAPT_READONLY`
- `ADAPT_DEBUG`
- `ADAPT_MCP_ENABLED`

`ADAPT_PORT` accepts an integer from 1 through 65535. The three Boolean
variables accept `1`, `true`, `yes`, or `on` for true. They accept `0`,
`false`, `no`, or `off` for false. Boolean values are case-insensitive and can
have surrounding spaces.

Effective precedence for serve behavior:

1. Defaults
2. `conf.json`
3. Environment variables
4. `adapt serve` CLI arguments

## TLS Setup

```bash
adapt serve . --tls-cert /path/to/cert.pem --tls-key /path/to/key.pem
```

## Created Directory Structure

Adapt creates a `.adapt/` directory in docroot:

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

By default, `/data` uses `emptyDir` and data is lost when the pod restarts.
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

The chart creates a `PersistentVolumeClaim` named after the Helm release.
If `storageClass` is empty, the cluster's default StorageClass is used.

**Existing PVC — cluster admin creates the volume beforehand:**

```bash
helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set persistence.existingClaim=my-adapt-pvc
```

No `PersistentVolumeClaim` object is created by the chart in this mode.

### Persistence values reference

| Value | Default | Description |
|---|---|---|
| `persistence.enabled` | `false` | Enable durable storage |
| `persistence.existingClaim` | `""` | Name of a pre-created PVC to mount |
| `persistence.storageClass` | `""` | StorageClass name; cluster default if empty |
| `persistence.accessModes` | `[ReadWriteOnce]` | PVC access modes |
| `persistence.size` | `10Gi` | Storage request size |
| `persistence.mountPath` | `""` (uses `adapt.rootPath`) | Mount path inside the container |
| `persistence.annotations` | `{}` | Extra annotations on the PVC |

### Admin prerequisites

- Provide a StorageClass with sufficient quota before using dynamic mode.
- For `ReadWriteOnce` volumes, keep `replicaCount=1` (the chart default).
  Use an `RWX`-capable StorageClass and increase `replicaCount` only when the
  storage driver supports concurrent writers.
- Adapt reads and writes `.adapt/adapt.db` (SQLite). Two pods sharing an `RWO`
  volume will cause write conflicts; `RWX` block volumes can cause corruption.
  Network filesystems (NFS, CephFS, Azure Files) with correct locking are the
  supported multi-replica path.

