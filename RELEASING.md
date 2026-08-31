# Releasing Adapt

Adapt has independent application and Helm chart releases. Application release
tags use `v<version>` and publish the Python package and container image.
Helm chart release tags use `chart-v<chart-version>` and publish only the
chart to GHCR.

## Release a Helm chart

1. Update `charts/adapt/Chart.yaml` `version` using semantic versioning. Do
   not change `appVersion` unless the chart is intentionally moving to a new
   Adapt application release.
2. Run the chart checks:

   ```bash
   helm lint charts/adapt
   helm unittest charts/adapt
   bash tools/test-helm-schema.sh
   ```

3. Commit the chart change, then create and push a matching annotated tag:

   ```bash
   git tag -a chart-v<chart-version> -m "Release chart <chart-version>"
   git push origin chart-v<chart-version>
   ```

The `Publish Helm Chart` workflow runs the Python test workflow and the full
Helm CI workflow before it packages and pushes the chart to
`oci://ghcr.io/mcindi/charts/adapt`. It rejects a tag whose version differs
from `Chart.yaml`.

## Consume a Helm chart

Install a released chart without cloning this repository:

```bash
helm install adapt oci://ghcr.io/mcindi/charts/adapt --version <chart-version>
```

OCI charts do not need `helm repo add`. Chart signing and provenance are
future M2 supply-chain work.