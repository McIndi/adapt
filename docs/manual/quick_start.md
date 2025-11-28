# Quick Start Guide

This guide will get you up and running with Adapt in minutes.

## Step 1: Install Adapt

```bash
pip install adapt-server
```

## Step 2: Create Your Data Directory

```bash
mkdir adapt-demo
cd adapt-demo
```

## Step 3: Add Sample Data

Create some sample files to demonstrate Adapt's capabilities:

### CSV Dataset
Create `products.csv`:
```csv
id,name,price,category,in_stock
1,Laptop,999.99,Electronics,true
2,Book,19.99,Books,true
3,Headphones,79.99,Electronics,false
4,Notebook,4.99,Stationery,true
5,Mouse,24.99,Electronics,true
```

### Excel Spreadsheet
Create `inventory.xlsx` with a sheet named "Stock" containing:
```csv
product_id,warehouse,quantity,last_updated
1,Warehouse A,50,2024-01-15
2,Warehouse A,25,2024-01-15
3,Warehouse B,0,2024-01-10
4,Warehouse A,100,2024-01-15
5,Warehouse B,75,2024-01-12
```

### Markdown Content
Create `readme.md`:
```markdown
# Welcome to Our Store

This is our product catalog and inventory management system, powered by Adapt.

## Features
- Real-time inventory tracking
- Product catalog management
- Automated reporting
```

### Python Handler
Create `reports.py`:
```python
from fastapi import APIRouter
from typing import List, Dict
import csv

router = APIRouter()

@router.get("/summary")
def get_summary() -> Dict:
    """Get a summary of products and inventory"""
    products = []
    with open('products.csv', 'r') as f:
        reader = csv.DictReader(f)
        products = list(reader)
    
    total_products = len(products)
    in_stock = len([p for p in products if p['in_stock'].lower() == 'true'])
    total_value = sum(float(p['price']) for p in products if p['in_stock'].lower() == 'true')
    
    return {
        "total_products": total_products,
        "in_stock": in_stock,
        "out_of_stock": total_products - in_stock,
        "total_inventory_value": round(total_value, 2)
    }
```

## Step 4: Start the Server

```bash
adapt serve .
```

You'll see output like:
```
INFO: Started server process [12345]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## Step 5: Explore Your Server

Open `http://localhost:8000` in your browser.

### Landing Page
The root URL shows:
- Welcome message
- List of available resources
- Quick start guide
- Links to admin (if superuser)

### DataTables UI
Visit `/ui/products` to see:
- Sortable, searchable table
- Pagination
- Inline editing capabilities
- Add/delete rows

### API Endpoints
Try these API calls:

```bash
# Get all products
curl http://localhost:8000/api/products

# Get product schema
curl http://localhost:8000/schema/products

# Add a new product
curl -X POST http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Keyboard","price":49.99,"category":"Electronics","in_stock":true}'

# Get inventory summary
curl http://localhost:8000/api/reports/summary
```

### Excel Sheets
For multi-sheet Excel files, Adapt creates per-sheet resources:
- `/api/inventory/Stock` - CRUD API for the Stock sheet
- `/ui/inventory/Stock` - DataTables UI for the Stock sheet
- `/schema/inventory/Stock` - Schema for the Stock sheet

### Content Serving
- `/readme` - Renders the Markdown file
- Direct file access for HTML files

## Step 6: Set Up Security (Optional)

For production use, set up authentication:

```bash
# Create a superuser
adapt addsuperuser . --username admin

# Create permissions for your resources
adapt admin create-permissions . products inventory readme reports

# Start server (will prompt for login)
adapt serve .
```

## Step 7: Customize (Optional)

### Custom Schema
Create `.adapt/products.schema.json`:
```json
{
  "type": "object",
  "properties": {
    "id": {"type": "integer", "title": "ID"},
    "name": {"type": "string", "title": "Product Name", "minLength": 1},
    "price": {"type": "number", "title": "Price ($)", "minimum": 0},
    "category": {"type": "string", "title": "Category", "enum": ["Electronics", "Books", "Stationery"]},
    "in_stock": {"type": "boolean", "title": "In Stock"}
  },
  "required": ["name", "price", "category"]
}
```

### Custom UI
Edit `.adapt/products.index.html` to customize the interface.

## What You've Built

In minutes, you've created:
- ✅ REST API for CSV data
- ✅ Web UI for data management
- ✅ Excel sheet APIs
- ✅ Markdown content serving
- ✅ Custom Python endpoints
- ✅ Authentication system
- ✅ Admin interface

## Next Steps

- Explore the [User Guide](user_guide.md) for detailed usage
- Learn about [Plugin Development](plugin_development.md) to extend Adapt
- Set up [Security](security.md) for production
- Check [Configuration](configuration.md) options

## Troubleshooting

### Server Won't Start
- Check if port 8000 is available
- Ensure you have write permissions in the directory
- Try `adapt check .` to diagnose issues

### Files Not Detected
- Ensure files are in the document root (not subdirectories unless configured)
- Check file extensions match supported types
- Restart the server after adding files

### API Returns 403 Forbidden
- You may need to log in or set up permissions
- Check the admin interface for user/group permissions