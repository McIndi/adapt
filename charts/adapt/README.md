# Adapt Helm Chart

This chart deploys Adapt with a mounted document root at `/data` by default.
Uploads are disabled until you enable them explicitly in the container
environment.

## Quick install

```bash
helm install adapt ./charts/adapt
```

## Persistence

Use `persistence.enabled=true` to keep document content and `.adapt/` state.

```bash
helm install adapt ./charts/adapt \
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
`persistence`, `service`, `ingress`, `env`, and `secretEnv`.