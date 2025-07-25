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
    tables = meta.get('tables', [])
    print(f"[Query→SQL] Loaded {len(tables)} tables from metadata")
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


def list_available_meta():
    """
    Liệt kê các meta_id có sẵn trong thư mục meta_uploads
    """
    meta_dir = "meta_uploads"
    if not os.path.exists(meta_dir):
        print(f"[INFO] Thư mục {meta_dir} không tồn tại.")
        return []
    
    meta_files = [f for f in os.listdir(meta_dir) if f.startswith('meta_') and f.endswith('.json')]
    if not meta_files:
        print(f"[INFO] Không có file metadata nào trong {meta_dir}")
        return []
    
    print(f"[INFO] Tìm thấy {len(meta_files)} meta file(s):")
    meta_ids = []
    for meta_file in sorted(meta_files):
        meta_id = meta_file.replace('meta_', '').replace('.json', '')
        meta_ids.append(meta_id)
        
        # Đọc thông tin cơ bản từ meta file
        try:
            with open(os.path.join(meta_dir, meta_file), 'r', encoding='utf-8') as f:
                meta = json.load(f)
                created_at = meta.get('uploaded_at', 'N/A')
                tables = meta.get('tables', [])
                num_tables = len(meta.get('tables', []))
                md_path = meta.get('md_path', 'N/A')
                print(f"  - md_path: {md_path}")
                print(f"  - meta_id: {meta_id}")
                print(f"    Tạo lúc: {created_at}")
                print(f"    Tables: {num_tables} tables")
                print(f"    Tables: {tables}")
        except Exception as e:
            print(f"  - meta_id: {meta_id} (lỗi đọc file: {e})")
    
    return meta_ids


def interactive_query_flow(meta_id, output_json="sql_queries.json"):
    """
    Chế độ tương tác: load data từ meta_id và cho phép nhập nhiều câu hỏi,
    tạo SQL query và lưu vào file JSON
    """
    # Load metadata
    meta_path = f"meta_uploads/meta_{meta_id}.json"
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Không tìm thấy file metadata: {meta_path}")
        print("Hãy chạy lệnh pdf2db trước để tạo metadata, hoặc sử dụng meta_id có sẵn.")
        print("\nCác meta_id có sẵn:")
        available_metas = list_available_meta()
        if not available_metas:
            print("Không có meta_id nào. Hãy chạy 'python run_pipeline.py pdf2db --pdf <file.pdf>' trước.")
        return

    schema = meta['schema']
    evidence = meta['evidence']
    tables = meta.get('tables', [])
    
    print(f"[INFO] Đã load metadata từ: {meta_path}")
    print(f"[INFO] Tables: {len(tables)} tables")
    if tables:
        print(f"[INFO] Table names: {', '.join(tables)}")
    
    # Load existing queries hoặc tạo mới
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
                    print(f"[INFO] Đã load {len(queries_data['queries'])} SQL queries từ {output_json}")
                else:
                    print(f"[INFO] File {output_json} có meta_id khác, tạo file mới")
        except Exception as e:
            print(f"[WARNING] Lỗi đọc file {output_json}: {e}")
    
    print("\n" + "="*60)
    print("CHẾ ĐỘ TƯƠNG TÁC - TẠO SQL QUERY")
    print("="*60)
    print("Nhập câu hỏi để tạo SQL query.")
    print("Các lệnh hữu ích:")
    print("  'exit', 'quit', 'thoát' - Thoát chế độ tương tác")
    print("  'list' - Xem danh sách SQL queries đã tạo")
    print("  'tables' - Xem danh sách tables có sẵn")
    print("  'info' - Xem thông tin metadata")
    print("="*60)
    
    query_counter = len(queries_data['queries']) + 1
    
    while True:
        try:
            question = input(f"\n[Q{query_counter}] Nhập câu hỏi: ").strip()
            
            if question.lower() in ['exit', 'quit', 'thoát']:
                print("\n[INFO] Đã thoát chế độ tương tác.")
                break
            
            if question.lower() == 'list':
                print(f"\n[INFO] Danh sách {len(queries_data['queries'])} SQL queries:")
                for i, q in enumerate(queries_data['queries'], 1):
                    print(f"  {i}. {q['question']}")
                    print(f"     SQL: {q['sql'][:100]}{'...' if len(q['sql']) > 100 else ''}")
                    print(f"     Thời gian: {q.get('timestamp', 'N/A')}")
                continue
            
            if question.lower() == 'tables':
                print(f"\n[INFO] Danh sách {len(tables)} tables có sẵn:")
                if tables:
                    for i, table in enumerate(tables, 1):
                        print(f"  {i}. {table}")
                else:
                    print("  Không có tables nào.")
                continue
            
            if question.lower() == 'info':
                print(f"\n[INFO] Thông tin metadata:")
                print(f"  Meta ID: {meta_id}")
                print(f"  File path: {meta_path}")
                print(f"  MD path: {meta.get('md_path', 'N/A')}")
                print(f"  Upload time: {meta.get('uploaded_at', 'N/A')}")
                print(f"  Tables: {len(tables)} tables")
                continue
            
            if not question:
                print("[WARNING] Câu hỏi không được để trống!")
                continue
            
            print(f"[INFO] Đang tạo SQL query cho: {question}")
            
            # Gọi text2sql để tạo SQL
            sql = text2sql(schema, evidence, question)
            
            print(f"[SQL] {sql}")
            
            # Lưu vào queries_data
            query_entry = {
                "id": query_counter,
                "question": question,
                "sql": sql,
                "timestamp": datetime.now().isoformat()
            }
            
            queries_data['queries'].append(query_entry)
            
            # Lưu vào file JSON
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(queries_data, f, ensure_ascii=False, indent=2)
            
            print(f"[INFO] Đã lưu SQL query #{query_counter} vào {output_json}")
            query_counter += 1
            
        except KeyboardInterrupt:
            print("\n\n[INFO] Đã dừng bằng Ctrl+C.")
            break
        except Exception as e:
            print(f"[ERROR] Lỗi xử lý: {e}")
            continue
    
    print(f"\n[INFO] Tổng cộng đã tạo {len(queries_data['queries'])} SQL queries")
    print(f"[INFO] Các queries đã được lưu trong: {output_json}")


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

    interactive_parser = subparsers.add_parser('interactive', help='Chế độ tương tác - Nhập nhiều câu hỏi và tạo SQL')
    interactive_parser.add_argument('--meta_id', required=True, help='ID upload/meta_id')
    interactive_parser.add_argument('--output', default='sql_queries.json', help='File JSON để lưu các SQL queries')

    list_parser = subparsers.add_parser('list', help='Liệt kê các meta_id có sẵn')

    args = parser.parse_args()

    if args.command == 'pdf2db':
        pdf2db_flow(args.pdf, args.out_dir)
    elif args.command == 'query2dashboard':
        query2dashboard_flow(args.meta_id, args.question, args.panel_title)
    elif args.command == 'interactive':
        interactive_query_flow(args.meta_id, args.output)
    elif args.command == 'list':
        list_available_meta()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 