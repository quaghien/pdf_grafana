import requests
import os
from typing import Optional, Dict, Any
import time
import uuid
import google.generativeai as genai

# Panel configuration templates for financial data
PANEL_TEMPLATES = {
    "table": {
        "type": "table",
        "format": "table",
        "height": 8,
        "width": 24,
        "description": "Best for displaying detailed financial statements with multiple line items"
    },
    "barchart": {
        "type": "barchart",
        "format": "table", 
        "height": 8,
        "width": 16,
        "description": "Best for comparing financial line items or year-over-year comparisons"
    },
    "piechart": {
        "type": "piechart",
        "format": "table",
        "height": 8,
        "width": 12, 
        "description": "Best for showing financial structure (asset composition, liability breakdown, etc.)"
    }
}

def get_panel_recommendation(sql_query: str, panel_title: str) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        return "table"
    
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
You are an expert financial data visualization consultant specializing in Grafana dashboard design for financial reports.

The data comes from financial statements with these tables:
- balance_sheet: Assets, liabilities, equity (ending_2024_vnd, beginning_2024_vnd)
- income_statement: Revenue, expenses, profit (year_2024_vnd, year_2023_vnd)  
- cash_flow_statement: Cash flows from operations, investing, financing (year_2024_vnd, year_2023_vnd)

Analyze the following SQL query and recommend the most appropriate Grafana panel type:

SQL Query:
```sql
{sql_query}
```

Panel Title: "{panel_title}"

Available Panel Types:
1. **table** - {PANEL_TEMPLATES['table']['description']}
2. **barchart** - {PANEL_TEMPLATES['barchart']['description']}
3. **piechart** - {PANEL_TEMPLATES['piechart']['description']}

Financial Analysis Guidelines:
- **barchart**: Choose for comparing financial line items or year-over-year comparisons (2024 vs 2023)
- **piechart**: Choose for financial structure analysis (asset composition, revenue breakdown, expense categories)
- **table**: Choose for detailed financial statements with multiple line items

Consider:
1. Financial statement type (balance sheet, income statement, cash flow)
2. Number of line items (single metric vs multiple items)
3. Comparison type (year-over-year, composition analysis, detailed listing)
4. Financial purpose (KPI monitoring, variance analysis, structure analysis)
5. Data aggregation (single value, grouped data, detailed breakdown)

Response Format:
Return ONLY the panel type name (one word, lowercase). Examples: "table", "barchart", "piechart"

Panel Type:"""

        response = model.generate_content(prompt)
        panel_type = response.text.strip().lower()
        
        if panel_type in PANEL_TEMPLATES:
            return panel_type
        else:
            return "table"
            
    except Exception:
        return "table"

def create_panel_config(panel_type: str, panel_id: int, panel_title: str, sql_query: str, ds_uid: str) -> Dict[str, Any]:
    template = PANEL_TEMPLATES.get(panel_type, PANEL_TEMPLATES["table"])
    
    base_panel = {
        "id": panel_id,
        "type": template["type"],
        "title": panel_title,
        "datasource": {"type": "postgres", "uid": ds_uid},
        "targets": [{
            "format": template["format"],
            "rawSql": sql_query,
            "refId": "A"
        }],
        "fieldConfig": {
            "defaults": {},
            "overrides": []
        },
        "gridPos": {
            "h": template["height"], 
            "w": template["width"], 
            "x": 0, 
            "y": panel_id * 8
        }
    }
    
    # Add specific configurations for certain panel types
    if panel_type == "barchart":
        base_panel["fieldConfig"]["defaults"].update({
            "custom": {
                "lineWidth": 1,
                "fillOpacity": 80,
                "gradientMode": "none",
                "axisPlacement": "auto",
                "axisLabel": "",
                "axisColorMode": "text",
                "axisBorderShow": False,
                "scaleDistribution": {
                    "type": "linear"
                },
                "axisCenteredZero": False,
                "hideFrom": {
                    "tooltip": False,
                    "viz": False,
                    "legend": False
                },
                "thresholdsStyle": {
                    "mode": "off"
                }
            },
            "color": {
                "mode": "palette-classic"
            },
            "mappings": [],
            "thresholds": {
                "mode": "absolute",
                "steps": [
                    {
                        "value": None,
                        "color": "green"
                    },
                    {
                        "value": 80,
                        "color": "red"
                    }
                ]
            },
            "unit": "currency:₫"
        })
        
        # Add bar chart specific options
        base_panel["options"] = {
            "orientation": "horizontal",
            "xTickLabelRotation": 0,
            "xTickLabelSpacing": 0,
            "showValue": "never",
            "stacking": "none",
            "groupWidth": 0.7,
            "barWidth": 0.97,
            "barRadius": 0,
            "fullHighlight": False,
            "tooltip": {
                "mode": "single",
                "sort": "none"
            },
            "legend": {
                "showLegend": True,
                "displayMode": "list",
                "placement": "right",
                "calcs": []
            }
        }
    
    elif panel_type == "piechart":
        base_panel["fieldConfig"]["defaults"].update({
            "custom": {
                "hideFrom": {
                    "legend": False,
                    "tooltip": False,
                    "vis": False
                }
            },
            "color": {"mode": "palette-classic"},
            "unit": "currency:₫",
            "mappings": []
        })
        base_panel["options"] = {
            "reduceOptions": {
                "values": True,  # Changed from False to True
                "calcs": ["lastNotNull"],
                "fields": ""
            },
            "pieType": "pie",
            "tooltip": {
                "mode": "single",
                "sort": "none"
            },
            "legend": {
                "showLegend": True,  # Show legend to display names
                "displayMode": "table", 
                "placement": "right",
                "values": ["value", "percent"],
                "calcs": []
            },
            "displayLabels": ["percent"]  # Show both name and percent on pie slices
        }
    
    elif panel_type == "table":
        base_panel["fieldConfig"]["defaults"].update({
            "unit": "currency:₫"
        })
    
    return base_panel

def create_grafana_panel(sql_query: str, panel_title: str, dashboard_uid: str = None, grafana_url: str = None, grafana_api_key: str = None, datasource_name: str = "grafana-postgresql-datasource", panel_type: str = None):
    if grafana_url is None:
        grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    if grafana_api_key is None:
        grafana_api_key = os.getenv("GRAFANA_API_KEY")
    if not grafana_api_key:
        raise RuntimeError("Missing GRAFANA_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {grafana_api_key}",
        "Content-Type": "application/json"
    }
    
    # Get panel type - use provided type or get AI recommendation
    if panel_type is None:
        panel_type = get_panel_recommendation(sql_query, panel_title)
    
    print(f"Using panel type: {panel_type}")
    
    # Get datasource uid
    resp = requests.get(f"{grafana_url}/api/datasources", headers=headers)
    resp.raise_for_status()
    datasources = resp.json()
    
    ds_uid = None
    for ds in datasources:
        if ds["name"] == datasource_name:
            ds_uid = ds["uid"]
            break
    if ds_uid is None:
        raise RuntimeError(f"Datasource {datasource_name} not found")
    
    # Create dashboard if needed
    if dashboard_uid is None:
        unique_suffix = str(uuid.uuid4())[:8]
        dashboard = {
            "dashboard": {
                "id": None,
                "uid": None,
                "title": f"Auto Dashboard {unique_suffix}",
                "panels": [],
                "timezone": "browser",
                "schemaVersion": 37,
                "version": 0,
                "folderId": 0
            },
            "overwrite": True
        }
        resp = requests.post(f"{grafana_url}/api/dashboards/db", headers=headers, json=dashboard)
        resp.raise_for_status()
        dashboard_uid = resp.json()["uid"]
        
        # Wait for dashboard to be ready
        for i in range(10):
            resp = requests.get(f"{grafana_url}/api/dashboards/uid/{dashboard_uid}", headers=headers)
            if resp.status_code == 200:
                break
            time.sleep(1) 
        else:
            raise RuntimeError(f"Dashboard not accessible after creation")
    
    # Get current dashboard
    resp = requests.get(f"{grafana_url}/api/dashboards/uid/{dashboard_uid}", headers=headers)
    resp.raise_for_status()
    dashboard = resp.json()["dashboard"]
    
    # Find panel position
    panel_id = max([p["id"] for p in dashboard.get("panels", [])], default=0) + 1
    
    # Create panel based on recommended type
    panel = create_panel_config(panel_type, panel_id, panel_title, sql_query, ds_uid)
    
    dashboard.setdefault("panels", []).append(panel)

    if "version" not in dashboard or dashboard["version"] is None:
        dashboard["version"] = 0
    else:
        dashboard["version"] += 1

    # Update dashboard
    payload = {
        "dashboard": dashboard,
        "overwrite": True
    }
    resp = requests.post(f"{grafana_url}/api/dashboards/db", headers=headers, json=payload)
    resp.raise_for_status()
    
    return dashboard["uid"], f"{grafana_url}/d/{dashboard['uid']}" 