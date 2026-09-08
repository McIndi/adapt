# Adapt Helm Chart

This chart deploys Adapt with a mounted document root at `/data` by default.
Uploads are disabled until you enable them explicitly in the container
environment.

## Quick install

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2
```

The release name `adapt` is valid. Server and bootstrap pods set
`enableServiceLinks: false`. See
[Kubernetes (Helm)](https://www.mcindi.com/adapt/manual/kubernetes/#install)
for resource naming when the release name contains `adapt`.

## Persistence

Use `persistence.enabled=true` to keep document content and `.adapt/` state.

```bash
helm install myadapt ./charts/adapt \
  --set persistence.enabled=true \
  --set persistence.size=20Gi
```

## Enable uploads

Pass the upload settings through `env` values. The chart exposes them as plain
environment variables on the Adapt container.

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

With uploads enabled, authenticated users who have `write` permission on the
document-root boundary see an upload card on `/` and can also call
`POST /api/uploads` directly.

## Other values

See [`values.yaml`](values.yaml) for the full chart surface, including
`persistence`, `service`, `ingress`, `image`, `imagePullSecrets`, `env`,
`secretEnv`, `oidc`, and `image.digest`. Set `image.digest` to a
`sha256:...` value and leave `image.tag` empty to pin by digest.

## Keycloak OIDC

Set `oidc.issuer` and `oidc.clientId` to wire `ADAPT_OIDC_*` on the
container. Store the confidential client secret in `oidc.existingSecret`
(key `client-secret` by default) or in `secretEnv` as
`ADAPT_OIDC_CLIENT_SECRET`.

```yaml
oidc:
  issuer: https://keycloak.example.com/realms/prod
  clientId: adapt-web
  publicUrl: https://adapt.example.com
  existingSecret: adapt-oidc
```

See the [security manual](https://www.mcindi.com/adapt/manual/security/#keycloak-oidc)
for the Keycloak realm checklist.

## Full documentation

This page covers the quick install only. For persistence modes, admin
bootstrapping, service exposure, image/registry overrides, a day-1
walkthrough, and troubleshooting, see
[Kubernetes (Helm)](https://www.mcindi.com/adapt/manual/kubernetes/) in the
full documentation.