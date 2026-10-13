# Releasing Adapt

Adapt has separate application and Helm chart releases. Do not use one tag for
both release types.

| Release | Tag | Result |
|---|---|---|
| Application | `v<app-version>` | PyPI package, container image, and documentation |
| Helm chart | `chart-v<chart-version>` | OCI chart in GHCR |

This guide gives the complete Helm chart release procedure.

## Dependency refresh

Start every application release by refreshing the pins on a branch from
`dev`:

```bash
uv lock --upgrade
uv sync --locked --extra dev --group docs
uv run python -m pytest tests/ -q
uv run mkdocs build --strict
```

Also bump the pinned uv version, the action SHAs, the Python patch versions,
and the image digests in `.github/workflows/` and `Dockerfile`. CI tests the
lower bounds from `constraints-min.txt` in the `test-min` job. Record every
pin change, old → new, in `CHANGES.md`.

The container image installs the runtime dependencies from a hashed export
of the lock. The `Dockerfile` creates it in a build stage:
`uv export --locked --format requirements-txt --no-dev --no-emit-project`.

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

OCI charts do not use `helm repo add`. After chart `0.5.2`, verify the
signature and SBOM with the commands below before trusting a new chart.

## Application release summary

Application releases use GitHub Releases, not `chart-v*` tags. Publish a
GitHub Release with a matching `v<app-version>` tag.

That event starts the PyPI, container-image, and documentation workflows. The
application version must match `pyproject.toml` and `adapt/__init__.py`.

The PyPI job publishes through Trusted Publishing, writes CycloneDX SBOMs
onto the GitHub Release, and attests those SBOMs. The image job attaches an
SPDX SBOM and SLSA provenance, then signs the image index with Cosign. The
chart job signs the OCI chart and attests a CycloneDX SBOM. `0.5.2` itself
predates those extra artifacts. See `SUPPLY_CHAIN.md`.

## Verify a release

Run these from a clean directory after the publish workflows succeed. Replace
the version. A wrong identity, a missing signature, or a changed file must
exit nonzero.

PyPI distributions. This checks the existing Trusted Publishing attestation.
It does not look for a second signature.

```bash
python -m pip install pypi-attestations
python -m pip download adapt-server==0.5.2 --no-deps --no-binary :all: -d dist
python -m pip download adapt-server==0.5.2 --no-deps --only-binary :all: -d dist
pypi-attestations verify pypi --repository McIndi/adapt dist/*
```

Python SBOMs, from the GitHub Release assets:

```bash
gh release download v0.5.2 --pattern "*.cdx.json" --dir sbom
gh attestation verify sbom/adapt_server-0.5.2.whl.cdx.json --repo McIndi/adapt
gh attestation verify sbom/adapt_server-0.5.2.tar.gz.cdx.json --repo McIndi/adapt
```

The asset names use the version of that release. `0.5.2` has no SBOM assets.
Use the next application release for this check.

Image signature, SBOM, and provenance:

```bash
cosign verify \
  --certificate-identity-regexp '^https://github.com/McIndi/adapt/\.github/workflows/publish-image\.yml@refs/tags/v.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/mcindi/adapt-server:0.5.2

docker buildx imagetools inspect ghcr.io/mcindi/adapt-server:0.5.2
```

`cosign verify` fails on `0.5.2` because that image has provenance and no
Cosign signature. The imagetools listing shows the provenance attestations.
The next image release must pass `cosign verify` and list an SBOM.

Chart signature and SBOM:

```bash
cosign verify \
  --certificate-identity-regexp '^https://github.com/McIndi/adapt/\.github/workflows/publish-chart\.yml@refs/tags/chart-v.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/mcindi/charts/adapt:0.5.2

cosign verify-attestation \
  --type cyclonedx \
  --certificate-identity-regexp '^https://github.com/McIndi/adapt/\.github/workflows/publish-chart\.yml@refs/tags/chart-v.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/mcindi/charts/adapt:0.5.2
```

Both chart commands fail on `0.5.2`. They apply to the next chart release.

Confirm a bad identity fails. This exits nonzero:

```bash
cosign verify \
  --certificate-identity https://github.com/McIndi/adapt/.github/workflows/does-not-exist.yml@refs/tags/v0.5.2 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/mcindi/adapt-server:0.5.2
```

## Quality gates

Pull requests run two extra required jobs in `.github/workflows/test.yml`:

- `lint` runs `ruff check adapt tests`. The rule set is in `pyproject.toml`.
  It covers pyflakes, bugbear, and a few pycodestyle error classes. It does
  not run `ruff format`.
- `coverage` runs the suite once and prints statement coverage plus
  missing lines. The floor is `[tool.coverage.report] fail_under` in
  `pyproject.toml`.

The measured baseline on 2026-10-12 is 81.50% statement coverage
(Python 3.14.6, 356 passed, 1 skipped). `fail_under` is 81, the highest
whole number that baseline meets.

Raise `fail_under` when a change increases coverage. Do not lower it to make
a pull request pass. The other test jobs stay free of coverage so the summary
comes from one job.

A lint syntax error and `--cov-fail-under=100` both exit nonzero. Those
checks were run locally on 2026-10-12 and then removed. The CI jobs use the
real Ruff configuration and `fail_under = 81`.
