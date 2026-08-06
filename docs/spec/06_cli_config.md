# Adapt Specification: CLI and Configuration

> **Status:** This document describes the current implementation. The running
> code on `main` wins if it differs. See the
> [documentation contract](../documentation-contract.md) and [user manual](../manual/index.md).

## 1. CLI

`adapt serve <root>` starts the server. It accepts `--host`, `--port`,
`--tls-cert`, `--tls-key`, `--reload`, `--readonly`, and `--debug`.

Both TLS file options must be present together. Direct TLS enables secure
cookies. Without both files, `adapt serve` disables secure cookies. A reverse
proxy that terminates TLS does not change this calculation.

The `--reload` option gives Uvicorn an importable application factory. Uvicorn
watches Python files in the document root and restarts Adapt after a change.

Operational commands include:

* `adapt check <root>` loads the configuration and initializes
  `.adapt/adapt.db`. It discovers and counts resources. It emits TLS and
  top-level route-collision warnings.
* `adapt addsuperuser <root> --username <name>` creates a superuser or reports
  an existing user. It supports noninteractive password options.
* `adapt list-endpoints <root>` builds the configured plugin routers and prints
  the resource paths they mount. It includes plugin-defined subresources and
  both supported namespace forms. It omits files that mount no routes.
* `adapt reindex <root> [--force]` rebuilds the full-text search index. The
  option also indexes resources whose file metadata is unchanged.

Administrative commands list, create, and delete users or groups. The
`change-password` command replaces a user password and revokes all browser
sessions for that user. Administrative commands can add users to groups or
remove them. They can also list resources and create the standard resource
permissions and groups.

`adapt admin create-permissions <root> <resources>...` accepts `__all__` for all
resources. The `--all-group` and `--read-group` values are prefixes. The
command adds a sorted resource suffix to each combined group name.

Run `adapt --help` and `adapt admin --help` for the current command list.

## 2. Configuration

Adapt creates `DOCROOT/.adapt/conf.json` with defaults when the file is absent.
Configuration precedence is CLI arguments, environment variables,
`conf.json`, then defaults.

`conf.json` accepts these keys:

* `plugin_registry`
* `host`
* `port`
* `tls_cert`
* `tls_key`
* `secure_cookies`
* `search_on_startup`
* `readonly`
* `debug`
* `mcp_enabled`
* `logging`

Unknown keys, invalid types, invalid ports, and malformed JSON stop the command.

The environment can override `host`, `port`, `readonly`, `debug`, and
`mcp_enabled` through `ADAPT_HOST`, `ADAPT_PORT`, `ADAPT_READONLY`,
`ADAPT_DEBUG`, and `ADAPT_MCP_ENABLED`.

Boolean environment values accept `1`, `true`, `yes`, or `on` for true. They
accept `0`, `false`, `no`, or `off` for false. Case and surrounding spaces do
not affect these values.

The default registry maps these extension groups:

* Datasets: `.csv`, `.xlsx`, `.xls`, `.parquet`
* Handlers and content: `.py`, `.html`, `.md`
* Generic files: `.txt`, `.pdf`, `.json`, `.xml`, `.svg`, `.png`, `.jpg`,
  `.jpeg`, `.gif`, `.webp`
* Media: `.mp4`, `.mp3`, `.avi`, `.mkv`, `.webm`, `.ogg`, `.wav`

The Excel plugin reads `.xlsx` and `.xls` files. Legacy `.xls` resources are
read-only. Discovery ignores extensions that do not have a registry mapping.

## 3. Logging

The default configuration writes JSON logs to standard output at `INFO` level.
The `logging` value accepts a Python `dictConfig` object. Debug mode sets the
root log level to `DEBUG`.
