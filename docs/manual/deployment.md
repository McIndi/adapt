# Deployment

Adapt runs directly on a host with `pip install adapt-server` (see
[Installation](installation.md)), or as a packaged workload:

- **[Container](container.md)** — a published Docker/Podman image
  (`ghcr.io/mcindi/adapt-server`), for a single host or any container
  runtime.
- **[Kubernetes (Helm)](kubernetes.md)** — a published Helm chart
  (`oci://ghcr.io/mcindi/charts/adapt`), for a cluster with persistence,
  service exposure, and an optional automated superuser bootstrap.

Both packaging paths run the same application and read the same `ADAPT_*`
environment variables documented in
[Installation → Configuration File](installation.md#configuration-file).
Choose the container page for a single instance on one host, or the
Kubernetes page to run Adapt as a managed, restartable workload.

Manual navigation: [Previous: Known Limitations](known_limitations.md) | [Index](index.md) | [Next: Container](container.md)
