# Quick Start Guide

[Previous](installation) | [Next](user_guide) | [Index](index)

This guide gets an Adapt server running with realistic examples.

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

## Step 4: Start the Server

```bash
adapt serve .
```

Open `http://localhost:8000`.

## Step 5: Explore Generated Routes

Try these endpoints in a browser first:

- `/ui/products`
- `/schema/products`
- `/readme`
- `/api/reports/summary` (if you created `reports.py`)

## Step 6: Use the Dataset API

Dataset mutations are action-based and target `/api/{resource}`.

Get rows:

```bash
curl http://localhost:8000/api/products
```

Create a row:

```bash
curl -X POST http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{"action":"create","data":[{"name":"Keyboard","price":49.99,"category":"Electronics","in_stock":true}]}'
```

Update a row by `_row_id`:

```bash
curl -X PATCH http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{"action":"update","data":{"_row_id":1,"price":899.99}}'
```

Delete a row by `_row_id`:

```bash
curl -X DELETE http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{"action":"delete","data":{"_row_id":1}}'
```

## Step 7: Optional Security Setup

Create a superuser:

```bash
adapt addsuperuser . --username admin
```

Create permissions for discovered resources:

```bash
adapt admin create-permissions . __all__
```

List groups and users:

```bash
adapt admin list-groups .
adapt admin list-users .
```

## Step 8: Optional Serve Flags

```bash
adapt serve . --host 127.0.0.1 --port 8000 --debug
```

Read-only mode:

```bash
adapt serve . --readonly
```

## What You Have Running

- Generated dataset API at `/api/products`
- Generated schema at `/schema/products`
- Generated UI at `/ui/products`
- Markdown route at `/readme`
- Optional Python handler route(s) under `/api/reports/*`

## Next Steps

- Continue to the [User Guide](user_guide)
- Review complete routes in the [API Reference](api_reference)
- Use the [Admin Guide](admin_guide) for user/group management

[Previous](installation) | [Next](user_guide) | [Index](index)
