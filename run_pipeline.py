import os
import argparse
from dotenv import load_dotenv
from pdf2md_pipeline import pdf_to_md
from md2db_pipeline import md2db_with_meta
from text2sql_pipeline import text2sql
from grafana_api_pipeline import create_grafana_panel
import requests
import json
from datetime import datetime

load_dotenv()

GRAFANA_URL = os.getenv('GRAFANA_URL', 'http://localhost:3000')
GRAFANA_API_KEY = os.getenv('GRAFANA_API_KEY')
PG_URL = os.getenv('PG_URL')


def pdf2db_flow(pdf_path, out_dir):
    print("Converting PDF to Markdown...")
    md_path = pdf_to_md(pdf_path, out_dir)
    print(f"Created: {md_path}")
    print("Uploading to PostgreSQL...")
    meta = md2db_with_meta(md_path, PG_URL)
    print(f"Meta ID: {meta['id']}")
    return meta['id']


def download_single_panel(dashboard_uid, panel_id, panel_title):
    import time
    
    if not GRAFANA_API_KEY:
        print("ERROR: GRAFANA_API_KEY not configured")
        return
    
    headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"}
    time.sleep(2)
    
    try:
        resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", headers=headers)
        resp.raise_for_status()
        dashboard_data = resp.json()
        slug = dashboard_data['meta']['slug']
        
        os.makedirs("panel", exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        panel_title_clean = panel_title.replace(' ', '_').replace('/', '_')
        
        img_url = f"{GRAFANA_URL}/render/d-solo/{dashboard_uid}/{slug}?orgId=1&from=now-2y&to=now&panelId={panel_id}&width=1200&height=600&tz=UTC&timeout=30"
        
        img_resp = requests.get(img_url, headers=headers, timeout=60)
        img_resp.raise_for_status()
        
        safe_title = "".join(c for c in panel_title_clean if c.isalnum() or c in ('_', '-'))[:50]
        out_path = f"panel/panel_{panel_id}_{safe_title}_{timestamp}.png"
        
        with open(out_path, 'wb') as f:
            f.write(img_resp.content)
        
        return out_path
        
    except Exception as e:
        print(f"Error downloading panel: {e}")
        return None


def auto_generate_panel_title(question: str) -> str:
    """Generate panel title from question or SQL query"""
    import re
    
    if question.strip().upper().startswith('SELECT'):
        table_match = re.search(r'FROM\s+(\w+)', question, re.IGNORECASE)
        table_name = table_match.group(1) if table_match else "data"
        
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', question, re.IGNORECASE | re.DOTALL)
        if select_match:
            columns_part = select_match.group(1)
            columns_part = re.sub(r'\s+AS\s+\w+', '', columns_part, flags=re.IGNORECASE)
            columns_part = re.sub(r'--.*', '', columns_part)
            columns = [col.strip() for col in columns_part.split(',')][:2]
            main_cols = [col.split('.')[1] if '.' in col else col for col in columns]
            
            title = f"{table_name.replace('_', ' ').title()} Analysis"
            if len(main_cols) > 1:
                title = f"{main_cols[0].replace('_', ' ').title()} Analysis"
                
            return title
    
    question = re.sub(r'^(what|how|show|find|get|list|display)\s+', '', question.lower())
    question = re.sub(r'\s+(for|in|of|from|with|by)\s+\d{4}', '', question)
    
    words = question.split()[:4]
    title = ' '.join(word.capitalize() for word in words)
    
    return title if title.strip() else "Financial Data"

def question2panel_flow(meta_id, output_json="dashboard_panels.json"):
    """Interactive question to panel flow"""
    
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except FileNotFoundError:
        print(f"Error: Metadata file not found: {meta_path}")
        return

    schema = meta['schema']
    evidence = meta['evidence']
    tables = meta.get('tables', [])
    
    dashboard_data = {"meta_id": meta_id, "created_at": datetime.now().isoformat(), 
                     "dashboard_uid": None, "dashboard_url": None, "panels": []}
    
    if os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if existing.get('meta_id') == meta_id:
                    dashboard_data = existing
        except:
            pass
    
    print("Interactive Dashboard Creation")
    print("Commands: 'exit' to quit")
    panel_counter = len(dashboard_data['panels']) + 1
    
    while True:
        try:
            question = input(f"\n[Panel {panel_counter}] Question: ").strip()
            
            if question.lower() in ['exit', 'quit']:
                break
            elif not question:
                continue
            
            panel_title = auto_generate_panel_title(question)
            print(f"Processing: {question} -> {panel_title}")
            
            sql = text2sql(schema, evidence, question)
            print(f"SQL: {sql}")
            
            from grafana_api_pipeline import get_panel_recommendation
            panel_type = get_panel_recommendation(sql, panel_title)
            
            try:
                dashboard_uid, dashboard_url = create_grafana_panel(sql, panel_title, dashboard_data.get('dashboard_uid'), panel_type=panel_type)
                dashboard_data.update({'dashboard_uid': dashboard_uid, 'dashboard_url': dashboard_url})
                
                resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", 
                                  headers={"Authorization": f"Bearer {GRAFANA_API_KEY}"})
                resp.raise_for_status()
                current_panels = resp.json()["dashboard"].get("panels", [])
                panel_id = max([p["id"] for p in current_panels]) if current_panels else panel_counter
                
                downloaded_file = download_single_panel(dashboard_uid, panel_id, panel_title)
                
                panel_entry = {
                    "id": panel_counter, "panel_id": panel_id, 
                    "question": question, "title": panel_title, "sql": sql, 
                    "recommended_panel_type": panel_type, "dashboard_uid": dashboard_uid, 
                    "timestamp": datetime.now().isoformat(), "downloaded_file": downloaded_file
                }
                dashboard_data['panels'].append(panel_entry)
                dashboard_data['last_updated'] = datetime.now().isoformat()
                
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
                
                print(f"Created panel #{panel_counter}: {panel_title}")
                if downloaded_file:
                    print(f"Downloaded: {downloaded_file}")
                panel_counter += 1
                
            except Exception as e:
                print(f"Error: {e}")
                continue
            
        except KeyboardInterrupt:
            print("\nStopped")
            break
    
    downloaded = len([p for p in dashboard_data['panels'] if p.get('downloaded_file')])
    print(f"\nSummary: {len(dashboard_data['panels'])} panels, {downloaded} downloaded")
    if dashboard_data.get('dashboard_url'):
        print(f"Dashboard: {dashboard_data['dashboard_url']}")


def main():
    parser = argparse.ArgumentParser(description="PDF to Dashboard Pipeline")
    subparsers = parser.add_subparsers(dest='command')

    # PDF to DB
    pdf2db_parser = subparsers.add_parser('pdf2db', help='Convert PDF to database')
    pdf2db_parser.add_argument('--pdf', required=True, help='PDF file path')
    pdf2db_parser.add_argument('--out_dir', default='.', help='Output directory')

    # Interactive question to dashboard
    question2panel_parser = subparsers.add_parser('question2panel', help='Interactive dashboard creation from questions')
    question2panel_parser.add_argument('--meta_id', required=True, help='Meta ID')
    question2panel_parser.add_argument('--output', default='dashboard_panels.json', help='Output JSON file')

    args = parser.parse_args()

    if args.command == 'pdf2db':
        pdf2db_flow(args.pdf, args.out_dir)
    elif args.command == 'question2panel':
        question2panel_flow(args.meta_id, args.output)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 