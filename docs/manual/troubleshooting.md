# Troubleshooting

This guide helps diagnose and resolve common issues with Adapt servers.

## Startup Issues

### Server Won't Start

**Symptoms:**
- `adapt serve` command exits immediately
- Error messages about ports or files
- No output or cryptic error

**Common Causes & Solutions:**

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   netstat -ano | findstr :8000

   # Use a different port
   adapt serve . --port 8001
   ```

2. **Permission Denied**
   ```bash
   # Check directory permissions
   icacls "C:\path\to\docroot"

   # Run as administrator or fix permissions
   # Right-click command prompt > Run as administrator
   ```

3. **Invalid Configuration**
   ```bash
   # Validate configuration
   adapt check .

   # Check for JSON syntax errors in conf.json
   # Look for missing commas, quotes, brackets
   ```

4. **Missing Dependencies**
   ```bash
   # Check Python version
   python --version

   # Reinstall adapt
   pip install --upgrade adapt-server
   ```

### Database Errors

**Symptoms:**
- "Database locked" errors
- Authentication failures
- Permission errors

**Solutions:**

1. **Database Locked**
   ```bash
   # Stop the server first
   # Delete lock file if server crashed
   rm .adapt/adapt.db-journal

   # Or reset database (WARNING: loses data)
   rm .adapt/adapt.db
   adapt addsuperuser . --username admin
   ```

2. **Corrupt Database**
   ```bash
   # Backup first
   cp .adapt/adapt.db .adapt/adapt.db.backup

   # Try to repair
   sqlite3 .adapt/adapt.db "PRAGMA integrity_check;"

   # If corrupt, restore from backup or recreate
   ```

## Authentication Issues

### Can't Log In

**Symptoms:**
- Login form rejects valid credentials
- "Invalid username or password" repeatedly

**Troubleshooting Steps:**

1. **Check User Exists**
   ```bash
   # List users (requires superuser)
   adapt admin list-users .
   ```

2. **Reset Password**
   ```bash
   # As superuser, change password via admin UI
   # Or recreate user
   adapt admin create-user . --username newuser --password newpass
   ```

3. **Check Database**
   ```bash
   # Query users table
   sqlite3 .adapt/adapt.db "SELECT username, is_active FROM users;"
   ```

4. **Session Issues**
   - Clear browser cookies
   - Try incognito/private browsing
   - Check session timeout settings

### API Key Problems

**Symptoms:**
- API requests return 401 Unauthorized
- `X-API-Key` header ignored

**Solutions:**

1. **Verify Key Format**
   ```bash
   # Keys should be in header
   curl -H "X-API-Key: your-key-here" http://localhost:8000/api/resource
   ```

2. **Check Key Status**
   ```bash
   # Via admin UI or database
   sqlite3 .adapt/adapt.db "SELECT key_hash, is_active FROM apikey WHERE user_id = 1;"
   ```

3. **Key Expiration**
   - Check `expires_at` in database
   - Regenerate expired keys

## Permission Issues

### 403 Forbidden Errors

**Symptoms:**
- Access denied to resources
- User can log in but can't view data

**Diagnosis:**

1. **Check User Groups**
   ```bash
   # List user groups
   adapt admin list-groups .
   ```

2. **Verify Permissions**
   ```bash
   # List permissions
   adapt admin list-permissions .

   # Check group permissions
   sqlite3 .adapt/adapt.db "SELECT p.resource, p.action FROM permission p JOIN grouppermission gp ON p.id = gp.permission_id JOIN groups g ON gp.group_id = g.id WHERE g.name = 'group_name';"
   ```

3. **Resource Name Matching**
   - Permissions use exact resource names
   - Check for typos: `products` vs `product`
   - Excel sheets: `workbook/Sheet1` format

4. **Superuser Check**
   ```bash
   # Make user superuser
   sqlite3 .adapt/adapt.db "UPDATE users SET is_superuser = 1 WHERE username = 'username';"
   ```

## File Discovery Issues

### Files Not Appearing

**Symptoms:**
- Files in docroot not showing in UI
- API endpoints missing

**Troubleshooting:**

1. **Check File Extensions**
   - Supported: `.csv`, `.xlsx`, `.parquet`, `.html`, `.md`, `.py`
   - Custom plugins may add more

2. **File Permissions**
   ```bash
   # Check read permissions
   icacls "path\to\file.csv"
   ```

3. **Restart Server**
   ```bash
   # File discovery happens at startup
   # Add files, then restart server
   ```

4. **Plugin Detection**
   ```bash
   # Check plugin registry in conf.json
   # Verify plugin classes are importable
   ```

### Companion Files Not Generated

**Symptoms:**
- No `.adapt/*.schema.json` files
- No custom UI templates

**Solutions:**

1. **Check Directory Permissions**
   ```bash
   # .adapt directory needs write access
   mkdir .adapt
   ```

2. **Manual Generation**
   ```bash
   # Trigger discovery
   adapt check .
   ```

3. **Custom Schema**
   - Create `.adapt/filename.schema.json` manually
   - Follow JSON Schema format

## Data Operation Issues

### Write Operations Fail

**Symptoms:**
- POST/PATCH requests fail
- "File locked" errors
- Data not saved

**Common Issues:**

1. **File Locking**
   ```bash
   # Check active locks in admin UI
   # Or database: SELECT * FROM filelock;
   ```

2. **Permission Issues**
   - Need `write` permission for resource
   - Check filesystem write permissions

3. **Schema Validation**
   - Data must match JSON schema
   - Check error messages for validation details

4. **Concurrent Access**
   - Wait for other users to finish
   - Use retry logic in client code

### Data Corruption

**Symptoms:**
- Files become unreadable
- Inconsistent data

**Recovery:**

1. **Check Backups**
   - Restore from backup if available

2. **Atomic Writes**
   - Adapt uses atomic writes to prevent corruption
   - Check for `.tmp` files left behind

3. **Validate Data**
   ```bash
   # For CSV files
   python -c "import csv; print(sum(1 for row in csv.reader(open('file.csv'))))"
   ```

## Performance Issues

### Slow Responses

**Symptoms:**
- Pages load slowly
- API calls take long time

**Optimization:**

1. **Check Cache**
   ```bash
   # View cache status in admin UI
   # Clear cache if corrupted
   ```

2. **Large Files**
   - Use pagination for large datasets
   - Implement streaming for big files

3. **Database Queries**
   ```bash
   # Enable query logging
   # Check for slow queries
   ```

4. **Resource Usage**
   ```bash
   # Monitor CPU/memory
   # Check for memory leaks
   ```

### High Memory Usage

**Symptoms:**
- Server consumes excessive RAM
- Out of memory errors

**Solutions:**

1. **Cache Configuration**
   - Reduce cache size in conf.json
   - Adjust TTL values

2. **File Processing**
   - Process large files in chunks
   - Use streaming for uploads/downloads

3. **Database Connections**
   - Check connection pool settings
   - Close idle connections

## UI Issues

### DataTables Not Loading

**Symptoms:**
- Tables show "Loading..." forever
- JavaScript errors in browser console

**Debugging:**

1. **Check API Endpoints**
   ```bash
   curl http://localhost:8000/api/resource
   ```

2. **Browser Console**
   - Open Developer Tools (F12)
   - Check Network tab for failed requests
   - Check Console for JavaScript errors

3. **CORS Issues**
   - Ensure correct CORS configuration
   - Check for mixed HTTP/HTTPS

### Custom UI Not Working

**Symptoms:**
- Companion HTML files ignored
- Template errors

**Solutions:**

1. **File Location**
   - Must be in `.adapt/filename.index.html`
   - Check file permissions

2. **Template Syntax**
   - Valid Jinja2 syntax
   - Correct variable references

3. **Base Template**
   - Extend `base.html` for navigation
   - Include required blocks

## Plugin Issues

### Plugin Not Loading

**Symptoms:**
- Custom plugin not recognized
- Import errors

**Troubleshooting:**

1. **Check Configuration**
   ```json
   {
     "plugin_registry": {
       ".ext": "module.path:ClassName"
     }
   }
   ```

2. **Import Path**
   ```bash
   # Test import
   python -c "from module.path import ClassName"
   ```

3. **Dependencies**
   ```bash
   # Install plugin requirements
   pip install -r requirements.txt
   ```

### Plugin Errors

**Symptoms:**
- 500 Internal Server Error
- Plugin-specific exceptions

**Debugging:**

1. **Enable Debug Logging**
   ```json
   {
     "log_level": "DEBUG"
   }
   ```

2. **Check Logs**
   - Server logs for stack traces
   - Plugin-specific error messages

3. **Test Plugin Isolation**
   ```python
   # Test plugin methods individually
   plugin = MyPlugin()
   resource = plugin.load(Path('test.file'))
   ```

## Network Issues

### Connection Refused

**Symptoms:**
- Can't connect to server
- `connection refused` errors

**Checks:**

1. **Server Running**
   ```bash
   # Check process
   tasklist | findstr python

   # Check port
   netstat -ano | findstr :8000
   ```

2. **Firewall**
   - Windows Firewall blocking port
   - Antivirus software interference

3. **Host/Port Configuration**
   - Check `adapt serve --host 0.0.0.0 --port 8000`
   - Verify no proxy interference

### TLS/HTTPS Issues

**Symptoms:**
- Certificate errors
- Mixed content warnings

**Solutions:**

1. **Certificate Files**
   ```bash
   # Check file existence and permissions
   ls -la cert.pem key.pem
   ```

2. **Certificate Validity**
   ```bash
   # Check certificate
   openssl x509 -in cert.pem -text -noout
   ```

3. **Configuration**
   ```json
   {
     "tls_cert": "/full/path/to/cert.pem",
     "tls_key": "/full/path/to/key.pem",
     "secure_cookies": true
   }
   ```

## Backup and Recovery

### Creating Backups

```bash
# Stop server first
# Backup data directory
tar -czf backup.tar.gz /path/to/docroot

# Or just database
cp .adapt/adapt.db .adapt/adapt.db.backup
```

### Recovery Process

1. **Stop Server**
2. **Restore Files**
   ```bash
   tar -xzf backup.tar.gz
   ```
3. **Fix Permissions**
4. **Start Server**
5. **Test Functionality**

## Getting Help

### Diagnostic Information

When reporting issues, include:

1. **System Info**
   ```bash
   python --version
   pip list | grep adapt
   systeminfo
   ```

2. **Configuration**
   ```bash
   cat .adapt/conf.json
   ```

3. **Logs**
   ```bash
   # Recent logs
   tail -n 100 adapt.log
   ```

4. **Error Reproduction**
   - Steps to reproduce the issue
   - Expected vs actual behavior

### Support Resources

1. **Documentation**: Check this manual and README
2. **GitHub Issues**: Search existing issues
3. **Community**: Forums or discussion groups
4. **Professional Support**: For enterprise deployments

### Emergency Procedures

For production outages:

1. **Assess Impact**: How many users affected?
2. **Check Monitoring**: Any alerts or metrics?
3. **Isolate Issue**: Can you reproduce locally?
4. **Implement Workaround**: Temporary fixes
5. **Escalate**: Contact development team
6. **Document**: Record everything for post-mortem

This troubleshooting guide covers the most common issues. For complex problems, consider enabling debug logging and collecting detailed diagnostic information before seeking help.