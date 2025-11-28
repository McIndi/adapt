# Admin Guide

This guide covers system administration tasks for Adapt servers, including user management, permissions, monitoring, and maintenance.

## Initial Setup

### Creating the First Superuser

After starting Adapt for the first time:

```bash
adapt addsuperuser /path/to/docroot --username admin
```

You'll be prompted to set a password. This creates a superuser with full administrative access.

### Setting Up Permissions

Create permissions for your resources:

```bash
# Create permissions for all resources
adapt admin create-permissions /path/to/docroot __all__

# Or specify individual resources
adapt admin create-permissions /path/to/docroot products inventory reports
```

This creates:
- A "read" permission for each resource
- A "write" permission for each resource
- Default groups: `{resource}-readers`, `{resource}-writers`

## Admin Interface

Access the admin interface at `/admin/` (requires superuser login).

### Users Tab

#### Creating Users
1. Click "Add User"
2. Enter username and password
3. Optionally set superuser status
4. Click "Create"

#### Managing Users
- **Edit**: Change passwords or superuser status
- **Delete**: Remove users (logs action in audit)
- **View Details**: See creation date and last login

### Groups Tab

#### Creating Groups
1. Click "Add Group"
2. Enter name and description
3. Add users to the group
4. Assign permissions to the group

#### Group Management
- **Membership**: Add/remove users from groups
- **Permissions**: Grant/revoke permissions for groups
- **Hierarchy**: Users inherit permissions from all groups

### Permissions Tab

#### Creating Permissions
1. Click "Add Permission"
2. Enter resource (e.g., `products`, `inventory/Stock`)
3. Select action (`read` or `write`)
4. Add description

#### Permission Management
- **View All**: See all defined permissions
- **Delete**: Remove unused permissions
- **Assignment**: Manage which groups have which permissions

### Locks Tab

#### Monitoring Locks
- **Active Locks**: See current file locks
- **Lock Details**: User, resource, timestamp, TTL
- **Stale Locks**: Identify locks that should be cleaned up

#### Managing Locks
- **Release Lock**: Manually unlock files
- **Auto-Cleanup**: Server automatically cleans locks older than 5 minutes

### API Keys Tab

#### Creating API Keys
1. Click "Generate Key" for a user
2. Optionally set expiration date
3. Add description

#### Key Management
- **View Keys**: See all keys with metadata
- **Revoke Keys**: Deactivate keys
- **Monitor Usage**: Track last used timestamps

### Audit Logs Tab

#### Viewing Logs
- **All Actions**: Chronological list of system events
- **Filter**: By user, action, resource, or date range
- **Details**: Full context for each action

#### Common Actions Logged
- User login/logout
- User/group/permission changes
- API key creation/revocation
- Data modifications
- Lock operations

### Cache Tab

#### Cache Management
- **View Entries**: See cached responses with metadata
- **Clear Individual**: Remove specific cache entries
- **Clear All**: Flush entire cache
- **Monitor Usage**: Track cache hit rates and storage

## CLI Administration

### User Management

```bash
# List all users
adapt admin list-users /path/to/docroot

# Create user
adapt admin create-user /path/to/docroot --username newuser --password secret

# Delete user
adapt admin delete-user /path/to/docroot --username olduser

# Change password
adapt admin change-password /path/to/docroot --username user --password newpass
```

### Group Management

```bash
# List groups
adapt admin list-groups /path/to/docroot

# Create group
adapt admin create-group /path/to/docroot --name "analysts"

# Add user to group
adapt admin add-to-group /path/to/docroot --username user --group analysts

# Remove user from group
adapt admin remove-from-group /path/to/docroot --username user --group analysts
```

### Permission Management

```bash
# List permissions
adapt admin list-permissions /path/to/docroot

# Create permission
adapt admin create-permission /path/to/docroot --resource products --action read

# Grant permission to group
adapt admin grant-permission /path/to/docroot --group analysts --permission products:read

# Revoke permission
adapt admin revoke-permission /path/to/docroot --group analysts --permission products:read
```

### Resource Management

```bash
# List all discovered resources
adapt admin list-resources /path/to/docroot

# Create permissions for resources
adapt admin create-permissions /path/to/docroot products inventory --all-group --read-group
```

## Security Best Practices

### Password Policies
- Enforce strong passwords (minimum 8 characters, mixed case, numbers, symbols)
- Regular password rotation
- No shared accounts

### API Key Management
- Use descriptive names for API keys
- Set expiration dates for temporary access
- Monitor usage patterns
- Revoke keys immediately when compromised

### Permission Design
- **Principle of Least Privilege**: Grant minimum required access
- **Group-Based Access**: Use groups rather than individual permissions
- **Regular Audits**: Review permissions periodically
- **Separation of Duties**: Different users for different roles

### Network Security
- Use HTTPS in production
- Configure secure cookies
- Implement firewall rules
- Regular security updates

## Monitoring and Maintenance

### Log Analysis

Adapt logs to stdout/stderr. Configure logging in `conf.json`:

```json
{
  "logging": {
    "version": 1,
    "root": {
      "level": "INFO",
      "handlers": ["file", "console"]
    },
    "handlers": {
      "file": {
        "class": "logging.FileHandler",
        "filename": "adapt.log",
        "formatter": "detailed"
      },
      "console": {
        "class": "logging.StreamHandler",
        "formatter": "simple"
      }
    },
    "formatters": {
      "simple": {
        "format": "%(asctime)s - %(levelname)s - %(message)s"
      },
      "detailed": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d"
      }
    }
  }
}
```

### Key Log Events
- Server startup/shutdown
- User authentication
- File operations
- Lock acquisitions/releases
- Cache hits/misses
- Error conditions

### Performance Monitoring

#### Cache Performance
- Monitor cache hit rates
- Adjust TTL values based on data change frequency
- Clear cache during maintenance windows

#### Lock Monitoring
- Watch for frequent lock conflicts
- Identify long-running operations
- Set up alerts for stale locks

#### Database Maintenance
The SQLite database (`adapt.db`) may need occasional maintenance:

```bash
# Backup database
cp .adapt/adapt.db .adapt/adapt.db.backup

# Vacuum database (reclaim space)
sqlite3 .adapt/adapt.db "VACUUM;"

# Analyze query performance
sqlite3 .adapt/adapt.db "ANALYZE;"
```

### Backup Strategy

#### Data Files
- Regular filesystem backups of the document root
- Include `.adapt/` directory for companion files
- Test restore procedures

#### Database
- Backup `adapt.db` regularly
- Export user/group/permission data
- Document recovery procedures

### Disaster Recovery

1. **Stop the server**
2. **Restore from backup**
3. **Verify database integrity**
4. **Restart and test functionality**
5. **Review audit logs for incident analysis**

## Troubleshooting

### Common Issues

#### Users Can't Access Resources
- Check group membership
- Verify permissions are assigned
- Review permission resource names (case-sensitive)

#### Performance Degradation
- Check cache status
- Monitor active locks
- Review database size
- Analyze query patterns

#### Authentication Failures
- Verify user accounts are active
- Check password policies
- Review session expiration settings

#### File Operation Errors
- Check filesystem permissions
- Look for lock conflicts
- Verify file formats are supported

### Diagnostic Commands

```bash
# Check server configuration
adapt check /path/to/docroot

# List all endpoints
adapt list-endpoints /path/to/docroot

# View system status
curl -H "X-API-Key: admin-key" http://localhost:8000/admin/api/status
```

### Log Analysis Scripts

Create scripts to analyze logs:

```python
import re
from collections import Counter

# Parse access patterns
with open('adapt.log', 'r') as f:
    logs = f.readlines()

# Count requests by endpoint
endpoints = []
for line in logs:
    match = re.search(r'GET (/[^ ]*)', line)
    if match:
        endpoints.append(match.group(1))

print("Top endpoints:")
for endpoint, count in Counter(endpoints).most_common(10):
    print(f"{endpoint}: {count}")
```

## Scaling Considerations

### Single Server Scaling
- **Caching**: Increase cache TTL for read-heavy workloads
- **Database**: Use WAL mode for concurrent access
- **File System**: Use fast storage for large datasets
- **Memory**: Monitor memory usage for large schemas

### Multi-Server Deployment
- **Shared Storage**: Use NFS or similar for document root
- **Database**: Move to PostgreSQL/MySQL for multi-server
- **Load Balancing**: Distribute requests across instances
- **Session Storage**: Configure shared session store

### High Availability
- **Backup Servers**: Hot standby instances
- **Database Replication**: For auth/cache data
- **Monitoring**: Comprehensive alerting
- **Failover**: Automatic switchover procedures

## Compliance and Auditing

### Audit Requirements
- **Data Access**: Log all data reads/writes
- **User Actions**: Track admin operations
- **Security Events**: Monitor failed authentications
- **Retention**: Configure log retention policies

### Compliance Features
- **Row-Level Security**: Restrict data access per user
- **Audit Trails**: Complete action history
- **Access Controls**: Granular permission system
- **Encryption**: TLS for data in transit

### Regular Audits
1. **Permission Review**: Quarterly permission audits
2. **Access Logs**: Monthly log reviews
3. **Security Testing**: Annual penetration testing
4. **Backup Testing**: Quarterly restore tests

## Advanced Configuration

### Custom Plugins
Extend Adapt with custom plugins in `conf.json`:

```json
{
  "plugin_registry": {
    ".custom": "mycompany.plugins.CustomPlugin"
  }
}
```

### Performance Tuning
```json
{
  "cache_ttl": 3600,
  "max_connections": 100,
  "worker_processes": 4
}
```

### Security Hardening
```json
{
  "secure_cookies": true,
  "session_timeout": 3600,
  "password_policy": {
    "min_length": 12,
    "require_uppercase": true,
    "require_numbers": true,
    "require_symbols": true
  }
}
```

This comprehensive admin guide covers all aspects of managing an Adapt server in production environments.