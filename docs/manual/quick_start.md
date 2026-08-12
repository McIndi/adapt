# Quick Start Guide

This guide shows how to start an Adapt server with realistic examples.

## Step 1: Install Adapt

```bash
pip install adapt-server
```

## Step 2: Create a Working Directory

```bash
mkdir adapt-demo
cd adapt-demo
```

## Step 3: Add Sample Files

Create `products.csv`:

```csv
id,name,price,category,in_stock
1,Laptop,999.99,Electronics,true
2,Book,19.99,Books,true
3,Headphones,79.99,Electronics,false
4,Notebook,4.99,Stationery,true
5,Mouse,24.99,Electronics,true
```

Create `readme.md`:

```markdown
# Welcome to Adapt Demo

This demo shows generated APIs, schema routes, and UI pages.
```

Optional: create `reports.py`:

```python
from fastapi import APIRouter
import csv

router = APIRouter()

@router.get("/summary")
def summary():
    with open("products.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    in_stock = [r for r in rows if str(r.get("in_stock", "")).lower() == "true"]
    total_value = sum(float(r.get("price", 0) or 0) for r in in_stock)

    return {
        "total_products": len(rows),
        "in_stock": len(in_stock),
        "out_of_stock": len(rows) - len(in_stock),
        "total_inventory_value": round(total_value, 2),
    }
```

## Step 4: Create a Superuser

Generated resource routes require authentication and the corresponding
resource permission. A superuser bypasses the normal resource permission
checks. Before you start the server, create a superuser.

```bash
adapt addsuperuser . --username admin
```

The command prompts for a password.

## Step 5: Start the Server

```bash
adapt serve .
```

Open `http://localhost:8000`.

## Step 6: Sign In and Create an API Key

Open `http://localhost:8000/auth/login`. Sign in as `admin`. Then open
`http://localhost:8000/profile` and create an API key. When the key is
shown, copy it. Adapt does not display the raw value again.

The browser UI uses your authenticated session. The command-line examples
below use the superuser API key and are therefore exempt from CSRF checks.

```bash
export ADAPT_API_KEY='<superuser-api-key>'
```

## Step 7: Explore Generated Routes

Try these endpoints in a browser first:

- `/ui/products/`
- `/schema/products/`
- `/readme`
- `/api/reports/summary` (if you created `reports.py`)

You must authenticate your browser session to open the generated resource
routes. A non-superuser also needs the resource's `read` permission.

## Step 8: Use the Dataset API

Dataset mutations are action-based and target `/api/{resource}/`.

Get rows:

```bash
curl -H "X-API-Key: $ADAPT_API_KEY" http://localhost:8000/api/products/
```

Create a row:

```bash
curl -X POST http://localhost:8000/api/products/ \
  -H "X-API-Key: $ADAPT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"create","data":[{"name":"Keyboard","price":49.99,"category":"Electronics","in_stock":true}]}'
```

Update a row by `_row_id`:

```bash
curl -X PATCH http://localhost:8000/api/products/ \
  -H "X-API-Key: $ADAPT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"update","data":{"_row_id":1,"price":899.99}}'
```

Delete a row by `_row_id`:

```bash
curl -X DELETE http://localhost:8000/api/products/ \
  -H "X-API-Key: $ADAPT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"delete","data":{"_row_id":1}}'
```

## Step 9: Optional Non-Superuser Permissions

Create permissions and groups for discovered resources:

```bash
adapt admin create-permissions . __all__
```

List groups and users:

```bash
adapt admin list-groups .
adapt admin list-users .
```

For each resource, the command creates `<resource>_readonly` and
`<resource>_readwrite` groups. Add non-superusers to the appropriate group.
The combined groups also include a suffix made from the selected resource
names. See the [Admin Guide](admin_guide.md) for details.

## Step 10: Optional Serve Flags

```bash
adapt serve . --host 127.0.0.1 --port 8000 --debug
```

Read-only mode:

```bash
adapt serve . --readonly
```

## What You Have Running

- Generated dataset API at `/api/products/`
- Generated schema at `/schema/products/`
- Generated UI at `/ui/products/`
- Markdown route at `/readme`
- Optional Python handler route(s) under `/api/reports/*`

## Next Steps

- Continue to the [User Guide](user_guide.md)
- Review complete routes in the [API Reference](api_reference.md)
- Use the [Admin Guide](admin_guide.md) for user and group management

Manual navigation: [Previous: Installation](installation.md) | [Index](index.md) | [Next: User Guide](user_guide.md)
