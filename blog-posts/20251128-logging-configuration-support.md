# Logging Configuration Support: Enhancing Adapt's Observability

Hey developers! In this sprint, we've added logging configuration to Adapt's config system, enabling users to customize logging levels, formats, and handlers via `conf.json`. This ensures early logging setup in the CLI for consistent, structured logs across all operations, improving debugging, auditing, and production monitoring. Let's explore what we built, why it matters, and how to leverage it.

## 1. **What We Changed**
Building on the existing config system, we extended support for logging configuration with the following key updates:

- **Config Extension**: Added a `logging` field to `AdaptConfig` as a dict, defaulting to a dictConfig setup with JSON formatting for structured logs.
- **Early CLI Configuration**: Modified `adapt.cli:main()` to load config and apply logging settings immediately after argument parsing, before executing any commands.
- **Validation and Merging**: Updated `load_from_file()` to validate the `logging` dict, include it in auto-created `conf.json`, and merge user overrides.
- **Dependency Addition**: Added `python-json-logger` to dependencies for reliable JSON log formatting.
- **Test Coverage**: Extended `test_config.py` with tests for logging validation, merging, and type checking.
- **Documentation Updates**: Enhanced README.md and docs/spec/06_cli_config.md to describe the new `logging` option and its usage.

The `logging` config uses Python's standard `dictConfig` format, supporting custom levels, formatters (e.g., JSON), and handlers (e.g., console, file).

## 2. **Why This Matters**
Adapt generates extensive logs for discovery, API operations, audit events, and admin actions, but previously lacked user control over logging behavior. This was problematic for production deployments needing specific log levels, formats, or destinations. By integrating logging into the config system:

- **Improves Observability**: Users can set log levels (e.g., DEBUG for development, INFO for production) and formats (e.g., JSON for log aggregation tools).
- **Supports Compliance**: JSON structured logs align with audit requirements, making it easier to parse and analyze security events.
- **Enhances Debugging**: Early configuration ensures logs are available from the start, aiding troubleshooting of startup issues or config problems.
- **Maintains Flexibility**: Like other config options, logging can be customized per deployment without code changes, following zero-config principles.
- **Follows Best Practices**: Uses standard Python logging with dictConfig, ensuring compatibility and extensibility.

This adheres to our coding standards with focused changes, comprehensive tests, and clear documentation.

## 3. **How to Use It**
Adapt auto-creates `DOCROOT/.adapt/conf.json` with logging defaults on first run. The default config enables INFO-level JSON logs to console:

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    // ... other defaults
  },
  "tls_cert": null,
  "tls_key": null,
  "secure_cookies": false,
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

Customize by editing `conf.json`. For example, to enable DEBUG logging and add a file handler:

```json
{
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
      },
      "file": {
        "class": "logging.FileHandler",
        "filename": "adapt.log",
        "formatter": "json"
      }
    },
    "root": {
      "level": "DEBUG",
      "handlers": ["console", "file"]
    }
  }
}
```

Precedence follows the config system: CLI args override defaults, but logging is set early for all commands. Invalid logging configs cause immediate exit with an error.

## 4. **Extending Logging for Plugins**
Plugins can access the logging config via `request.app.state.config.logging` to adjust behavior, such as enabling verbose logging for custom handlers. This keeps logging consistent and configurable.

## 5. **Conclusion**
This logging config support makes Adapt more observable and production-ready, allowing easy customization of logs for different environments. By integrating with the existing config system, we've maintained simplicity while adding powerful control. As always, we've included tests for reliability. Excited to hear your feedback and see how you use it!