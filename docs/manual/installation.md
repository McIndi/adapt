# Installation

## System Requirements

- Python 3.8 or higher
- pip package manager
- SQLite (included with Python)

## Installation

Install Adapt from PyPI:

```bash
pip install adapt-server
```

For development or to build from source:

```bash
git clone https://github.com/your-org/adapt.git
cd adapt
pip install -e .
```

## Quick Start

1. Create a directory for your data:

```bash
mkdir my-adapt-server
cd my-adapt-server
```

2. Add some sample data files:

```bash
# Create a CSV file
echo "name,age,city
Alice,25,New York
Bob,30,San Francisco
Charlie,35,Chicago" > employees.csv

# Create a simple HTML page
echo "<h1>Welcome to Adapt</h1><p>This is a test page.</p>" > index.html
```

3. Start the server:

```bash
adapt serve .
```

4. Open your browser to `http://localhost:8000`

Adapt will automatically:
- Generate a landing page at `/`
- Create API endpoints at `/api/employees`
- Create a UI at `/ui/employees`
- Serve the HTML page at `/index`

## CLI Commands

### Basic Commands

```bash
# Start the server
adapt serve <directory> [options]

# Check configuration and list resources
adapt check <directory>

# Create a superuser
adapt addsuperuser <directory> --username <username>

# List all generated endpoints
adapt list-endpoints <directory>
```

### Administrative Commands

```bash
# List all discovered resources
adapt admin list-resources <directory>

# Create permissions for resources
adapt admin create-permissions <directory> <resource>... [--all-group] [--read-group]

# List groups and their permissions
adapt admin list-groups <directory>
```

### Command Options

```bash
adapt serve <directory> [OPTIONS]

Options:
  --host TEXT          Host to bind to (default: 127.0.0.1)
  --port INTEGER       Port to bind to (default: 8000)
  --tls-cert PATH      Path to TLS certificate file
  --tls-key PATH        Path to TLS private key file
  --read-only           Start server in read-only mode
  --admin               Enable admin interface (default: enabled)
  --log-level TEXT      Set logging level (DEBUG, INFO, WARNING, ERROR)
  --reload              Enable auto-reload on file changes (development)
```

## Configuration File

Adapt uses a configuration file at `DOCROOT/.adapt/conf.json`. If it doesn't exist, it's created with defaults on first run.

Example `conf.json`:

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
    ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
    ".html": "adapt.plugins.html_plugin.HtmlPlugin",
    ".md": "adapt.plugins.markdown_plugin.MarkdownPlugin",
    ".py": "adapt.plugins.python_plugin.PythonPlugin"
  },
  "tls_cert": null,
  "tls_key": null,
  "secure_cookies": false,
  "logging": {
    "version": 1,
    "root": {
      "level": "INFO",
      "handlers": ["console"]
    },
    "handlers": {
      "console": {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "stream": "ext://sys.stdout"
      }
    },
    "formatters": {
      "default": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      }
    }
  }
}
```

Configuration precedence: CLI arguments > `conf.json` > defaults.

## TLS/HTTPS Setup

To enable HTTPS:

1. Obtain or generate TLS certificates
2. Configure in `conf.json` or via CLI:

```json
{
  "tls_cert": "/path/to/certificate.pem",
  "tls_key": "/path/to/private-key.pem",
  "secure_cookies": true
}
```

Or via CLI:

```bash
adapt serve . --tls-cert /path/to/cert.pem --tls-key /path/to/key.pem
```

## Directory Structure

Adapt creates a `.adapt/` directory in your document root for companion files:

```
your-data-directory/
├── data.csv
├── document.md
├── .adapt/
│   ├── conf.json          # Configuration file
│   ├── adapt.db           # SQLite database (auth, cache, locks)
│   ├── data.schema.json   # Inferred schema for data.csv
│   ├── data.index.html    # Generated UI template for data.csv
│   └── data.db            # Additional metadata if needed
```

## Troubleshooting Installation

### Common Issues

1. **Port already in use**: Use `--port` to specify a different port
2. **Permission denied**: Ensure write access to the document root
3. **Import errors**: Verify Python version and pip installation
4. **Database errors**: Delete `.adapt/adapt.db` and restart

### Verifying Installation

Run the check command to verify everything is working:

```bash
adapt check .
```

This will:
- Initialize the database
- Check configuration
- List discovered resources
- Report any issues