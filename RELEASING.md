# Releasing Adapt

Adapt has separate application and Helm chart releases. Do not use one tag for
both release types.

| Release | Tag | Result |
|---|---|---|
| Application | `v<app-version>` | PyPI package, container image, and documentation |
| Helm chart | `chart-v<chart-version>` | OCI chart in GHCR |

This guide gives the complete Helm chart release procedure.

## Coordinated application and chart release

Publish the Python package and the container image before the chart. The
chart `appVersion` must match an image that already exists.

For `0.5.2`:

1. Confirm `pyproject.toml` and `adapt/__init__.py` report `0.5.2`.
2. Create the GitHub Release with tag `v0.5.2`. That publishes PyPI and
   `ghcr.io/mcindi/adapt-server:0.5.2`.
3. Confirm the image exists for `linux/amd64` and `linux/arm64`.
4. Set chart `version` to `0.5.2-rc.1` and `appVersion` to `"0.5.2"`. Tag
   `chart-v0.5.2-rc.1` and follow the Helm chart release steps below.
5. From a clean machine, pull and install the RC. Include
   `helm install adapt ...` and confirm `/health` returns HTTP 200.
6. Set chart `version` to `0.5.2`. Tag `chart-v0.5.2` and repeat the Helm
   chart release steps.

Do not use one git tag for both the application and the chart.

## Helm chart release

### 1. Select the chart version

Use semantic versioning for `charts/adapt/Chart.yaml` `version`.

Use a release candidate for the first registry test of a new chart release:

```yaml
version: 0.5.2-rc.1
```

Set the same value in your shell. The commands below use this variable:

```bash
ADAPT_CHART_VERSION=0.5.2-rc.1
```

Keep `appVersion` equal to the Adapt image you already published. For the
`0.5.2` chart, `appVersion` is `"0.5.2"`.

### 2. Run the local checks

Run these commands from the repository root:

```bash
helm lint charts/adapt
helm unittest charts/adapt
bash tools/test-helm-schema.sh
```

Package the chart and inspect its metadata:

```bash
mkdir -p /tmp/adapt-chart-release
helm package charts/adapt --destination /tmp/adapt-chart-release
helm show chart "/tmp/adapt-chart-release/adapt-${ADAPT_CHART_VERSION}.tgz"
```

Make sure that the output contains the correct `version`, `appVersion`,
`home`, `sources`, `maintainers`, and `keywords` values.

### 3. Commit the release candidate

Commit the version change. For the first OCI release, also commit the
publishing workflow and this guide before you create the tag.

```bash
git status --short
git diff --check
git add charts/adapt/Chart.yaml
git commit -m "chore(chart): prepare ${ADAPT_CHART_VERSION}"
git push origin main
```

Wait for the normal `main` branch checks to pass.

### 4. Create the chart tag

Create an annotated tag that exactly matches `Chart.yaml`:

```bash
git tag -a "chart-v${ADAPT_CHART_VERSION}" \
  -m "Release chart ${ADAPT_CHART_VERSION}"
git push origin "chart-v${ADAPT_CHART_VERSION}"
```

The tag push starts the `Publish Helm Chart` workflow in
`.github/workflows/publish-chart.yml`.

### 5. Monitor the publishing workflow

Open **GitHub Actions > Publish Helm Chart**. Make sure that these jobs pass:

1. `test` runs the Python test workflow.
2. `helm-ci` runs lint, schema, unit, and kind checks.
3. `package-and-push` checks the tag, packages the chart, and pushes it.

The last job publishes this OCI chart:

```text
oci://ghcr.io/mcindi/charts/adapt
```

The workflow rejects a tag that does not match `Chart.yaml`.
The publishing job cannot start until both test jobs pass.

### 6. Make sure that the package is public

Open the new package in GitHub Packages. Make sure that anonymous users have
read access.

If the package is private, change its visibility to public before the next
step.

### 7. Run the anonymous registry test

Use a machine or VM with no repository checkout. Use a temporary Helm registry
configuration to exclude saved GHCR credentials.

If no test cluster exists, create one:

```bash
kind create cluster --name adapt-release-check --wait 180s
```

Run the registry checks from a clean directory:

```bash
release_check_dir=$(mktemp -d)
cd "$release_check_dir"
export HELM_REGISTRY_CONFIG="$release_check_dir/registry.json"

helm show chart oci://ghcr.io/mcindi/charts/adapt \
  --version "${ADAPT_CHART_VERSION}"

helm install adapt-release-check oci://ghcr.io/mcindi/charts/adapt \
  --version "${ADAPT_CHART_VERSION}" \
  --namespace adapt-release-check \
  --create-namespace \
  --wait \
  --timeout 180s

helm get notes adapt-release-check --namespace adapt-release-check
helm test adapt-release-check --namespace adapt-release-check --logs --timeout 120s
kubectl get pods --namespace adapt-release-check
```

Make sure that the chart metadata is correct. Make sure that the pod is ready
and the Helm test passes.

Remove the test release:

```bash
helm uninstall adapt-release-check --namespace adapt-release-check
kubectl delete namespace adapt-release-check
```

If this procedure created the kind cluster, delete it:

```bash
kind delete cluster --name adapt-release-check
```

### 8. Record the result

Record the workflow URL and registry commands in the applicable release or
milestone log. Do not mark the review gate complete without this evidence.

## Promote a release candidate

If the release candidate passes, change `Chart.yaml` from the release
candidate to the stable version.

For example, change `0.5.2-rc.1` to `0.5.2`. Then repeat all release steps
with the stable version and `chart-v0.5.2` tag. Update the shell variable first:

```bash
ADAPT_CHART_VERSION=0.5.2
```

Do not reuse or move a published tag. If a release candidate is incorrect,
create a new version such as `0.5.2-rc.2`.

## Failure recovery

- If a test job fails, correct the failure and create a new release-candidate
  version.
- If the tag does not match `Chart.yaml`, correct the version and create a new
  tag.
- If GHCR rejects the push, make sure that the workflow has `packages: write`.
- If anonymous access fails, make the GHCR package public.
- If an incorrect chart is already published, increment the chart version.
  Do not replace an OCI chart version after publication.

## Install a released chart

Users install a released chart without cloning the repository:

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt \
  --version "${ADAPT_CHART_VERSION}"
```

The release name `adapt` is valid on chart `0.5.2` and later.

OCI charts do not use `helm repo add`. Chart signing and provenance remain
Phase 3 work in milestone M3.

## Application release summary

Application releases use GitHub Releases, not `chart-v*` tags. Publish a
GitHub Release with a matching `v<app-version>` tag.

That event starts the PyPI, container-image, and documentation workflows. The
application version must match `pyproject.toml` and `adapt/__init__.py`.
