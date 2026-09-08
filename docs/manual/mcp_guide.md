# MCP Interface Guide

This guide explains how to let an agentic tool (Claude Code, Claude Desktop,
or another [MCP](https://modelcontextprotocol.io) client) talk to an Adapt
server. It covers account creation, permission grants, API key creation, and
how to point the client at `/mcp/`.

## What Is the MCP Interface?

Adapt mounts a [Model Context Protocol](https://modelcontextprotocol.io)
server at `/mcp/` on the same FastAPI app that `adapt serve` runs. It exposes
five tools: `list_resources`, `get_schema`, `read_resource`, `write_resource`,
and `search`. These tools wrap the same permission checks and plugin methods
that the REST API and browser UI use.

There is no separate API surface and no separate process to run. If a user
can read or write a resource over `/api/*`, the same user can do it through
MCP.

Authentication is enforced when a tool executes, and also at the HTTP
layer when Keycloak OIDC is configured. MCP uses Adapt's shared
authentication resolver. A tool call can authenticate with a session
cookie, an API key, or a Bearer JWT. API keys remain the simple option
for scripts and CI. OAuth MCP clients should send `Authorization: Bearer`.
A client that sends a session cookie must also handle CSRF on its HTTP POST
requests.

## Prerequisites

- Adapt installed (`pip install adapt-server`) and a docroot with at least
  one resource (see the [Quick Start](quick_start.md)).
- An MCP-capable client. This guide shows examples for the Claude Code CLI
  and a generic JSON configuration that works with most desktop MCP clients.

## Step 1: Create a Superuser and Start the Server

```bash
adapt addsuperuser /path/to/docroot --username admin
adapt serve /path/to/docroot
```

## Step 2: Create Permissions for Your Resources

This generates `<resource>_readonly` and `<resource>_readwrite` groups for
each discovered resource, so you can assign users without hand-building
permission rows:

```bash
adapt admin create-permissions /path/to/docroot __all__
adapt admin list-groups /path/to/docroot
```

If you only want permissions generated for some resources, pass specific
resource namespaces instead of `__all__`. The command also creates combined
groups named `read_resources_<selected-resource-suffix>` and
`all_resources_<selected-resource-suffix>`. The suffix contains all selected
resource names in sorted order, joined with underscores.

## Step 3: Create a User for the Agent and Grant Access

Give the agent its own account. Do not reuse the superuser's account for
this. A separate account keeps audit logs meaningful and lets you revoke
access without other effects.

Successful `write_resource` calls create the same dataset audit records as
REST mutations.

```bash
adapt admin create-user /path/to/docroot --username agent --password <a-strong-password>
adapt admin add-to-group /path/to/docroot --username agent --group <resource>_readonly
```

If the agent must also create, update, or delete rows through
`write_resource`, use the `<resource>_readwrite` group instead, or in
addition. Repeat `add-to-group` for every resource namespace the agent needs.

## Step 4: Create an API Key

Sign in as `agent` at `/auth/login`. Open `/profile`. Create an API key
there. A user does not need superuser involvement to create their own key.

If the MCP client is an OAuth app (Cursor, Claude, VS Code MCP), skip the
API key. Point the client at `{public_url}/mcp`. Adapt returns `401` with
`WWW-Authenticate` and serves RFC 9728 metadata at
`/.well-known/oauth-protected-resource/mcp`. The client then registers with
Keycloak (DCR) and sends a Bearer token whose `aud` is Adapt `public_url`.
JIT provisioning creates the Adapt user from the token. Put that user in the
same Keycloak groups you created in Step 2.

Adapt shows the raw API key only once. Save it somewhere safe. Adapt stores
only its hash on the server.

A superuser can also mint or revoke a key for another user from the admin UI
(`/admin/` → **API Keys** → **Create**, then select the `agent` user). This
is useful to provision an agent's key without sharing its password. It is an
admin convenience, not a requirement.

## Step 5: Verify the MCP Endpoint Is Reachable

```bash
curl -i \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -X POST http://localhost:8000/mcp/ \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

A `200 OK` with a JSON-RPC response body means the server is up.
Initialization does not authenticate the user. Adapt checks the configured
credentials when the client executes a tool.

## Step 6: Point an Agentic Tool at It

### Claude Code (CLI)

```bash
claude mcp add --transport http adapt http://localhost:8000/mcp/ \
  --header "X-API-Key: <key>"
```

### Generic MCP Client Config (Claude Desktop and similar)

Most desktop clients that support remote or HTTP MCP servers accept a
configuration block similar to this. See your client's documentation for the
exact key names.

```json
{
  "mcpServers": {
    "adapt": {
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "X-API-Key": "<key>"
      }
    }
  }
}
```

When you move off `localhost`, use `https://` and a certificate the client
trusts. See [Security](security.md) for TLS setup.

## Step 7: What the Agent Can Do

| Tool | Equivalent REST call | Notes |
|---|---|---|
| `list_resources` | `GET /` (JSON) | Every namespace the agent can read, with its type. |
| `get_schema` | `GET /schema/{resource}/` | Columns and types for a dataset resource. |
| `read_resource` | `GET /api/{resource}/` | Accepts `limit`, `offset`, `sort`, `order`, `filter` for datasets. `sort` is the column name. `order` must be `asc` or `desc`. |
| `write_resource` | `POST`, `PATCH`, or `DELETE /api/{resource}/` | `action` is `"create"`, `"update"`, or `"delete"`. See the [mutation section](api_reference.md#mutations-create-update-delete). |
| `search` | `GET /search` | Full-text search across every resource the agent can read. |

Once the client is connected, ask the agent something like "what data do you
have access to?" It calls `list_resources` on its own. You can also ask
"search for parental leave policy" to exercise `search`.

To read `products` sorted by category ascending, pass MCP tool arguments like:

```json
{
  "resource": "products",
  "sort": "category",
  "order": "asc"
}
```

## Troubleshooting

- **"Authentication required" from every tool call** — the `X-API-Key` or
  `Authorization` header is missing, misspelled, or the client is not
  forwarding custom headers for HTTP MCP servers. Look again at Step 4 and
  Step 6. If OIDC is on and the HTTP request itself returned `401`, check
  that the client fetched `/.well-known/oauth-protected-resource/mcp` and
  that the access token `aud` matches Adapt `public_url`.
- **"Permission denied: read/write on `<namespace>`"** — the agent's user is
  not in a group with that permission. Revisit Step 3 and
  `adapt admin list-groups`.
- **"Unknown resource"** — the namespace does not match what
  `list_resources` reports. Namespaces are the file's relative path without
  its extension (for example, `products`, not `products.csv`), unless a
  `sub_namespace` (Excel sheet name) applies.
- **"Server is in read-only mode"** — the server started with `--readonly`,
  or `conf.json` has `readonly: true`. `write_resource` is disabled for
  everyone, regardless of permissions.
- **No `/mcp/` route at all** — the server has `mcp_enabled: false` in
  `.adapt/conf.json`, or has `ADAPT_MCP_ENABLED=false` set. See
  [Configuration](configuration.md).

Manual navigation: [Previous: Security](security.md) | [Index](index.md) | [Next: Configuration](configuration.md)
