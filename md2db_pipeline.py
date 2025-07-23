import re
import json
import os
import psycopg2
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

def extract_sections(md_content: str):
    # Tách các bảng JSON
    json_tables = []
    for i in range(1, 10):
        title_match = re.search(r'<title_' + str(i) + r'>\s*(.*?)\s*</title_' + str(i) + r'>', md_content, re.DOTALL)
        json_match = re.search(r'<json_' + str(i) + r'>\s*(.*?)\s*</json_' + str(i) + r'>', md_content, re.DOTALL)
        if not title_match or not json_match:
            break
        table_name = title_match.group(1).strip()
        table_json = json.loads(json_match.group(1))
        json_tables.append((table_name, table_json))
    # Tách schema
    m_schema = re.search(r'<m_schema>(.*?)</m_schema>', md_content, re.DOTALL)
    m_schema = m_schema.group(1).strip() if m_schema else None
    # Tách evidence
    evidence = re.search(r'<evidence>(.*?)</evidence>', md_content, re.DOTALL)
    evidence = evidence.group(1).strip() if evidence else None
    return json_tables, m_schema, evidence

def infer_pg_type(val):
    if isinstance(val, int):
        return 'BIGINT'
    if isinstance(val, float):
        return 'DOUBLE PRECISION'
    return 'TEXT'

def create_table_sql(table_name: str, rows: List[Dict[str, Any]]):
    if not rows:
        return None
    columns = {}
    for row in rows:
        for k, v in row.items():
            if k not in columns:
                columns[k] = infer_pg_type(v)
    cols = ', '.join([f'"{k}" {v}' for k, v in columns.items()])
    return f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols});'

def insert_rows_sql(table_name: str, rows: List[Dict[str, Any]]):
    if not rows:
        return []
    keys = rows[0].keys()
    sql = f'INSERT INTO "{table_name}" ({', '.join([f'"{k}"' for k in keys])}) VALUES ({', '.join(['%s']*len(keys))}) ON CONFLICT DO NOTHING;'
    values = [tuple(row[k] for k in keys) for row in rows]
    return sql, values

def load_to_postgres(json_tables, pg_url):
    conn = psycopg2.connect(pg_url)
    cur = conn.cursor()
    for table_name, rows in json_tables:
        sql = create_table_sql(table_name, rows)
        if sql:
            cur.execute(sql)
        insert_sql, values = insert_rows_sql(table_name, rows)
        for v in values:
            try:
                cur.execute(insert_sql, v)
            except Exception:
                pass  # Bỏ qua lỗi duplicate
    conn.commit()
    cur.close()
    conn.close()

def md2db(md_path: str, pg_url: str):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    json_tables, m_schema, evidence = extract_sections(content)
    load_to_postgres(json_tables, pg_url)
    return m_schema, evidence

def md2db_with_meta(md_path: str, pg_url: str, meta_dir: str = "meta_uploads") -> dict:
    """Upload và lưu metadata (schema, evidence, bảng, id, file)"""
    os.makedirs(meta_dir, exist_ok=True)
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    json_tables, m_schema, evidence = extract_sections(content)
    load_to_postgres(json_tables, pg_url)
    upload_id = str(uuid.uuid4())
    table_names = [t[0] for t in json_tables]
    meta = {
        "id": upload_id,
        "md_path": md_path,
        "tables": table_names,
        "schema": m_schema,
        "evidence": evidence,
        "uploaded_at": datetime.now().isoformat()
    }
    meta_path = os.path.join(meta_dir, f"meta_{upload_id}.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta
# Có thể import và gọi hàm md2db_with_meta để upload và lưu metadata 