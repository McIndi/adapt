# Configuration

[Previous](security) | [Next](plugin_development) | [Index](index)

Adapt is designed to work out of the box with sensible defaults, but offers extensive configuration options for customization. Configuration can be set via command-line arguments, configuration files, or environment variables.

## Configuration Sources

Configuration values are resolved in this order (later sources override earlier ones):

1. **Built-in defaults**
2. **Configuration file** (`DOCROOT/.adapt/conf.json`)
3. **Command-line arguments** (for serve command only)

## Configuration File

The main configuration file is `DOCROOT/.adapt/conf.json`. It's automatically created with defaults if it doesn't exist.

### Basic Configuration

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".xls": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
    ".py": "adapt.plugins.python_plugin.PythonHandlerPlugin",
    ".html": "adapt.plugins.html_plugin.HtmlPlugin",
    ".md": "adapt.plugins.markdown_plugin.MarkdownPlugin",
    ".mp4": "adapt.plugins.media_plugin.MediaPlugin",
    ".mp3": "adapt.plugins.media_plugin.MediaPlugin",
    ".avi": "adapt.plugins.media_plugin.MediaPlugin",
    ".mkv": "adapt.plugins.media_plugin.MediaPlugin",
    ".webm": "adapt.plugins.media_plugin.MediaPlugin",
    ".ogg": "adapt.plugins.media_plugin.MediaPlugin",
    ".wav": "adapt.plugins.media_plugin.MediaPlugin"
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

### TLS Configuration

```json
{
  "tls_cert": "/path/to/certificate.pem",
  "tls_key": "/path/to/private-key.pem",
  "secure_cookies": true
}
```

### Logging Configuration

```json
{
  "logging": {
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
      "default": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      },
      "json": {
        "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
      }
    },
    "handlers": {
      "console": {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "level": "INFO"
      },
      "file": {
        "class": "logging.FileHandler",
        "filename": "adapt.log",
        "formatter": "json",
        "level": "DEBUG"
      }
    },
    "root": {
      "level": "INFO",
      "handlers": ["console", "file"]
    },
    "loggers": {
      "adapt": {
        "level": "DEBUG",
        "handlers": ["file"],
        "propagate": false
      }
    }
  }
}
```

### Plugin Registry

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".xls": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
    ".py": "adapt.plugins.python_plugin.PythonHandlerPlugin",
    ".html": "adapt.plugins.html_plugin.HtmlPlugin",
    ".md": "adapt.plugins.markdown_plugin.MarkdownPlugin",
    ".mp4": "adapt.plugins.media_plugin.MediaPlugin",
    ".mp3": "adapt.plugins.media_plugin.MediaPlugin"
  }
}
```

## Command-Line Options

## Command-Line Options

### Server Options

```bash
adapt serve [OPTIONS] DOCROOT

Options:
  --host TEXT           Host to bind to [default: 127.0.0.1]
  --port INTEGER        Port to bind to [default: 8000]
  --tls-cert PATH       Path to TLS certificate file
  --tls-key PATH        Path to TLS private key file
  --readonly           Start server in read-only mode
  --reload              Enable auto-reload for development
```

### Administrative Commands

```bash
# Initialize and check configuration
adapt check [OPTIONS] DOCROOT

# Create superuser
adapt addsuperuser [OPTIONS] DOCROOT --username USERNAME --password PASSWORD

# List all generated endpoints
adapt list-endpoints [OPTIONS] DOCROOT

# Admin tasks
adapt admin list-resources [OPTIONS] DOCROOT
adapt admin create-permissions [OPTIONS] DOCROOT [RESOURCES]...
adapt admin list-groups [OPTIONS] DOCROOT
```

## Plugin Configuration

### Custom Plugin Registry

Add custom plugins by extending the plugin registry:

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".json": "mycompany.plugins.JsonPlugin",
    ".xml": "mycompany.plugins.XmlPlugin"
  }
}
```

## Configuration Validation

Adapt validates configuration on startup:

```bash
adapt check /path/to/docroot
```

This command:
- Loads and parses configuration
- Validates required settings
- Checks file permissions
- Tests database connectivity
- Lists discovered resources
- Reports any configuration errors

## Configuration Examples

### Minimal Production Configuration

```json
{
  "tls_cert": "/etc/ssl/certs/adapt.pem",
  "tls_key": "/etc/ssl/private/adapt.pem",
  "secure_cookies": true
}
```

### Development Configuration

```json
{
  "logging": {
    "root": {
      "level": "DEBUG"
    }
  }
}
```

## Troubleshooting Configuration

### Common Issues

1. **Configuration not loaded**
   - Check file path and permissions
   - Validate JSON syntax
   - Check for typos in keys

2. **Settings not applied**
   - Use `adapt check` to verify configuration loading
   - Check logs for any error messages

3. **Plugin not registered**
   - Verify class path in plugin_registry
   - Check import errors in logs
   - Ensure plugin is installed

4. **Database connection failed**
   - Verify SQLite database file exists and is writable
   - Check file permissions on `.adapt/adapt.db`

### Debugging Configuration

Enable debug logging to see configuration loading:

```json
{
  "logging": {
    "root": {
      "level": "DEBUG"
    }
  }
}
```

This configuration guide covers the available options for customizing Adapt.

[Previous](security) | [Next](plugin_development) | [Index](index)
