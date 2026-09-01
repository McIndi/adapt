# Known Limitations

This page lists important limitations in the running implementation on `main`.
The workarounds apply until the implementation changes.

## File Support

### Legacy Excel Files

Adapt can discover and read each sheet in a legacy `.xls` workbook. The API,
schema, search index, and DataTables UI support these sheets.

Legacy `.xls` sheets are read-only. A `POST`, `PATCH`, or `DELETE` request
returns `405`. Before you modify a legacy sheet through Adapt, convert the
workbook to `.xlsx`. This restriction prevents formula and
workbook-feature loss.

## Dataset Writes

### Write-Level Row Security

`Plugin.filter_for_user()` filters direct dataset reads. The shared search
index does not apply this filter at the row level.

The shared mutation path does not safely enforce row-level security for
writes. Row-level security therefore does not cover all reads and writes.

Do not use this hook as write authorization. If a plugin requires row-level
write authorization, implement and test a custom write path.

Do not index rows that contain data with per-user access restrictions.

## Package Versions

The repository can contain changes that are newer than the published
`adapt-server` package on PyPI. When you compare behavior with this manual,
record the source commit or installed package version.

## Helm Release Name `adapt` Collides With Its Own Config Variable

The Helm chart's `fullname` helper collapses to the bare release name
whenever that name contains `adapt` (`charts/adapt/templates/_helpers.tpl`).
Installing with the release name literally `adapt` (for example
`helm install adapt oci://ghcr.io/mcindi/charts/adapt ...`) therefore names
every chart resource, including the Service, `adapt`. Kubernetes injects
Docker-links-style environment variables into every pod in the namespace,
named after each Service (`<SERVICE>_SERVICE_HOST`, `<SERVICE>_PORT`, and so
on) — for a Service named `adapt`, that includes `ADAPT_PORT`. This collides
with Adapt's own `ADAPT_PORT` configuration variable, whose value from the
Service (`tcp://10.x.x.x:80`) is not an integer. The server fails at startup
with `ADAPT_PORT must be an integer` and the pod crash-loops.

This was confirmed on a real cluster: the pod runs successfully immediately
after `helm install`, then crash-loops once Kubernetes injects the Service's
env vars (usually by the second or third pod restart, once the Service
object exists).

**Workaround:** use any release name that does not resolve to exactly
`adapt` — for example `myadapt`, which still exercises the chart's
name-collapse rule (because it contains `adapt`) without colliding, since
its Service name renders as the distinct prefix `MYADAPT_*`. There is
currently no chart option to disable Kubernetes' service-link env var
injection (`enableServiceLinks: false` on the pod spec would be the
standard fix); this is an open gap, not yet fixed in the chart. See
[Kubernetes (Helm) → Install](kubernetes.md#install) and
[Troubleshooting](troubleshooting.md) for the same warning in context.

## Related Guides

- [Installation](installation.md)
- [API Reference](api_reference.md)
- [Admin Guide](admin_guide.md)
- [Security](security.md)
- [Configuration](configuration.md)
- [Plugin Development](plugin_development.md)
- [Architecture](architecture.md)
- [Troubleshooting](troubleshooting.md)

Manual navigation: [Previous: Troubleshooting](troubleshooting.md) | [Index](index.md) | [Next: Deployment](deployment.md)
