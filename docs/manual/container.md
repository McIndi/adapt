# Container

Adapt publishes a container image on every release. This page covers pulling
it, running it against a bind-mounted document root, and the differences
from a local `pip install` covered in [Installation](installation.md).

## Image coordinates and tags

The image is published to GHCR as `ghcr.io/mcindi/adapt-server`:

- `ghcr.io/mcindi/adapt-server:<version>` — pushed on every release, matching
  the `pyproject.toml` version (for example `0.5.2`, the current release)
- `ghcr.io/mcindi/adapt-server:latest` — pushed only for non-prerelease
  releases

Each tag is a multi-arch manifest list covering `linux/amd64` and
`linux/arm64`. Docker and Podman pull the manifest that matches the host
architecture automatically.

```bash
docker pull ghcr.io/mcindi/adapt-server:0.5.2
```

## Running the image

The image runs as a non-root user pinned to UID 1000 / GID 1000, and serves
on port 8000 with the default `CMD`. Bind-mount a document root and publish
the port:

```bash
mkdir -p ./docroot
sudo chown 1000:1000 ./docroot   # required — see below

docker run -d --name adapt \
  -p 8000:8000 \
  -v "$(pwd)/docroot:/data" \
  ghcr.io/mcindi/adapt-server:0.5.2
```

Open `http://localhost:8000`.

### The UID 1000 ownership requirement

The container process runs as UID 1000, not root. A bind-mounted directory
that the container cannot write to (for example one owned by `root:root`, or
by a host user with a different UID) makes Adapt fail immediately, because it
cannot create `.adapt/` in the document root:

```text
PermissionError: [Errno 13] Permission denied: '/data/.adapt'
```

Fix it before starting the container:

```bash
sudo chown 1000:1000 ./docroot
```

If your host user's UID already happens to be 1000 (common on a fresh Linux
desktop or VM install), no `chown` is needed — the directory is already
writable by that UID.

## Creating the first superuser

```bash
docker exec -it adapt adapt addsuperuser /data --username admin
```

The `-it` flags are required because `addsuperuser` prompts for the password
interactively; without a TTY the prompt raises `EOFError`. For scripted or
non-interactive use, pass `--password`, `--password-confirm`, and
`--allow-weak-password` as applicable. Set the password in a shell variable
first — an unquoted `<placeholder>` on the command line is Bash redirection
syntax, not a value to substitute, and breaks the command:

```bash
ADMIN_PASSWORD='choose-your-own-password'

docker exec adapt adapt addsuperuser /data \
  --username admin --password "$ADMIN_PASSWORD" --password-confirm "$ADMIN_PASSWORD"
```

## Environment variables

The container reads the same `ADAPT_*` environment variables as a local
install. Pass them with `-e` (or `--env-file`):

```bash
docker run -d --name adapt \
  -p 8000:8000 \
  -v "$(pwd)/docroot:/data" \
  -e ADAPT_UPLOAD_ENABLED=true \
  -e ADAPT_UPLOAD_MAX_SIZE_BYTES=10485760 \
  ghcr.io/mcindi/adapt-server:0.5.2
```

See [Installation → Configuration File](installation.md#configuration-file)
for the full variable list and value parsing rules.

## Overriding the default command

The image's default `CMD` is:

```bash
adapt serve /data --host 0.0.0.0 --port 8000
```

Append arguments after the image name to run a different command against the
same image, for example to change the port or run a one-off admin command:

```bash
docker run --rm -v "$(pwd)/docroot:/data" ghcr.io/mcindi/adapt-server:0.5.2 \
  adapt serve /data --host 0.0.0.0 --port 9090

docker run --rm ghcr.io/mcindi/adapt-server:0.5.2 adapt --help
```

## Verifying the image

Inspect the OCI labels a plain `docker build` or a pulled release image
carries:

```bash
docker image inspect ghcr.io/mcindi/adapt-server:0.5.2 --format '{{json .Config.Labels}}'
```

This includes `org.opencontainers.image.version`, `.source`, `.revision`,
`.title`, `.description`, and `.licenses`.

Inspect the multi-arch manifest list to confirm both platforms are present:

```bash
docker buildx imagetools inspect ghcr.io/mcindi/adapt-server:0.5.2
```

The image also carries a built-in `HEALTHCHECK` that polls `/health` every
30 seconds. `docker ps` shows the container's health status directly:

```bash
docker ps --filter name=adapt
```

**Future work:** signature verification (cosign/sigstore) and an attached
SBOM are not yet part of the publish pipeline — see Phase 3 and milestone M3 in
[MILESTONES.md](https://github.com/McIndi/adapt/blob/main/MILESTONES.md).

## Kubernetes

Running the same image on Kubernetes, with persistence, service exposure,
and an automated superuser bootstrap, is covered in
[Kubernetes (Helm)](kubernetes.md).

Manual navigation: [Previous: Deployment](deployment.md) | [Index](index.md) | [Next: Kubernetes (Helm)](kubernetes.md)
