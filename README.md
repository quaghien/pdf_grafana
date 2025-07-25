# pdf2dashboard_grafana

## 1. Thiết lập môi trường
- Tạo file `.env` với nội dung mẫu:
```
GEMINI_API_KEY=**your_gemini_key
PG_URL=postgresql://grafana:grafana@localhost:5432/dashboard_db
GRAFANA_API_KEY=**your_grafana_api_key
GRAFANA_URL=http://localhost:3000
```
- Lấy `GRAFANA_API_KEY` trong Grafana: (quyền Editor trở lên)
<img src="images/tạo%20token%20grafana.png" alt="Tạo token Grafana" width="600">

- Tải thư viện cần thiết:
```
pip install -r requirements.txt
```

- Ngoài ra còn cần tải các thư viện khác (đã nêu trong file requirements.txt)

- Tải các model gguf tùy chọn về local:

```
python download_gguf_models.py
```

## 2. Khởi động dịch vụ
```bash
docker compose up -d
```
- PostgreSQL: cổng 5432, user/password/db: grafana/grafana/dashboard_db
- Grafana: cổng 3000, http://localhost:3000 (user: admin, password: admin)
- grafana-image-renderer để tại ảnh từ grafana về local

Kết nối postgresql với grafana trên http://localhost:3000:
<img src="images/kết nối postgresql với grafana.png" alt="Tạo token Grafana" width="600">


```
# PDF to Database
python run_pipeline.py pdf2db --pdf report.pdf

# Single Question → Dashboard
python run_pipeline.py query2dashboard --meta_id abc123 --question "Total assets 2024"

# Single SQL → Panel  
python run_pipeline.py sql2panel --meta_id abc123 --sql_query "SELECT..."

# Interactive Question Mode
python run_pipeline.py interactive_q2dash --meta_id abc123

# Interactive SQL Mode  
python run_pipeline.py interactive_sql --meta_id abc123

# Utilities
python run_pipeline.py list
```


## 6. Lưu ý
- Các biến môi trường phải đặt đúng trong file .env.
- Nếu gặp lỗi kết nối, kiểm tra lại Docker và cấu hình Grafana/PostgreSQL.
- Nếu muốn đổi câu hỏi, chỉ cần chạy lại flow 2 với meta_id cũ.

---
Example sql query:

#TABLE
```
python run_pipeline.py sql2panel --meta_id 68222824-35ed-4f1c-bcc0-e1329bd67421 --sql_query "SELECT
  ending_2024_vnd
FROM
  balance_sheet
WHERE
  line_item = 'original_cost_tangible_fixed_assets';"
```

#BAR
```
python run_pipeline.py sql2panel --meta_id 68222824-35ed-4f1c-bcc0-e1329bd67421 --sql_query "SELECT
  line_item,
  year_2024_vnd,
  year_2023_vnd
FROM
  cash_flow_statement
WHERE
  line_item IN ('net_cash_flow_from_operating_activities', 'profit_before_tax', 'depreciation_and_amortization', 'changes_in_receivables', 'changes_in_inventories', 'changes_in_payables_and_other_payables');"
```
#PIE

```
python run_pipeline.py sql2panel --meta_id 68222824-35ed-4f1c-bcc0-e1329bd67421 --sql_query "SELECT
  line_item,
  year_2024_vnd AS value_for_pie_chart -- Giá trị để vẽ biểu đồ
FROM           
  income_statement
WHERE                
  line_item IN ('revenue_from_sales_and_services', 'revenue_deductions', 'cost_of_goods_sold_and_services_rendered')
  AND year_2024_vnd IS NOT NULL;"
```

```
python run_pipeline.py sql2panel --meta_id 68222824-35ed-4f1c-bcc0-e1329bd67421 --sql_query "SELECT
  line_item,
  ending_2024_vnd AS value_for_pie_chart -- Giá trị để vẽ biểu đồ
FROM
  balance_sheet
WHERE
  line_item IN ('share_capital', 'share_premium', 'investment_and_development_fund', 'undistributed_profit_after_tax', 'other_owner_equity')
  AND ending_2024_vnd IS NOT NULL;"
```

