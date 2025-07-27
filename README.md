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

- Tải các model LLM tạo sql query về local:

```
python download_gguf_models.py
```

## 2. Khởi động dịch vụ
```bash
docker compose up -d
```
- PostgreSQL: cổng 5432, user/password/db: grafana/grafana/dashboard_db
- Grafana: cổng 3000, http://localhost:3000 (user: admin, password: admin)
- grafana-image-renderer để tải ảnh từ grafana về local

Kết nối postgresql với grafana trên http://localhost:3000:
<img src="images/kết nối postgresql với grafana.png" alt="Kết nối PostgreSQL với Grafana" width="600">

## 3. Sử dụng

### Bước 1: Convert PDF thành database
```bash
python run_pipeline.py pdf2db --pdf file.pdf --out_dir .
```

### Bước 2: Tạo dashboard từ câu hỏi
```bash
python run_pipeline.py question2panel --meta_id YOUR_META_ID --output dashboard_panels.json
```

## 4. Ví dụ kết quả

Pipeline sẽ tự động tạo và download các panel dưới dạng PNG:

### Balance Sheet Analysis
![Balance Sheet Analysis](panel/panel_1_Balance_Sheet_Analysis_20250725_175530.png)

### Line Item Analysis
![Line Item Analysis 1](panel/panel_1_Line_Item_Analysis_20250725_175605.png)

![Line Item Analysis 2](panel/panel_1_Line_Item_Analysis_20250725_175942.png)

## 5. Mẫu câu hỏi

Đây là các câu hỏi bạn có thể sử dụng trong interactive mode:

**Câu hỏi 1:**
"Cho tôi biết nguyên giá tài sản cố định hữu hình vào cuối năm 2024 là bao nhiêu?"

**Câu hỏi 2:**
"So sánh lưu chuyển tiền thuần từ hoạt động kinh doanh, lợi nhuận trước thuế, khấu hao và phân bổ, thay đổi các khoản phải thu, thay đổi hàng tồn kho, và thay đổi các khoản phải trả và phải trả khác giữa năm 2023 và năm 2024."

**Câu hỏi 3:**
"Phân bổ các thành phần doanh thu và chi phí của năm 2024 như thế nào?"

**Câu hỏi 4:**
"Cơ cấu vốn chủ sở hữu cuối năm 2024 của công ty ra sao?"

## 6. Lưu ý
- Các biến môi trường phải đặt đúng trong file .env
- Nếu gặp lỗi kết nối, kiểm tra lại Docker và cấu hình Grafana/PostgreSQL
- Nếu muốn thêm câu hỏi mới, chỉ cần chạy lại `question2panel` với cùng meta_id
- Các panel được tự động download vào folder `panel/`
