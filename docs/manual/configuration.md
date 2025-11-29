# Configuration

[Previous](security) | [Next](plugin_development) | [Index](index)

Adapt is designed to work out of the box with sensible defaults, but offers extensive configuration options for customization. Configuration can be set via command-line arguments, configuration files, or environment variables.

## Configuration Sources

Configuration values are resolved in this order (later sources override earlier ones):

1. **Built-in defaults**
2. **Configuration file** (`DOCROOT/.adapt/conf.json`)
3. **Environment variables**
4. **Command-line arguments**

## Configuration File

The main configuration file is `DOCROOT/.adapt/conf.json`. It's automatically created with defaults if it doesn't exist.

### Basic Configuration

```json
{
  "host": "127.0.0.1",
  "port": 8000,
  "debug": false,
  "log_level": "INFO",
  "docroot": "/path/to/document/root",
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
    ".html": "adapt.plugins.html_plugin.HtmlPlugin",
    ".md": "adapt.plugins.markdown_plugin.MarkdownPlugin",
    ".py": "adapt.plugins.python_plugin.PythonPlugin"
  }
}
```

### Security Configuration

```json
{
  "tls_cert": "/path/to/certificate.pem",
  "tls_key": "/path/to/private-key.pem",
  "secure_cookies": true,
  "session_timeout": 604800,
  "password_iterations": 100000,
  "audit_retention_days": 90,
  "max_login_attempts": 5,
  "lockout_duration": 900
}
```

### Caching Configuration

```json
{
  "cache_enabled": true,
  "cache_ttl": 3600,
  "cache_max_size": 1000,
  "cache_strategy": "lru"
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

## Command-Line Options

### Server Options

```bash
adapt serve [OPTIONS] DOCROOT

Options:
  --host TEXT           Host to bind to [default: 127.0.0.1]
  --port INTEGER        Port to bind to [default: 8000]
  --tls-cert PATH       Path to TLS certificate file
  --tls-key PATH        Path to TLS private key file
  --read-only           Start server in read-only mode
  --admin               Enable admin interface [default: enabled]
  --log-level TEXT      Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  --reload              Enable auto-reload for development
  --workers INTEGER     Number of worker processes
  --threads INTEGER     Number of threads per worker
```

### Administrative Commands

```bash
# Initialize and check configuration
adapt check [OPTIONS] DOCROOT

# Create superuser
adapt addsuperuser [OPTIONS] DOCROOT

# List all generated endpoints
adapt list-endpoints [OPTIONS] DOCROOT

# User management
adapt admin create-user [OPTIONS] DOCROOT --username USERNAME --password PASSWORD
adapt admin delete-user [OPTIONS] DOCROOT --username USERNAME
adapt admin list-users [OPTIONS] DOCROOT

# Group management
adapt admin create-group [OPTIONS] DOCROOT --name GROUP_NAME
adapt admin add-to-group [OPTIONS] DOCROOT --username USERNAME --group GROUP_NAME
adapt admin remove-from-group [OPTIONS] DOCROOT --username USERNAME --group GROUP_NAME
adapt admin list-groups [OPTIONS] DOCROOT

# Permission management
adapt admin create-permission [OPTIONS] DOCROOT --resource RESOURCE --action ACTION
adapt admin grant-permission [OPTIONS] DOCROOT --group GROUP_NAME --permission PERMISSION
adapt admin revoke-permission [OPTIONS] DOCROOT --group GROUP_NAME --permission PERMISSION
adapt admin list-permissions [OPTIONS] DOCROOT

# Resource management
adapt admin list-resources [OPTIONS] DOCROOT
adapt admin create-permissions [OPTIONS] DOCROOT [RESOURCES]...
```

## Environment Variables

Environment variables can override configuration:

```bash
export ADAPT_HOST=0.0.0.0
export ADAPT_PORT=8080
export ADAPT_DEBUG=true
export ADAPT_LOG_LEVEL=DEBUG
export ADAPT_DOCROOT=/var/adapt/data
export ADAPT_TLS_CERT=/etc/ssl/certs/adapt.pem
export ADAPT_TLS_KEY=/etc/ssl/private/adapt.key
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

### Plugin-Specific Configuration

Some plugins support additional configuration:

```json
{
  "plugins": {
    "csv": {
      "encoding": "utf-8",
      "delimiter": ",",
      "quotechar": "\""
    },
    "excel": {
      "engine": "openpyxl",
      "read_only": false
    },
    "parquet": {
      "engine": "pyarrow",
      "use_threads": true
    }
  }
}
```

## Database Configuration

Adapt uses SQLite by default, but can be configured for other databases:

```json
{
  "database": {
    "url": "sqlite:///./adapt.db",
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600
  }
}
```

For PostgreSQL:

```json
{
  "database": {
    "url": "postgresql://user:password@localhost/adapt",
    "pool_size": 10,
    "max_overflow": 20
  }
}
```

## Performance Tuning

### Server Performance

```json
{
  "workers": 4,
  "threads": 2,
  "max_requests": 1000,
  "max_requests_jitter": 50,
  "worker_timeout": 30,
  "keepalive": 10
}
```

### Cache Tuning

```json
{
  "cache": {
    "enabled": true,
    "backend": "memory",
    "ttl": 3600,
    "max_size": 10000,
    "key_prefix": "adapt:",
    "serializer": "json"
  }
}
```

### Connection Limits

```json
{
  "limits": {
    "max_concurrent_requests": 100,
    "max_request_size": "10M",
    "request_timeout": 30,
    "keepalive_timeout": 75
  }
}
```

## Security Configuration

### Authentication Settings

```json
{
  "auth": {
    "session_cookie_name": "adapt_session",
    "session_timeout": 604800,
    "password_min_length": 8,
    "password_require_uppercase": true,
    "password_require_lowercase": true,
    "password_require_numbers": true,
    "password_require_symbols": false,
    "max_login_attempts": 5,
    "lockout_duration": 900
  }
}
```

### TLS Configuration

```json
{
  "tls": {
    "certfile": "/path/to/cert.pem",
    "keyfile": "/path/to/key.pem",
    "ca_certs": "/path/to/ca-bundle.crt",
    "ciphers": "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA",
    "ssl_version": "TLSv1_2"
  }
}
```

## Monitoring and Observability

### Metrics Configuration

```json
{
  "metrics": {
    "enabled": true,
    "path": "/metrics",
    "namespace": "adapt",
    "buckets": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
  }
}
```

### Health Checks

```json
{
  "health": {
    "enabled": true,
    "path": "/health",
    "database_check": true,
    "filesystem_check": true
  }
}
```

## File System Configuration

### Document Root Settings

```json
{
  "filesystem": {
    "docroot": "/var/adapt/data",
    "adapt_dir": ".adapt",
    "max_file_size": "100M",
    "allowed_extensions": [".csv", ".xlsx", ".parquet", ".html", ".md", ".py"],
    "hidden_files": true,
    "follow_symlinks": false
  }
}
```

### Companion Files

```json
{
  "companions": {
    "generate_schemas": true,
    "generate_uis": true,
    "schema_extension": ".schema.json",
    "ui_extension": ".index.html",
    "override_allowed": true
  }
}
```

## Development Configuration

### Debug Mode

```json
{
  "debug": true,
  "reload": true,
  "log_level": "DEBUG",
  "cors": {
    "enabled": true,
    "origins": ["http://localhost:3000", "http://localhost:8080"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "headers": ["Content-Type", "Authorization", "X-API-Key"]
  }
}
```

### Testing Configuration

```json
{
  "testing": {
    "enabled": true,
    "database_url": "sqlite:///./test.db",
    "fixtures_dir": "tests/fixtures",
    "cleanup_after_tests": true
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
  "host": "0.0.0.0",
  "port": 443,
  "tls_cert": "/etc/ssl/certs/adapt.pem",
  "tls_key": "/etc/ssl/private/adapt.pem",
  "secure_cookies": true,
  "log_level": "WARNING"
}
```

### Development Configuration

```json
{
  "debug": true,
  "reload": true,
  "log_level": "DEBUG",
  "host": "0.0.0.0",
  "port": 8000,
  "cors": {
    "enabled": true,
    "origins": ["*"]
  }
}
```

### High-Performance Configuration

```json
{
  "workers": 8,
  "threads": 4,
  "cache": {
    "enabled": true,
    "ttl": 7200,
    "max_size": 50000
  },
  "database": {
    "pool_size": 20,
    "max_overflow": 40
  },
  "limits": {
    "max_concurrent_requests": 1000
  }
}
```

## Configuration Management

### Version Control

Keep configuration in version control (excluding secrets):

```bash
# Add to git
git add .adapt/conf.json

# Exclude secrets
echo ".adapt/secrets.json" >> .gitignore
```

### Secrets Management

Store sensitive data separately:

```json
// .adapt/secrets.json (not in git)
{
  "database_password": "secret123",
  "api_keys": ["key1", "key2"]
}
```

### Configuration Templates

Use templates for different environments:

```json
// conf.template.json
{
  "database": {
    "url": "{{ DATABASE_URL }}",
    "password": "{{ DB_PASSWORD }}"
  },
  "tls_cert": "{{ TLS_CERT_PATH }}"
}
```

## Troubleshooting Configuration

### Common Issues

1. **Configuration not loaded**
   - Check file path and permissions
   - Validate JSON syntax
   - Check for typos in keys

2. **Settings not applied**
   - Remember precedence order
   - Use `adapt check` to verify
   - Check logs for override messages

3. **Plugin not registered**
   - Verify class path
   - Check import errors
   - Ensure plugin is installed

4. **Database connection failed**
   - Verify connection string
   - Check credentials
   - Test connectivity manually

### Debugging Configuration

Enable debug logging to see configuration loading:

```json
{
  "log_level": "DEBUG",
  "logging": {
    "root": {
      "level": "DEBUG"
    }
  }
}
```

Check loaded configuration via API:

```bash
curl http://localhost:8000/admin/api/config
```

This comprehensive configuration guide covers all aspects of customizing Adapt for your specific needs and environment.

[Previous](security) | [Next](plugin_development) | [Index](index)
