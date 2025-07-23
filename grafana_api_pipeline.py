import requests
import os
from typing import Optional
import time
import uuid

def create_grafana_panel(sql_query: str, panel_title: str, dashboard_uid: str = None, grafana_url: str = None, grafana_api_key: str = None, datasource_name: str = "grafana-postgresql-datasource"):
    if grafana_url is None:
        grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    if grafana_api_key is None:
        grafana_api_key = os.getenv("GRAFANA_API_KEY")
    if not grafana_api_key:
        raise RuntimeError("Thiếu GRAFANA_API_KEY trong .env")
    headers = {
        "Authorization": f"Bearer {grafana_api_key}",
        "Content-Type": "application/json"
    }
    # Lấy datasource id
    resp = requests.get(f"{grafana_url}/api/datasources", headers=headers)
    resp.raise_for_status()
    datasources = resp.json()
    # Lấy datasource uid (không phải id)
    ds_uid = None
    for ds in datasources:
        if ds["name"] == datasource_name:
            ds_uid = ds["uid"]
            break
    if ds_uid is None:
        raise RuntimeError(f"Không tìm thấy datasource {datasource_name} trên Grafana")
    # Nếu chưa có dashboard, tạo mới
    if dashboard_uid is None:
        # Tạo title unique để tránh conflict
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
                "folderId": 0  # Đặt trong General folder
            },
            "overwrite": True  # Cho phép overwrite để tránh conflict
        }
        resp = requests.post(f"{grafana_url}/api/dashboards/db", headers=headers, json=dashboard)
        if resp.status_code != 200:
            print(f"Error creating dashboard: {resp.status_code}")
            print(f"Response: {resp.text}")
            resp.raise_for_status()
        dashboard_uid = resp.json()["uid"]
        
        # Retry để đảm bảo dashboard sẵn sàng sau khi tạo
        max_retries = 10
        for i in range(max_retries):
            resp = requests.get(f"{grafana_url}/api/dashboards/uid/{dashboard_uid}", headers=headers)
            if resp.status_code == 200:
                break
            time.sleep(1) 
        else:
            raise RuntimeError(f"Không thể truy cập dashboard sau khi tạo (uid={dashboard_uid})")
    # Lấy dashboard hiện tại
    resp = requests.get(f"{grafana_url}/api/dashboards/uid/{dashboard_uid}", headers=headers)
    resp.raise_for_status()
    dashboard = resp.json()["dashboard"]
    # Tìm vị trí panel mới
    panel_id = max([p["id"] for p in dashboard.get("panels", [])], default=0) + 1
    # ==== MẪU PANEL CÓ THỂ THAY ĐỔI ====
    # Mẫu 1: Table (bảng)
    # panel = {
    #     "id": panel_id,
    #     "type": "table",
    #     "title": panel_title,
    #     "datasource": {"type": "postgres", "uid": ds_uid},
    #     "targets": [{
    #         "format": "table",
    #         "rawSql": sql_query,
    #         "refId": "A"
    #     }],
    #     "fieldConfig": {"defaults": {}, "overrides": []},
    #     "gridPos": {"h": 8, "w": 24, "x": 0, "y": panel_id * 8}
    # }
    #
    # Mẫu 2: Graph (biểu đồ đường/thời gian)
    # panel = {
    #     "id": panel_id,
    #     "type": "graph",
    #     "title": panel_title,
    #     "datasource": {"type": "postgres", "uid": ds_uid},
    #     "targets": [{
    #         "format": "time_series",
    #         "rawSql": sql_query,
    #         "refId": "A"
    #     }],
    #     "fieldConfig": {"defaults": {}, "overrides": []},
    #     "gridPos": {"h": 8, "w": 24, "x": 0, "y": panel_id * 8}
    # }
    #
    # Mẫu 3: Stat (số liệu tổng hợp)
    # panel = {
    #     "id": panel_id,
    #     "type": "stat",
    #     "title": panel_title,
    #     "datasource": {"type": "postgres", "uid": ds_uid},
    #     "targets": [{
    #         "format": "time_series",  # hoặc "table" nếu trả về 1 giá trị
    #         "rawSql": sql_query,
    #         "refId": "A"
    #     }],
    #     "fieldConfig": {"defaults": {}, "overrides": []},
    #     "gridPos": {"h": 4, "w": 8, "x": 0, "y": panel_id * 4}
    # }
    #
    # Mẫu 4: Pie chart (biểu đồ tròn, cần plugin Pie Chart)
    # panel = {
    #     "id": panel_id,
    #     "type": "piechart",
    #     "title": panel_title,
    #     "datasource": {"type": "postgres", "uid": ds_uid},
    #     "targets": [{
    #         "format": "table",
    #         "rawSql": sql_query,
    #         "refId": "A"
    #     }],
    #     "fieldConfig": {"defaults": {}, "overrides": []},
    #     "gridPos": {"h": 8, "w": 8, "x": 0, "y": panel_id * 8}
    # }
    # ==== HẾT MẪU ====

    # Panel mặc định: Table
    panel = {
        "id": panel_id,
        "type": "table",  # <-- Thay 'table' bằng loại bạn muốn
        "title": panel_title,
        "datasource": {"type": "postgres", "uid": ds_uid},
        "targets": [{
            "format": "table",
            "rawSql": sql_query,
            "refId": "A"
        }],
        "fieldConfig": {
            "defaults": {},
            "overrides": []
        },
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": panel_id * 8}
    }
    dashboard.setdefault("panels", []).append(panel)

    if "version" not in dashboard or dashboard["version"] is None:
        dashboard["version"] = 0
    else:
        dashboard["version"] += 1

    # Cập nhật dashboard
    payload = {
        "dashboard": dashboard,
        "overwrite": True
    }
    resp = requests.post(f"{grafana_url}/api/dashboards/db", headers=headers, json=payload)
    resp.raise_for_status()
    return dashboard["uid"], f"{grafana_url}/d/{dashboard['uid']}"

# Có thể import và gọi hàm create_grafana_panel để tạo dashboard/panel từ SQL query 