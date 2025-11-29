# Architecture

[Previous](plugin_development) | [Next](troubleshooting) | [Index](index)

This document describes the internal architecture of Adapt, including system components, data flow, and design patterns.

## System Overview

```mermaid
graph TB
    subgraph "Client Layer"
        C1[Web Browser]
        C2[API Client]
        C3[CLI Tools]
    end

    subgraph "Adapt Server"
        A1[FastAPI App]
        A2[Authentication]
        A3[Authorization]
        A4[Caching Layer]
        A5[Plugin System]
        A6[Database Layer]
    end

    subgraph "File System"
        F1[Document Root]
        F2[Companion Files]
        F3[Configuration]
    end

    C1 --> A1
    C2 --> A1
    C3 --> A1

    A1 --> A2
    A1 --> A3
    A1 --> A4
    A1 --> A5

    A5 --> F1
    A5 --> F2
    A4 --> A6
    A2 --> A6
    A3 --> A6
```

## Core Components

### 1. FastAPI Application

The central web framework handling HTTP requests:

- **Routing**: Dynamic route generation based on discovered resources
- **Middleware**: Authentication, CORS, security headers
- **Dependency Injection**: Request context and user information
- **Background Tasks**: Cleanup, monitoring, scheduled operations

### 2. Authentication System

Multi-layered authentication with session and API key support:

```mermaid
flowchart TD
    A[Request] --> B{Has Session Cookie?}
    B -->|Yes| C[Validate Session]
    B -->|No| D{Has API Key?}
    D -->|Yes| E[Validate API Key]
    D -->|No| F[Anonymous User]

    C -->|Valid| G[Authenticated User]
    C -->|Invalid| H[401 Unauthorized]
    E -->|Valid| G
    E -->|Invalid| H

    G --> I[Proceed to Authorization]
    F --> I
    H --> J[Error Response]
```

### 3. Authorization System

Role-Based Access Control (RBAC) with resource-level permissions:

```mermaid
flowchart TD
    A[Authenticated Request] --> B{User is Superuser?}
    B -->|Yes| C[Allow All Actions]
    B -->|No| D[Get User Groups]
    D --> E[Get Group Permissions]
    E --> F{Resource + Action Allowed?}
    F -->|Yes| G[Allow Access]
    F -->|No| H[403 Forbidden]

    C --> I[Proceed]
    G --> I
    H --> J[Deny Access]
```

### 4. Plugin System

Extensible architecture for handling different file types:

```mermaid
classDiagram
    class Plugin {
        +detect(path: Path): bool
        +load(path: Path): ResourceDescriptor
        +schema(resource): dict
        +read(resource, request): Any
        +write(resource, data, request, context): Any
        +get_route_configs(resource): list
        +get_ui_template(resource): tuple
    }

    class DatasetPlugin {
        +_infer_schema()
        +_validate_data()
        +_acquire_lock()
    }

    class ContentPlugin {
        +_render_content()
    }

    class HandlerPlugin {
        +_load_router()
    }

    Plugin <|-- DatasetPlugin
    Plugin <|-- ContentPlugin
    Plugin <|-- HandlerPlugin

    class PluginRegistry {
        +register(extension, plugin_class)
        +get_plugin(path): Plugin
    }

    PluginRegistry --> Plugin
```

## Data Flow

### Request Processing Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Auth
    participant Plugin
    participant Cache
    participant Database
    participant Filesystem

    Client->>FastAPI: HTTP Request
    FastAPI->>Auth: Check Authentication
    Auth->>Database: Validate Session/API Key
    Database-->>Auth: User Info
    Auth-->>FastAPI: User Context

    FastAPI->>Plugin: Check Authorization
    Plugin->>Database: Get Permissions
    Database-->>Plugin: Permission List
    Plugin-->>FastAPI: Access Decision

    FastAPI->>Cache: Check Cache
    Cache-->>FastAPI: Cached Response (if available)

    FastAPI->>Plugin: Process Request
    Plugin->>Filesystem: Read/Write Data
    Filesystem-->>Plugin: Data
    Plugin-->>FastAPI: Response

    FastAPI->>Cache: Store Response
    FastAPI-->>Client: HTTP Response
```

### File Discovery Flow

```mermaid
flowchart TD
    A[Server Startup] --> B[Scan Document Root]
    B --> C[For Each File]
    C --> D{Plugin Detects?}
    D -->|Yes| E[Plugin Load]
    D -->|No| F[Skip File]

    E --> G[Create ResourceDescriptor]
    G --> H[Generate Companion Files]
    H --> I[Register Routes]
    I --> J[Add to Resource List]

    F --> K{More Files?}
    J --> K
    K -->|Yes| C
    K -->|No| L[Discovery Complete]

    L --> M[Start Server]
```

## Database Schema

Adapt uses SQLite with the following core tables:

```mermaid
erDiagram
    users ||--o{ usergroup : ""
    users ||--o{ apikey : ""
    users ||--o{ auditlog : ""

    groups ||--o{ usergroup : ""
    groups ||--o{ grouppermission : ""

    permission ||--o{ grouppermission : ""

    users ||--o{ dbsession : ""

    users {
        integer id PK
        text username UK
        text password_hash
        boolean is_active
        boolean is_superuser
        timestamp created_at
    }

    groups {
        integer id PK
        text name UK
        text description
    }

    permission {
        integer id PK
        text resource
        text action
        text description
    }

    usergroup {
        integer user_id FK
        integer group_id FK
    }

    grouppermission {
        integer group_id FK
        integer permission_id FK
    }

    dbsession {
        integer id PK
        integer user_id FK
        text token UK
        timestamp created_at
        timestamp expires_at
        timestamp last_active
    }

    apikey {
        integer id PK
        integer user_id FK
        text key_hash UK
        text description
        timestamp created_at
        timestamp expires_at
        timestamp last_used_at
        boolean is_active
    }

    auditlog {
        integer id PK
        integer user_id FK
        timestamp timestamp
        text action
        text resource
        text details
    }
```

## Caching Architecture

Multi-level caching system:

```mermaid
graph TD
    A[Request] --> B{Memory Cache}
    B -->|Hit| C[Return Cached]
    B -->|Miss| D{Disk Cache}
    D -->|Hit| E[Load to Memory]
    E --> C
    D -->|Miss| F[Compute Result]
    F --> G[Store in Disk]
    G --> H[Store in Memory]
    H --> C

    I[Write Operation] --> J[Invalidate Cache]
    J --> K[Delete Memory]
    K --> L[Delete Disk]
```

### Cache Key Strategy

- **Read Operations**: `read:{resource_name}:{params_hash}`
- **Schema Operations**: `schema:{resource_name}`
- **UI Templates**: `ui:{resource_name}:{user_id}`

## Locking System

File-level locking for safe concurrent access:

```mermaid
stateDiagram-v2
    [*] --> Available
    Available --> Locked: Acquire Lock
    Locked --> Available: Release Lock
    Locked --> Stale: Timeout
    Stale --> Available: Cleanup
    Stale --> Locked: Retry Success
```

### Lock Implementation

```python
# Optimistic locking with database constraints
def acquire_lock(resource_path: str, user_id: int) -> bool:
    try:
        # Insert lock record (fails if exists)
        db.execute("""
            INSERT INTO filelock (resource_path, user_id, expires_at)
            VALUES (?, ?, datetime('now', '+5 minutes'))
        """, (resource_path, user_id))
        return True
    except IntegrityError:
        # Check if existing lock is expired
        existing = db.execute("""
            SELECT user_id, expires_at FROM filelock
            WHERE resource_path = ?
        """, (resource_path,)).fetchone()

        if existing and datetime.now() > existing.expires_at:
            # Clean up stale lock and retry
            db.execute("DELETE FROM filelock WHERE resource_path = ?", (resource_path,))
            return acquire_lock(resource_path, user_id)

        return False
```

## Plugin Architecture Deep Dive

### Plugin Loading

```mermaid
flowchart TD
    A[Server Startup] --> B[Load Plugin Registry]
    B --> C[For Each Extension]
    C --> D[Import Plugin Class]
    D --> E[Instantiate Plugin]
    E --> F[Register Plugin]
    F --> G{More Extensions?}
    G -->|Yes| C
    G -->|No| H[Plugins Ready]

    I[File Discovery] --> J[Get Plugin for Extension]
    J --> K[Plugin.detect(path)]
    K -->|True| L[Plugin.load(path)]
    K -->|False| M[Next Plugin]
```

### Route Generation

```mermaid
flowchart TD
    A[Resource Loaded] --> B[Plugin.get_route_configs()]
    B --> C[For Each Route Config]
    C --> D[Create FastAPI Router]
    D --> E[Add Authentication]
    E --> F[Add Authorization]
    F --> G[Add Caching]
    G --> H[Register with App]
    H --> I{More Routes?}
    I -->|Yes| C
    I -->|No| J[Routes Active]
```

## Security Architecture

### Defense in Depth

```mermaid
graph TD
    A[Network] --> B[TLS Encryption]
    B --> C[Authentication]
    C --> D[Authorization]
    D --> E[Input Validation]
    E --> F[Safe File Operations]
    F --> G[Audit Logging]
    G --> H[Monitoring]
```

### Threat Model

**Attack Vectors Considered:**
- Network eavesdropping (mitigated by TLS)
- Authentication bypass (multi-factor checks)
- Authorization bypass (RBAC enforcement)
- Data injection (schema validation)
- File system attacks (path validation, safe writes)
- DoS attacks (rate limiting, resource limits)

## Performance Characteristics

### Scalability Factors

- **Concurrent Users**: Limited by database connection pool
- **File Size**: Streaming for large files, pagination for datasets
- **Plugin Count**: Minimal overhead per plugin
- **Cache Hit Rate**: Dramatically improves response times

### Performance Metrics

```mermaid
graph LR
    A[Request Rate] --> B[Throughput]
    A --> C[Latency]
    B --> D[Resource Usage]
    C --> D
    D --> E[Scaling Decisions]
```

### Optimization Strategies

1. **Caching**: GET responses cached with TTL
2. **Async I/O**: Non-blocking file operations
3. **Connection Pooling**: Database connection reuse
4. **Lazy Loading**: Resources loaded on demand
5. **Background Processing**: Cleanup and maintenance tasks

## Deployment Patterns

### Single Server

```mermaid
graph TD
    A[Load Balancer] --> B[Adapt Server]
    B --> C[SQLite DB]
    B --> D[File System]
    B --> E[Cache Store]
```

### Multi-Server

```mermaid
graph TD
    A[Load Balancer] --> B[Adapt Server 1]
    A --> C[Adapt Server 2]
    A --> D[Adapt Server N]

    B --> E[Shared Database]
    C --> E
    D --> E

    B --> F[Shared Storage]
    C --> F
    D --> F

    B --> G[Redis Cache]
    C --> G
    D --> G
```

### Container Deployment

```mermaid
graph TD
    A[Docker Host] --> B[Adapt Container]
    B --> C[Volume: Data]
    B --> D[Volume: Config]
    B --> E[Network: External]
```

## Monitoring and Observability

### Metrics Collection

- **Request Metrics**: Count, latency, error rates
- **Resource Metrics**: CPU, memory, disk I/O
- **Business Metrics**: Active users, API calls, data volumes
- **Security Metrics**: Failed logins, permission denials

### Logging Strategy

```mermaid
graph TD
    A[Application Logs] --> B[Structured JSON]
    B --> C[Log Aggregation]
    C --> D[Search/Indexing]
    D --> E[Dashboards]
    E --> F[Alerting]
```

### Health Checks

- **Application Health**: `/health` endpoint
- **Database Health**: Connection and query tests
- **Filesystem Health**: Read/write permissions
- **Dependency Health**: Plugin and external service checks

## Future Architecture

### Planned Extensions

- **GraphQL Support**: Query interface for complex data relationships
- **Real-time Updates**: WebSocket support for live data
- **Plugin Marketplace**: Centralized plugin distribution
- **Multi-tenancy**: Isolated workspaces for different users/teams
- **API Gateway**: Advanced routing and transformation capabilities

This architecture document provides a comprehensive view of Adapt's design, enabling developers to understand, extend, and maintain the system effectively.

[Previous](plugin_development) | [Next](troubleshooting) | [Index](index)
