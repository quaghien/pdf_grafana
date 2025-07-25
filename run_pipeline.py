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
    print(f"Created file: {md_path}")
    print("Uploading data to PostgreSQL...")
    meta = md2db_with_meta(md_path, PG_URL)
    print(f"Uploaded. meta_id: {meta['id']}")
    return meta['id']


def query2dashboard_flow(meta_id, question, panel_title):
    # Load metadata
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    schema = meta['schema']
    evidence = meta['evidence']
    tables = meta.get('tables', [])
    
    print(f"Loaded {len(tables)} tables from metadata")
    
    # Generate SQL
    print("Generating SQL...")
    sql = text2sql(schema, evidence, question)
    print(f"SQL: {sql}")
    
    # Get AI recommendation
    from grafana_api_pipeline import get_panel_recommendation
    panel_type = get_panel_recommendation(sql, panel_title)
    print(f"AI recommended: {panel_type}")
    
    # Create dashboard/panel
    print("Creating dashboard/panel...")
    uid, url = create_grafana_panel(sql, panel_title, panel_type=panel_type)
    print(f"Dashboard UID: {uid}")
    print(f"URL: {url}")
    
    # Download panels
    download_all_panels(uid)


def download_all_panels(dashboard_uid):
    import time
    from datetime import datetime
    
    if not GRAFANA_API_KEY:
        print("ERROR: GRAFANA_API_KEY not configured")
        return
    
    headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"}
    time.sleep(3)  # Wait for panel to load
    
    try:
        resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", headers=headers)
        resp.raise_for_status()
        dashboard_data = resp.json()
        slug = dashboard_data['meta']['slug']
        panels = dashboard_data['dashboard']['panels']
        
        if not panels:
            print("No panels found in dashboard")
            return
        
    except Exception as e:
        print(f"Error getting dashboard info: {e}")
        return
    
    # Create panel folder
    os.makedirs("panel", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    success_count = 0
    
    for panel in panels:
        panel_id = panel['id']
        panel_title = panel.get('title', f'Panel_{panel_id}').replace(' ', '_').replace('/', '_')
        
        img_url = f"{GRAFANA_URL}/render/d-solo/{dashboard_uid}/{slug}?orgId=1&from=now-2y&to=now&panelId={panel_id}&width=1200&height=600&tz=UTC&timeout=30"
        
        try:
            img_resp = requests.get(img_url, headers=headers, timeout=60)
            img_resp.raise_for_status()
            
            if 'image' not in img_resp.headers.get('content-type', ''):
                continue
            
            safe_title = "".join(c for c in panel_title if c.isalnum() or c in ('_', '-'))[:50]
            out_path = f"panel/panel_{panel_id}_{safe_title}_{timestamp}.png"
            
            with open(out_path, 'wb') as f:
                f.write(img_resp.content)
            
            print(f"Downloaded: {out_path}")
            success_count += 1
            
        except Exception as e:
            print(f"Error downloading panel {panel_id}: {e}")
    
    print(f"Downloaded {success_count}/{len(panels)} panels")


def download_single_panel(dashboard_uid, panel_id, panel_title):
    import time
    from datetime import datetime
    
    if not GRAFANA_API_KEY:
        print("ERROR: GRAFANA_API_KEY not configured")
        return
    
    headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"}
    time.sleep(2)  # Brief wait for panel to load
    
    try:
        resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", headers=headers)
        resp.raise_for_status()
        dashboard_data = resp.json()
        slug = dashboard_data['meta']['slug']
        
    except Exception as e:
        print(f"Error getting dashboard info: {e}")
        return
    
    # Create panel folder
    os.makedirs("panel", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    panel_title_clean = panel_title.replace(' ', '_').replace('/', '_')
    
    img_url = f"{GRAFANA_URL}/render/d-solo/{dashboard_uid}/{slug}?orgId=1&from=now-2y&to=now&panelId={panel_id}&width=1200&height=600&tz=UTC&timeout=30"
    
    try:
        img_resp = requests.get(img_url, headers=headers, timeout=60)
        img_resp.raise_for_status()
        
        if 'image' not in img_resp.headers.get('content-type', ''):
            print(f"Error: Response is not an image for panel {panel_id}")
            return
        
        safe_title = "".join(c for c in panel_title_clean if c.isalnum() or c in ('_', '-'))[:50]
        out_path = f"panel/panel_{panel_id}_{safe_title}_{timestamp}.png"
        
        with open(out_path, 'wb') as f:
            f.write(img_resp.content)
        
        return out_path
        
    except Exception as e:
        print(f"Error downloading panel {panel_id}: {e}")
        return None


def list_available_meta():
    meta_dir = "meta_uploads"
    if not os.path.exists(meta_dir):
        print(f"Directory {meta_dir} does not exist")
        return []
    
    meta_files = [f for f in os.listdir(meta_dir) if f.startswith('meta_') and f.endswith('.json')]
    if not meta_files:
        print(f"No metadata files found in {meta_dir}")
        return []
    
    print(f"Found {len(meta_files)} meta file(s):")
    meta_ids = []
    for meta_file in sorted(meta_files):
        meta_id = meta_file.replace('meta_', '').replace('.json', '')
        meta_ids.append(meta_id)
        
        try:
            with open(os.path.join(meta_dir, meta_file), 'r', encoding='utf-8') as f:
                meta = json.load(f)
                created_at = meta.get('uploaded_at', 'N/A')
                tables = meta.get('tables', [])
                num_tables = len(tables)
                md_path = meta.get('md_path', 'N/A')
                print(f"  Meta ID: {meta_id}")
                print(f"    Created: {created_at}")
                print(f"    Tables: {num_tables}")
                print(f"    MD Path: {md_path}")
        except Exception as e:
            print(f"  Meta ID: {meta_id} (error reading: {e})")
    
    return meta_ids


def interactive_query_flow(meta_id, output_json="sql_queries.json"):
    # Load metadata
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except FileNotFoundError:
        print(f"Error: Metadata file not found: {meta_path}")
        print("Available meta_ids:")
        available_metas = list_available_meta()
        if not available_metas:
            print("No meta_id found. Run 'python run_pipeline.py pdf2db --pdf <file.pdf>' first")
        return

    schema = meta['schema']
    evidence = meta['evidence']
    tables = meta.get('tables', [])
    
    print(f"Loaded metadata: {len(tables)} tables")
    if tables:
        print(f"Table names: {', '.join(tables)}")
    
    # Load existing queries
    queries_data = {
        "meta_id": meta_id,
        "created_at": datetime.now().isoformat(),
        "queries": []
    }
    
    if os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if existing_data.get('meta_id') == meta_id:
                    queries_data = existing_data
                    print(f"Loaded {len(queries_data['queries'])} existing SQL queries")
                else:
                    print(f"File {output_json} has different meta_id, creating new file")
        except Exception as e:
            print(f"Warning: Error reading {output_json}: {e}")
    
    print("Interactive SQL Query Creation")
    print("Commands: 'exit', 'list', 'tables', 'info'")
    
    query_counter = len(queries_data['queries']) + 1
    
    while True:
        try:
            question = input(f"\n[Q{query_counter}] Question: ").strip()
            
            if question.lower() in ['exit', 'quit']:
                print("Exited interactive mode")
                break
            
            if question.lower() == 'list':
                print(f"Created queries: {len(queries_data['queries'])}")
                for i, q in enumerate(queries_data['queries'], 1):
                    print(f"  {i}. {q['question']}")
                    print(f"     SQL: {q['sql'][:100]}{'...' if len(q['sql']) > 100 else ''}")
                continue
            
            if question.lower() == 'tables':
                print(f"Available tables: {', '.join(tables) if tables else 'None'}")
                continue
            
            if question.lower() == 'info':
                print(f"Meta ID: {meta_id}")
                print(f"MD path: {meta.get('md_path', 'N/A')}")
                print(f"Upload time: {meta.get('uploaded_at', 'N/A')}")
                print(f"Tables: {len(tables)}")
                continue
            
            if not question:
                print("Question cannot be empty")
                continue
            
            print(f"Creating SQL query for: {question}")
            
            # Generate SQL
            sql = text2sql(schema, evidence, question)
            print(f"SQL: {sql}")
            
            # Save query
            query_entry = {
                "id": query_counter,
                "question": question,
                "sql": sql,
                "timestamp": datetime.now().isoformat()
            }
            
            queries_data['queries'].append(query_entry)
            
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(queries_data, f, ensure_ascii=False, indent=2)
            
            print(f"Saved SQL query #{query_counter} to {output_json}")
            query_counter += 1
            
        except KeyboardInterrupt:
            print("\nStopped by Ctrl+C")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print(f"\nTotal created: {len(queries_data['queries'])} SQL queries")
    print(f"Queries saved in: {output_json}")


def auto_generate_panel_title(question: str) -> str:
    """Generate panel title from question or SQL query"""
    import re
    
    # Check if this is a SQL query
    if question.strip().upper().startswith('SELECT'):
        # Extract table name from SQL
        table_match = re.search(r'FROM\s+(\w+)', question, re.IGNORECASE)
        table_name = table_match.group(1) if table_match else "data"
        
        # Extract main columns (not including AS aliases)
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', question, re.IGNORECASE | re.DOTALL)
        if select_match:
            columns_part = select_match.group(1)
            # Remove AS aliases and comments
            columns_part = re.sub(r'\s+AS\s+\w+', '', columns_part, flags=re.IGNORECASE)
            columns_part = re.sub(r'--.*', '', columns_part)
            # Get first few column names
            columns = [col.strip() for col in columns_part.split(',')][:2]
            main_cols = [col.split('.')[1] if '.' in col else col for col in columns]
            
            # Create meaningful title
            title = f"{table_name.replace('_', ' ').title()} Analysis"
            if len(main_cols) > 1:
                title = f"{main_cols[0].replace('_', ' ').title()} Analysis"
                
            return title
    
    # Original logic for non-SQL questions
    question = re.sub(r'^(what|how|show|find|get|list|display)\s+', '', question.lower())
    question = re.sub(r'\s+(for|in|of|from|with|by)\s+\d{4}', '', question)
    
    words = question.split()[:4]
    title = ' '.join(word.capitalize() for word in words)
    
    return title if title.strip() else "Financial Data"

def interactive_query2dashboard_flow(meta_id, output_json="dashboard_panels.json"):
    """Simplified interactive question to dashboard flow"""
    import requests
    
    # Load metadata
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except FileNotFoundError:
        print(f"Error: Metadata file not found: {meta_path}")
        list_available_meta()
        return

    schema = meta['schema']
    evidence = meta['evidence']
    tables = meta.get('tables', [])
    print(f"Loaded: {len(tables)} tables")
    
    # Load/create dashboard data
    dashboard_data = {"meta_id": meta_id, "created_at": datetime.now().isoformat(), 
                     "dashboard_uid": None, "dashboard_url": None, "panels": []}
    
    if os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if existing.get('meta_id') == meta_id:
                    dashboard_data = existing
                    print(f"Loaded {len(dashboard_data['panels'])} existing panels")
        except Exception as e:
            print(f"Warning: {e}")
    
    print("Interactive Dashboard Creation - Commands: 'list', 'download', 'tables', 'info', 'exit'")
    panel_counter = len(dashboard_data['panels']) + 1
    
    while True:
        try:
            question = input(f"\n[Panel {panel_counter}] Question: ").strip()
            
            # Handle commands
            if question.lower() in ['exit', 'quit']:
                break
            elif question.lower() == 'list':
                for i, p in enumerate(dashboard_data['panels'], 1):
                    status = "✓" if p.get('downloaded_file') else "✗"
                    print(f"  {i}. {p['title']} [{status}] - {p.get('recommended_panel_type', 'auto')}")
                continue
            elif question.lower() == 'download':
                if dashboard_data.get('dashboard_uid'):
                    download_all_panels(dashboard_data['dashboard_uid'])
                    print("Downloaded all panels")
                else:
                    print("No dashboard to download")
                continue
            elif question.lower() == 'tables':
                print(f"Tables: {', '.join(tables) if tables else 'None'}")
                continue
            elif question.lower() == 'info':
                print(f"Meta: {meta_id}, Panels: {len(dashboard_data['panels'])}, "
                      f"Dashboard: {dashboard_data.get('dashboard_uid', 'Not created')}")
                continue
            elif not question:
                print("Question cannot be empty")
                continue
            
            # Process question
            panel_title = auto_generate_panel_title(question)
            print(f"Processing: {question} -> {panel_title}")
            
            # Generate SQL and create panel
            sql = text2sql(schema, evidence, question)
            print(f"SQL: {sql}")
            
            from grafana_api_pipeline import get_panel_recommendation
            panel_type = get_panel_recommendation(sql, panel_title)
            print(f"AI: {panel_type}")
            
            try:
                dashboard_uid, dashboard_url = create_grafana_panel(sql, panel_title, dashboard_data.get('dashboard_uid'), panel_type=panel_type)
                dashboard_data.update({'dashboard_uid': dashboard_uid, 'dashboard_url': dashboard_url})
                
                # Get panel ID and download
                resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", 
                                  headers={"Authorization": f"Bearer {GRAFANA_API_KEY}"})
                resp.raise_for_status()
                current_panels = resp.json()["dashboard"].get("panels", [])
                panel_id = max([p["id"] for p in current_panels]) if current_panels else panel_counter
                
                downloaded_file = download_single_panel(dashboard_uid, panel_id, panel_title)
                
                # Save panel data
                panel_entry = {
                    "id": panel_counter, "panel_id": panel_id, "question": question, "title": panel_title,
                    "sql": sql, "recommended_panel_type": panel_type, "dashboard_uid": dashboard_uid,
                    "timestamp": datetime.now().isoformat(), "downloaded_file": downloaded_file
                }
                dashboard_data['panels'].append(panel_entry)
                dashboard_data['last_updated'] = datetime.now().isoformat()
                
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
                
                print(f"Created panel #{panel_counter}: {panel_title}")
                print(f"Downloaded: {downloaded_file}" if downloaded_file else "Download failed")
                panel_counter += 1
                
            except Exception as e:
                print(f"Error: {e}")
                continue
            
        except KeyboardInterrupt:
            print("\nStopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    # Summary
    downloaded = len([p for p in dashboard_data['panels'] if p.get('downloaded_file')])
    print(f"\nSummary: {len(dashboard_data['panels'])} panels, {downloaded} downloaded")
    if dashboard_data.get('dashboard_url'):
        print(f"Dashboard: {dashboard_data['dashboard_url']}")


def sql2panel_flow(meta_id, sql_query, panel_title=None):
    """Direct SQL to panel flow"""
    import requests
    
    # Load metadata for context
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        tables = meta.get('tables', [])
        print(f"Using metadata: {len(tables)} tables")
    except FileNotFoundError:
        print(f"Error: Metadata file not found: {meta_path}")
        return
    
    # Auto-generate title if not provided
    if not panel_title:
        panel_title = auto_generate_panel_title(sql_query)
    
    print(f"SQL: {sql_query}")
    print(f"Title: {panel_title}")
    
    # Get AI recommendation
    from grafana_api_pipeline import get_panel_recommendation
    panel_type = get_panel_recommendation(sql_query, panel_title)
    print(f"AI recommended: {panel_type}")
    
    # Create panel with specific type
    print("Creating panel...")
    try:
        dashboard_uid, dashboard_url = create_grafana_panel(sql_query, panel_title, panel_type=panel_type)
        print(f"Created: {dashboard_url}")
        
        # Get panel ID
        resp = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}", 
                          headers={"Authorization": f"Bearer {GRAFANA_API_KEY}"})
        resp.raise_for_status()
        current_dashboard = resp.json()["dashboard"]
        panel_id = max([p["id"] for p in current_dashboard.get("panels", [])]) if current_dashboard.get("panels") else 1
        
        # Download panel
        print("Downloading...")
        downloaded_file = download_single_panel(dashboard_uid, panel_id, panel_title)
        if downloaded_file:
            print(f"Downloaded: {downloaded_file}")
        else:
            print("Download failed")
            
    except Exception as e:
        print(f"Error: {e}")


def interactive_sql_flow(meta_id):
    """Interactive SQL input flow"""
    import requests
    
    # Load metadata
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        tables = meta.get('tables', [])
        print(f"Loaded metadata: {len(tables)} tables - {', '.join(tables) if tables else 'None'}")
    except FileNotFoundError:
        print(f"Error: Metadata file not found: {meta_path}")
        list_available_meta()
        return
    
    print("Interactive SQL Panel Creation")
    print("Commands: 'exit', 'tables'")
    
    counter = 1
    while True:
        try:
            print(f"\n--- Panel {counter} ---")
            
            # Get SQL
            sql_query = input("SQL Query: ").strip()
            if sql_query.lower() in ['exit', 'quit']:
                break
            if sql_query.lower() == 'tables':
                print(f"Available tables: {', '.join(tables) if tables else 'None'}")
                continue
            if not sql_query:
                print("SQL query cannot be empty")
                continue
            
            # Get title (optional)
            auto_title = auto_generate_panel_title(sql_query)
            panel_title = input(f"Panel title (Enter = '{auto_title}'): ").strip()
            if not panel_title:
                panel_title = auto_title
            
            # Create and download
            sql2panel_flow(meta_id, sql_query, panel_title)
            counter += 1
            
        except KeyboardInterrupt:
            print("\nStopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print(f"Created {counter-1} panels")


def main():
    parser = argparse.ArgumentParser(description="PDF to Dashboard Pipeline")
    subparsers = parser.add_subparsers(dest='command')

    # PDF to DB
    pdf2db_parser = subparsers.add_parser('pdf2db', help='Convert PDF to database')
    pdf2db_parser.add_argument('--pdf', required=True, help='PDF file path')
    pdf2db_parser.add_argument('--out_dir', default='.', help='Output directory')

    # Single query to dashboard
    q2dash_parser = subparsers.add_parser('query2dashboard', help='Natural language question to dashboard')
    q2dash_parser.add_argument('--meta_id', required=True, help='Meta ID')
    q2dash_parser.add_argument('--question', required=True, help='Natural language question')
    q2dash_parser.add_argument('--panel_title', default='Auto Panel', help='Panel title')

    # Direct SQL to panel
    sql_parser = subparsers.add_parser('sql2panel', help='Direct SQL to panel')
    sql_parser.add_argument('--meta_id', required=True, help='Meta ID')
    sql_parser.add_argument('--sql_query', required=True, help='SQL query')
    sql_parser.add_argument('--panel_title', help='Panel title (auto if not provided)')

    # Interactive modes
    interactive_parser = subparsers.add_parser('interactive', help='Interactive SQL query creation')
    interactive_parser.add_argument('--meta_id', required=True, help='Meta ID')
    interactive_parser.add_argument('--output', default='sql_queries.json', help='Output JSON file')

    interactive_q2dash_parser = subparsers.add_parser('interactive_q2dash', help='Interactive dashboard creation (questions)')
    interactive_q2dash_parser.add_argument('--meta_id', required=True, help='Meta ID')
    interactive_q2dash_parser.add_argument('--output', default='dashboard_panels.json', help='Output JSON file')

    interactive_sql_parser = subparsers.add_parser('interactive_sql', help='Interactive dashboard creation (SQL)')
    interactive_sql_parser.add_argument('--meta_id', required=True, help='Meta ID')

    # Utilities
    list_parser = subparsers.add_parser('list', help='List available meta IDs')

    args = parser.parse_args()

    if args.command == 'pdf2db':
        pdf2db_flow(args.pdf, args.out_dir)
    elif args.command == 'query2dashboard':
        query2dashboard_flow(args.meta_id, args.question, args.panel_title)
    elif args.command == 'sql2panel':
        sql2panel_flow(args.meta_id, args.sql_query, args.panel_title)
    elif args.command == 'interactive':
        interactive_query_flow(args.meta_id, args.output)
    elif args.command == 'interactive_q2dash':
        interactive_query2dashboard_flow(args.meta_id, args.output)
    elif args.command == 'interactive_sql':
        interactive_sql_flow(args.meta_id)
    elif args.command == 'list':
        list_available_meta()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 