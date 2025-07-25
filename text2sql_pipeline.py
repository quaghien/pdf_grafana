import os
from typing import Optional

def build_prompt(schema: str, evidence: str, question: str) -> str:
    prompt = f"""
You are an expert in PostgreSQL and need to read and understand the following 【Database Schema】description, as well as any 【Reference Information】that may be used, and apply your PostgreSQL knowledge to generate an SQL query to answer the 【User Question】.

【User Question】
{question}

【Database Schema】
{schema}

【Reference Information】
{evidence}

【User Question】
{question}

```sql"""
    return prompt

def text2sql(schema: str, evidence: str, question: str, model_path: Optional[str] = None) -> str:
    try:
        from llama_cpp import Llama
    except ImportError:
        raise ImportError("Cần cài đặt llama-cpp-python: pip install llama-cpp-python")
    if model_path is None:
        model_path = os.getenv("XIYAN_GGUF_MODEL", "/home/s24thai/Workspace/hienhq/t2sql/pdf2dashboard_grafana/xiyan-sqlcoder-7b.gguf")
    if not os.path.exists(model_path):
        raise RuntimeError(f"Không tìm thấy model GGUF: {model_path}")
    model = Llama(model_path=model_path, n_ctx=16000, n_threads=1, n_gpu_layers=-1, verbose=False, seed=42)
    prompt = build_prompt(schema, evidence, question)
    response = model(prompt, max_tokens=1024, temperature=0.1)
    sql = response['choices'][0]['text'].strip()
    return sql.strip()

# Có thể import và gọi hàm text2sql trong các pipeline tiếp theo 