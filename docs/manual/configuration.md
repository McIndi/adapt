# Configuration

[Previous](security) | [Next](plugin_development) | [Index](index)

This guide documents configuration behavior currently implemented in Adapt.

## Configuration File

Adapt reads configuration from:

- `DOCROOT/.adapt/conf.json`

If the file does not exist, Adapt creates it with defaults on first load.

## Supported Top-Level Keys

Current accepted keys are:

- `plugin_registry`
- `host`
- `port`
- `tls_cert`
- `tls_key`
- `secure_cookies`
- `readonly`
- `debug`
- `logging`

Unknown keys are treated as configuration errors.

## Source Precedence

Effective precedence (later overrides earlier):

1. Built-in defaults
2. `conf.json`
3. Environment variables
4. `adapt serve` CLI arguments

Environment variables currently supported:

- `ADAPT_HOST`
- `ADAPT_PORT`
- `ADAPT_READONLY`
- `ADAPT_DEBUG`

## Example `conf.json`

```json
{
  "host": "127.0.0.1",
  "port": 8000,
  "readonly": false,
  "debug": false,
  "tls_cert": null,
  "tls_key": null,
  "secure_cookies": false,
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".xls": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
    ".py": "adapt.plugins.python_plugin.PythonHandlerPlugin",
    ".html": "adapt.plugins.html_plugin.HtmlPlugin",
    ".txt": "adapt.plugins.html_plugin.HtmlPlugin",
    ".md": "adapt.plugins.markdown_plugin.MarkdownPlugin",
    ".mp4": "adapt.plugins.media_plugin.MediaPlugin",
    ".mp3": "adapt.plugins.media_plugin.MediaPlugin",
    ".avi": "adapt.plugins.media_plugin.MediaPlugin",
    ".mkv": "adapt.plugins.media_plugin.MediaPlugin",
    ".webm": "adapt.plugins.media_plugin.MediaPlugin",
    ".ogg": "adapt.plugins.media_plugin.MediaPlugin",
    ".wav": "adapt.plugins.media_plugin.MediaPlugin"
  },
  "logging": {
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
      "json": {
        "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
      }
    },
    "handlers": {
      "console": {
        "class": "logging.StreamHandler",
        "formatter": "json",
        "stream": "ext://sys.stdout"
      }
    },
    "root": {
      "level": "INFO",
      "handlers": ["console"]
    }
  }
}
```

## Serve-Time CLI Overrides

`adapt serve` supports:

- `--host`
- `--port`
- `--tls-cert`
- `--tls-key`
- `--reload`
- `--readonly`
- `--debug`

TLS note:

- `--tls-cert` and `--tls-key` must be provided together.

## Plugin Registry Notes

`plugin_registry` values must use dotted class paths, for example:

```json
{
  "plugin_registry": {
    ".myext": "my_plugin.plugin.MyPlugin"
  }
}
```

## Validation and Diagnostics

Use `adapt check` to validate config and discovery:

```bash
adapt check /path/to/docroot
```

Typical checks:

- config parse and key validation
- DB initialization
- resource discovery
- TLS path sanity warnings

## Common Configuration Issues

1. Invalid JSON in `conf.json`
2. Unknown top-level key
3. Wrong type for `port`, `readonly`, or `debug`
4. Invalid plugin class path
5. TLS cert/key only partially set

[Previous](security) | [Next](plugin_development) | [Index](index)
