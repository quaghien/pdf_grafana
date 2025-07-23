import os
import argparse
from dotenv import load_dotenv
from pdf2md_pipeline import pdf_to_md
from md2db_pipeline import md2db_with_meta
from text2sql_pipeline import text2sql
from grafana_api_pipeline import create_grafana_panel
import requests
import json

load_dotenv()

GRAFANA_URL = os.getenv('GRAFANA_URL', 'http://localhost:3000')
GRAFANA_API_KEY = os.getenv('GRAFANA_API_KEY')
PG_URL = os.getenv('PG_URL')


def pdf2db_flow(pdf_path, out_dir):
    print("[PDF→DB] Chuyển PDF sang Markdown...")
    md_path = pdf_to_md(pdf_path, out_dir)
    print(f"[PDF→DB] Đã tạo file: {md_path}")
    print("[PDF→DB] Upload dữ liệu vào PostgreSQL và lưu metadata...")
    meta = md2db_with_meta(md_path, PG_URL)
    print(f"[PDF→DB] Đã upload. meta_id: {meta['id']}")
    return meta['id']


def query2dashboard_flow(meta_id, question, panel_title):
    # Lấy schema, evidence từ meta
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    schema = meta['schema']
    evidence = meta['evidence']
    print("[Query→SQL] Sinh SQL từ câu hỏi...")
    sql = text2sql(schema, evidence, question)
    print(f"[Query→SQL] SQL: {sql}")
    print("[Dashboard] Tạo dashboard/panel trên Grafana...")
    uid, url = create_grafana_panel(sql, panel_title)
    print(f"[Dashboard] Đã tạo dashboard UID: {uid}")
    print(f"[Dashboard] Truy cập: {url}")
    # Tải panel về local
    download_all_panels(uid)


def download_all_panels(dashboard_uid):
    headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"}
    # Lấy slug
    resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", headers=headers)
    resp.raise_for_status()
    slug = resp.json()['meta']['slug']
    panels = resp.json()['dashboard']['panels']
    for panel in panels:
        panel_id = panel['id']
        img_url = f"{GRAFANA_URL}/render/d-solo/{dashboard_uid}/{slug}?orgId=1&from=now-6h&to=now&panelId={panel_id}&width=800&height=400&tz=UTC"
        img_resp = requests.get(img_url, headers=headers)
        img_resp.raise_for_status()
        out_path = f"panel_{panel_id}.png"
        with open(out_path, 'wb') as f:
            f.write(img_resp.content)
        print(f"[Panel] Đã tải panel {panel_id} về {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Pipeline PDF→DB hoặc Query→Dashboard→Tải panel")
    subparsers = parser.add_subparsers(dest='command')

    pdf2db_parser = subparsers.add_parser('pdf2db', help='PDF → DB')
    pdf2db_parser.add_argument('--pdf', required=True, help='Đường dẫn file PDF đầu vào')
    pdf2db_parser.add_argument('--out_dir', default='.', help='Thư mục lưu file .md')

    q2dash_parser = subparsers.add_parser('query2dashboard', help='Query → Dashboard → Tải panel')
    q2dash_parser.add_argument('--meta_id', required=True, help='ID upload/meta_id')
    q2dash_parser.add_argument('--question', required=True, help='Câu hỏi tự nhiên cho LLM')
    q2dash_parser.add_argument('--panel_title', default='Auto Panel', help='Tên panel Grafana')
    args = parser.parse_args()

    if args.command == 'pdf2db':
        pdf2db_flow(args.pdf, args.out_dir)
    elif args.command == 'query2dashboard':
        query2dashboard_flow(args.meta_id, args.question, args.panel_title)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 