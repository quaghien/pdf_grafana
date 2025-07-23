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

## 3. Flow 1: PDF → Gemini → file .md → table → up lên postgresql
Chuyển PDF báo cáo tài chính thành dữ liệu, upload lên PostgreSQL, sinh meta_id để dùng cho bước sau.
```bash
python run_pipeline.py pdf2db --pdf <file.pdf> --out_dir .

# python run_pipeline.py pdf2db --pdf báo_cáo_tài_chính_hợp_nhất_vinamill_28-02-2025.pdf --out_dir .
```
- Kết quả: sinh file .md và upload dữ liệu vào DB, in ra meta_id.

## 4. Flow 2: User request → LLM (Text2SQL) → SQL query → port Grafana → tạo dashboard → tải image dashboard về local

Sinh SQL từ câu hỏi, tạo dashboard/panel trên Grafana, tự động tải tất cả panel về local (panel_{id}.png).
```bash
python run_pipeline.py query2dashboard --meta_id <meta_id> --question "Câu hỏi tài chính" --panel_title "Tên Panel"

# python run_pipeline.py query2dashboard --meta_id d0088d64-6160-4476-a9e2-934d9174edb7 --question "Find net cash flow during the year 2024" --panel_title "Hqh Panel"
```
- Kết quả: tạo dashboard mới, in ra UID, tải về các file panel_{id}.png (ảnh từng panel)

## 5. Ý nghĩa file panel_{id}.png
- Mỗi file panel_{id}.png là ảnh chụp panel trên dashboard vừa tạo.
- Có thể dùng để báo cáo, nhúng vào tài liệu, hoặc kiểm thử kết quả truy vấn.

## 6. Lưu ý
- Các biến môi trường phải đặt đúng trong file .env.
- Nếu gặp lỗi kết nối, kiểm tra lại Docker và cấu hình Grafana/PostgreSQL.
- Nếu muốn đổi câu hỏi, chỉ cần chạy lại flow 2 với meta_id cũ.

---
**Liên hệ: AI hỗ trợ tự động hóa báo cáo tài chính với Grafana** 