# Configuration File Support: Making Adapt More Customizable

Hey developers! In this sprint, we've introduced support for a configuration file (`conf.json`) in the document root's `.adapt/` directory, allowing users to customize Adapt's behavior without modifying code. This includes configuring file handlers, TLS settings, and other options, making Adapt more flexible and user-friendly. Let's dive into what we implemented, why it's valuable, and how it works.

## 1. **What We Changed**
We added a new configuration system centered around `DOCROOT/.adapt/conf.json`, which is automatically created with defaults on first run. Key changes include:

- **Config Loading**: Extended `AdaptConfig` with a `load_from_file()` method that reads, validates, and merges `conf.json` settings.
- **Validation**: Strict validation ensures only allowed keys and correct types; invalid configs cause the server to exit with an error.
- **CLI Integration**: The `adapt serve` command now loads config after initialization, with CLI args taking precedence.
- **Check Command Enhancement**: `adapt check` also loads config and validates TLS file existence, providing early feedback.
- **Documentation Updates**: Updated README.md and docs/spec/06_cli_config.md with usage examples and precedence rules.
- **Comprehensive Tests**: Added `test_config.py` with 6 test cases covering creation, loading, merging, and validation failures.

The config supports:
- `plugin_registry`: Map file extensions to plugin classes for custom handlers.
- `tls_cert`/`tls_key`: Paths to TLS certificate and key files.
- `secure_cookies`: Boolean for setting secure cookie flags.

## 2. **Why This Matters**
Adapt's original design emphasized zero-configuration startup, which is great for simplicity but limited customization. Users deploying Adapt in production or with specific needs (e.g., custom file types, HTTPS) had to use CLI args or modify code. This change addresses that by providing a discoverable, file-based config that:

- **Improves Usability**: Users can edit `conf.json` to add custom plugins or set TLS without CLI flags.
- **Maintains Simplicity**: The file is auto-created with defaults; deleting it resets to defaults.
- **Ensures Safety**: Validation prevents misconfigurations from causing runtime issues.
- **Supports Extensibility**: Plugins and future features can leverage the config system.
- **Aligns with Standards**: Many tools use JSON configs; this makes Adapt more intuitive.

This follows our coding standards by keeping changes focused and adding tests for reliability.

## 3. **How to Use It**
When you run `adapt serve <root>` or `adapt check <root>`, Adapt creates `DOCROOT/.adapt/conf.json` if it doesn't exist:

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    // ... other defaults
  },
  "tls_cert": null,
  "tls_key": null,
  "secure_cookies": false
}
```

Edit it to customize:
```json
{
  "plugin_registry": {
    ".custom": "my_plugin.CustomPlugin"
  },
  "tls_cert": "/path/to/cert.pem",
  "tls_key": "/path/to/key.pem",
  "secure_cookies": true
}
```

Precedence: CLI args (e.g., `--tls-cert`) override `conf.json`, which overrides defaults. Invalid configs exit immediately.

## 4. **Adding a New Configuration Option**
To add a new supported config key (e.g., `new_option` as a string):

1. **Update AdaptConfig** (`adapt/config.py`): Add the field to the dataclass with a default value.
   ```python
   new_option: str = "default_value"
   ```

2. **Modify load_from_file()** (`adapt/config.py`): Add to `allowed_keys`, validate type, and merge.
   ```python
   allowed_keys = {"plugin_registry", "tls_cert", "tls_key", "secure_cookies", "new_option"}
   # In validation:
   if "new_option" in data:
       if not isinstance(data["new_option"], str):
           logger.error("new_option must be str")
           sys.exit(1)
   # In merge:
   if "new_option" in data:
       self.new_option = data["new_option"]
   ```

3. **Update Defaults** (`adapt/config.py` in `load_from_file()`): Include in the auto-created `conf.json`.
   ```python
   defaults = {
       # ... existing
       "new_option": self.new_option,
   }
   ```

4. **Use the Option**: Access via `config.new_option` in relevant code (e.g., plugins, app setup).

5. **Add Tests** (`tests/test_config.py`): Extend with validation and merging tests for the new option.

6. **Update Docs** (`README.md` and `docs/spec/06_cli_config.md`): Add to documentation with examples.

This ensures new options integrate seamlessly with validation and precedence.

## 5. **Plugin Integration with Config**
Plugins can leverage the config system unobtrusively by accessing `request.app.state.config` in route handlers or plugin methods. For example:

- **Custom Handlers**: A plugin can check `config.plugin_registry` for its extension and adjust behavior.
- **TLS-Aware Features**: Plugins can conditionally enable features based on `config.tls_cert` (e.g., secure redirects).
- **Extensible Config**: While core config is strictly validated and only allows predefined keys, plugins can suggest new config options to be added to the core system for extensibility.

Example in a plugin:
```python
def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
    config = descriptor.request.app.state.config  # Assuming passed or accessed
    if config.secure_cookies:
        # Enable secure features
        pass
    # ...
```

This keeps plugins intuitive and config-driven without tight coupling.

## 6. **Conclusion**
This config file support makes Adapt more powerful and user-friendly, enabling easy customization for deployments. By following the pattern for adding options, we can extend it incrementally. Plugins benefit through access to config, promoting flexible, config-aware behavior. As always, we've added tests to ensure reliability. Looking forward to your feedback and future enhancements!