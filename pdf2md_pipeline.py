import os
from datetime import datetime
import google.generativeai as genai
import time
from dotenv import load_dotenv

load_dotenv()

class GeminiAnalyzer:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    def upload_pdf(self, pdf_path: str):
        file = genai.upload_file(pdf_path, mime_type="application/pdf")
        while file.state.name == "PROCESSING":
            time.sleep(5)
            file = genai.get_file(name=file.name)
        if file.state.name == "FAILED":
            raise RuntimeError(f"Upload thất bại: {file.state.name}")
        return file

    def analyze(self, pdf_path: str) -> str:
        file = self.upload_pdf(pdf_path)
        prompt = self.get_prompt(file)
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        response = model.generate_content(prompt, request_options={'timeout': 600})
        if not response.parts:
            raise RuntimeError("Không nhận được phản hồi hợp lệ từ Gemini.")
        return response.text

    def get_prompt(self, uploaded_file):
        # Tái sử dụng prompt như trong gemini_to_readme.py
        return ['''
Bạn là một chuyên gia phân tích tài chính chuyên nghiệp.
Dựa vào file báo cáo tài chính PDF được cung cấp, hãy thực hiện:

PHẦN 1: TẠO DỮ LIỆU JSON

Trích xuất 3 bảng số liệu quan trọng từ báo cáo tài chính (Balance Sheet, Income Statement, Cash Flow Statement) và lưu dưới dạng JSON với tên bảng bằng tiếng Anh.

YÊU CẦU:

- Tiêu đề của bảng nằm trong tag <title_i> </title_i> với i là số thứ tự của bảng (ví dụ: <title_1> </title_1>)
- Dữ liệu bảng nằm trong tag <json_i> </json_i> với i là số thứ tự của bảng (ví dụ: <json_1> </json_1>)
- Tên bảng: chỉ chữ thường, bằng tiếng Anh, dùng underscore `_` (ví dụ: cash_flow_statement, balance_sheet, income_statement)
- Tên cột: snake_case, bằng tiếng Anh, không ngoặc/ký tự đặc biệt (ví dụ: line_item, year_2024_vnd, year_2023_vnd)
- Không được có in đậm, in nghiêng, markdown, hay ký tự đặc biệt trong JSON.
- Các mục trống có thể pdf sẽ để dấu `-`, hãy chuyển chúng thành 0.
- Các số liệu có thể là số dương hoặc âm. Các giá trị trong báo cáo PDF xuất hiện trong dấu ngoặc đơn `()` (ví dụ: `(1,000,000)`) phải được chuyển đổi thành số âm trong JSON (ví dụ: `-1000000`).

---

PHẦN 2: TẠO M-SCHEMA

Dựa vào dữ liệu JSON đã tạo ở PHẦN 1, hãy tạo ra một mô tả database schema theo định dạng M-Schema chính xác.

YÊU CẦU:

- Toàn bộ nội dung M-Schema phải được bao bọc bởi tag <m_schema></m_schema>.
- Cấu trúc M-Schema phải theo định dạng đã thảo luận:
    - Bắt đầu với `[DB_ID] financial_data`
    - Tiếp theo là `[Schema]`
    - Mỗi bảng được mô tả bằng `# Table: table_name`
    - Sau đó là danh sách các cột trong bảng: `(column_name:DATATYPE, Primary Key/Foreign Key/Description, description_text, Examples: [example1, example2])`
        - Đối với cột `line_item`, hãy liệt kê **TẤT CẢ** các giá trị `line_item` có trong JSON tương ứng làm `Examples`. Đây là yêu cầu quan trọng nhất.
        - Kiểu dữ liệu nên là `TEXT` cho `line_item` và `INTEGER` (hoặc `BIGINT` nếu số quá lớn) cho các cột giá trị.
        - `Primary Key` cho cột `line_item`.
    - Cuối cùng là `[Foreign keys]` để liệt kê các mối quan hệ khóa ngoại (nếu có, hoặc ghi chú nếu không có).
- **Tất cả nội dung trong M-Schema phải là tiếng Anh.**
- Không sử dụng in đậm, in nghiêng hoặc markdown trong phần M-Schema.
- Đảm bảo không bỏ sót bất kỳ cột hoặc `line_item` nào từ dữ liệu JSON.

---

PHẦN 3: TẠO EVIDENCE (THÔNG TIN BỔ SUNG VÀ NGỮ CẢNH)

Dựa vào kiến thức tài chính chuyên sâu và các JSON đã tạo, hãy cung cấp thông tin ngữ cảnh và quy tắc nghiệp vụ quan trọng.

YÊU CẦU:

- Toàn bộ nội dung Evidence phải được bao bọc bởi tag <evidence></evidence>.
- Nội dung phải chi tiết, rõ ràng, và súc tích, bằng tiếng Anh.
- Bao gồm các phần sau (sử dụng tiêu đề phụ in đậm):
    1.  **Data Granularity and Time Periods**: Giải thích ý nghĩa của các cột thời gian (`ending_2024_vnd`, `beginning_2024_vnd`, `year_2024_vnd`, `year_2023_vnd`) và cách chúng thể hiện "snapshot" vs. "period over time". Đề cập đến đơn vị tiền tệ.
    2.  **Core Financial Relationships and Identifiers**: Giải thích vai trò của `line_item` và chỉ ra các liên kết khái niệm giữa các `line_item` có cùng tên nhưng ở các bảng khác nhau (ví dụ: `profit_before_tax` trong IS và CFS, `cash_and_cash_equivalents` trong BS và CFS).
    3.  **Fundamental Accounting Equations/Relationships**: Liệt kê các công thức kế toán cơ bản và mối quan hệ giữa các tổng số liệu (ví dụ: `Assets = Liabilities + Equity`).
    4.  **Common Calculations and Ratios**: Cung cấp các công thức tính toán tỷ lệ tài chính phổ biến (ví dụ: Current Ratio, Gross Profit Margin, Growth Rate).
    5.  **Handling of Values and Parentheses Convention**: Lưu ý về định dạng số liệu (có thể là âm) và cách chuyển đổi giá trị trong ngoặc đơn từ PDF sang số âm trong JSON.
    6.  **Querying Best Practices for LLM**: Hướng dẫn cho chính bạn (LLM) về cách diễn giải các yêu cầu phổ biến của người dùng (ví dụ: "change" nghĩa là gì, "growth" nghĩa là gì).
- Không bỏ sót bất kỳ thông tin quan trọng nào để tạo ra các SQL chất lượng cao.

---
**LƯU Ý CHUNG CHO TOÀN BỘ ĐẦU RA:**
- Đầu ra phải sạch sẽ, đúng định dạng XML, và mở/đóng tag chính xác (ví dụ: <title_1>, <json_1>, <m_schema>, <evidence>).
- Các giá trị trong báo cáo PDF xuất hiện trong dấu ngoặc đơn `()` phải được chuyển đổi thành số âm trong JSON.

**VÍ DỤ ĐẦU RA CHUẨN:**
PHẦN 1: TẠO DỮ LIỆU JSON

<title_1>
balance_sheet
</title_1>

<json_1>
[
{
"line_item": "total_assets",
"ending_2024_vnd": 55049061537061,
"beginning_2024_vnd": 52673371104460
},
{
"line_item": "current_assets",
"ending_2024_vnd": 37553650065098,
"beginning_2024_vnd": 35935879621477
}
]
</json_1>

<title_2>
income_statement
</title_2>

<json_2>
[
{
"line_item": "revenue_from_sales_and_services",
"year_2024_vnd": 61823889921880,
"year_2023_vnd": 60478912566740
},
{
"line_item": "net_revenue_from_sales_and_services",
"year_2024_vnd": 61782609528445,
"year_2023_vnd": 60368915511505
}
]
</json_2>

<title_3>
cash_flow_statement
</title_3>

<json_3>
[
{
"line_item": "profit_before_tax",
"year_2024_vnd": 11599653741335,
"year_2023_vnd": 10967899391486
},
{
"line_item": "net_cash_flow_from_operating_activities",
"year_2024_vnd": 9685937539346,
"year_2023_vnd": 7887423562363
},
{
"line_item": "net_cash_flow_from_financing_activities",
"year_2024_vnd": -6641260238228,
"year_2023_vnd": -4292773661270
}
]
</json_3>

---

PHẦN 2: TẠO M-SCHEMA

<m_schema>
[DB_ID] financial_data
[Schema]
# Table: balance_sheet
[
(line_item:TEXT, Primary Key, Description of the financial item on the balance sheet, Examples: [total_assets, current_assets, cash_and_cash_equivalents, cash, cash_equivalents, short_term_financial_investments, trading_securities, provision_for_decline_in_trading_securities, held_to_maturity_investments, short_term_receivables, trade_receivables, advances_to_suppliers, other_short_term_receivables, provision_for_doubtful_short_term_receivables, inventories, inventory_cost, provision_for_inventory_devaluation, other_current_assets, short_term_prepaid_expenses, input_vat_deductible, taxes_receivable_from_state_budget, non_current_assets, long_term_receivables, long_term_trade_receivables, other_long_term_receivables, fixed_assets, tangible_fixed_assets, original_cost_tangible_fixed_assets, accumulated_depreciation_tangible_fixed_assets, intangible_fixed_assets, original_cost_intangible_fixed_assets, accumulated_depreciation_intangible_fixed_assets, investment_properties, original_cost_investment_properties, accumulated_depreciation_investment_properties, long_term_assets_in_progress, long_term_production_and_business_in_progress_costs, construction_in_progress, long_term_financial_investments, investments_in_joint_ventures_associates, equity_investments_in_other_entities, provision_for_decline_in_long_term_financial_investments, long_term_held_to_maturity_investments, other_non_current_assets, long_term_prepaid_expenses, deferred_income_tax_assets, goodwill, total_liabilities_and_equity, liabilities, current_liabilities, trade_payables, advances_from_customers, taxes_payable_to_state_budget, payables_to_employees, accrued_expenses, unearned_revenue_short_term, other_current_payables, short_term_borrowings, short_term_provisions, bonus_and_welfare_fund, non_current_liabilities, other_long_term_payables, long_term_borrowings, deferred_income_tax_liabilities, equity, owner_equity, share_capital, share_premium, other_owner_equity, foreign_exchange_differences, investment_and_development_fund, undistributed_profit_after_tax, undistributed_profit_after_tax_accumulated_till_prior_year_end, undistributed_profit_after_tax_for_the_year, non_controlling_interests]),
(ending_2024_vnd:INTEGER, The value of the line item at the end of 2024 in VND),
(beginning_2024_vnd:INTEGER, The value of the line item at the beginning of 2024 in VND)
]

# Table: income_statement
[
(line_item:TEXT, Primary Key, Description of the financial item on the income statement, Examples: [revenue_from_sales_and_services, revenue_deductions, net_revenue_from_sales_and_services, cost_of_goods_sold_and_services_rendered, gross_profit_from_sales_and_services, financial_income, financial_expenses, interest_expense, share_of_profit_loss_from_joint_ventures_associates, selling_expenses, general_and_administrative_expenses, net_operating_profit, other_income, other_expenses, profit_from_other_activities, profit_before_tax, current_corporate_income_tax_expense, deferred_corporate_income_tax_benefit_expense, profit_after_tax, attributable_to_owners_of_the_company, non_controlling_interests_income_statement, basic_earnings_per_share]),
(year_2024_vnd:INTEGER, The value of the line item for the year 2024 in VND),
(year_2023_vnd:INTEGER, The value of the line item for the year 2023 in VND)
]

# Table: cash_flow_statement
[
(line_item:TEXT, Primary Key, Description of the financial item on the cash flow statement, Examples: [profit_before_tax, depreciation_and_amortization, amortization_of_goodwill, provisions, gain_loss_on_foreign_exchange_differences_from_revaluation_of_monetary_items_denominated_in_foreign_currencies, loss_from_disposal_write_off_of_fixed_assets_and_construction_in_progress, income_from_dividends_interest_on_deposits_and_gain_loss_from_other_investing_activities, gain_loss_from_joint_ventures_associates, interest_expense_cfs, profit_from_operating_activities_before_changes_in_working_capital, changes_in_receivables, changes_in_inventories, changes_in_payables_and_other_payables, changes_in_prepaid_expenses, interest_paid, corporate_income_tax_paid, other_cash_outflows_for_operating_activities, net_cash_flow_from_operating_activities, cash_paid_for_purchase_of_fixed_assets_and_other_long_term_assets, cash_received_from_disposal_of_fixed_assets_and_construction_in_progress, cash_paid_for_time_deposits, cash_paid_for_equity_investments_in_other_entities, cash_received_from_recovery_of_equity_investments_in_other_entities, cash_received_from_interest_on_deposits_and_dividends, net_cash_flow_from_investing_activities, cash_received_from_non_controlling_shareholders_capital_contribution_in_a_subsidiary, cash_repaid_to_non_controlling_shareholders_of_dissolved_subsidiary, cash_received_from_borrowings, cash_paid_for_principal_of_borrowings, cash_paid_for_dividends, cash_paid_for_dividends_by_subsidiaries_to_non_controlling_shareholders, net_cash_flow_from_financing_activities, net_cash_flow_during_the_year, cash_and_cash_equivalents_at_beginning_of_year, effect_of_exchange_rate_changes_on_cash_and_cash_equivalents, foreign_exchange_differences_cfs, cash_and_cash_equivalents_at_end_of_year]),
(year_2024_vnd:INTEGER, The value of the line item for the year 2024 in VND),
(year_2023_vnd:INTEGER, The value of the line item for the year 2023 in VND)
]

[Foreign keys]
-- No explicit foreign key relationships exist between these tables based on the provided JSON structure.
-- The 'line_item' column in each table serves as a primary key unique to that specific financial statement.
-- If cross-statement linking based on line item names is intended, a separate master 'line_item_definitions' table would typically be used,
-- with these tables referencing its primary key.
</m_schema>

---

PHẦN 3: TẠO EVIDENCE (THÔNG TIN BỔ SUNG VÀ NGỮ CẢNH)

<evidence>
This database contains financial statement data for a company, spanning Balance Sheet, Income Statement, and Cash Flow Statement. All monetary values are expressed in Vietnamese Dong (VND).

**1. Data Granularity and Time Periods:**
- For the 'balance_sheet' table:
    - 'ending_2024_vnd' represents the *snapshot value* of a specific financial item at the end of the fiscal year 2024 (December 31, 2024).
    - 'beginning_2024_vnd' represents the *snapshot value* of the same item at the beginning of the fiscal year 2024 (January 1, 2024), which is equivalent to the value at the end of fiscal year 2023 (December 31, 2023).
- For the 'income_statement' and 'cash_flow_statement' tables:
    - 'year_2024_vnd' represents the *aggregated value* over the entire fiscal year 2024.
    - 'year_2023_vnd' represents the *aggregated value* over the entire fiscal year 2023.
- These distinctions are crucial for calculating changes (snapshot difference) versus total performance (period sum).

**2. Core Financial Relationships and Identifiers:**
- The 'line_item' column in each table ('balance_sheet', 'income_statement', 'cash_flow_statement') serves as a unique textual identifier for each specific financial metric *within that particular statement*.
- While 'line_item' names can be identical across different statements (e.g., 'profit_before_tax'), they should primarily be interpreted in the context of their specific financial statement.
- However, for comparative analysis and reconciliation, the following *conceptual links* between line items across different statements are vital:
    - **Profit Before Tax Consistency:** The 'profit_before_tax' in the 'income_statement' is the same conceptual figure as 'profit_before_tax' in the 'cash_flow_statement', serving as the starting point for the indirect method of cash flow from operations.
    - **Cash Balance Reconciliation:** The 'cash_and_cash_equivalents' (ending balance) in the 'balance_sheet' for a given year should conceptually reconcile with 'cash_and_cash_equivalents_at_end_of_year' in the 'cash_flow_statement' for the same year. Similarly, 'cash_and_cash_equivalents_at_beginning_of_year' in the 'cash_flow_statement' matches the 'beginning_2024_vnd' (end of 2023) of 'cash_and_cash_equivalents' in the 'balance_sheet'.
    - **Profit Transfer to Equity:** The 'profit_after_tax' from the 'income_statement' contributes directly to 'undistributed_profit_after_tax_for_the_year' within the 'equity' section of the 'balance_sheet'.
    - **Non-Controlling Interests:** 'non_controlling_interests' on the 'balance_sheet' reflects the cumulative balance, while 'non_controlling_interests_income_statement' on the 'income_statement' reflects the current period's share of profit/loss attributable to them.

**3. Fundamental Accounting Equations and Relationships:**
- **The Accounting Equation (Balance Sheet):** `total_assets = total_liabilities_and_equity`. This is always true for the balance sheet.
- **Asset Structure:** `total_assets = current_assets + non_current_assets`.
- **Liabilities and Equity Structure:** `total_liabilities_and_equity = liabilities + equity`.
- **Equity Structure:** `equity = owner_equity + non_controlling_interests`.
- **Components of Fixed Assets:** `fixed_assets = tangible_fixed_assets + intangible_fixed_assets + investment_properties`.
    - For individual fixed asset categories (tangible, intangible, investment properties), their net book value is calculated as `original_cost + accumulated_depreciation` (since accumulated depreciation is stored as a negative value in the JSON).
- **Inventories:** `inventories = inventory_cost + provision_for_inventory_devaluation` (since provision is stored as a negative value).
- **Receivables:** `short_term_receivables = trade_receivables + advances_to_suppliers + other_short_term_receivables + provision_for_doubtful_short_term_receivables` (since provision is stored as a negative value).
- **Income Statement Flow:** `net_revenue_from_sales_and_services - cost_of_goods_sold_and_services_rendered = gross_profit_from_sales_and_services`.
- **Overall Profit:** `profit_before_tax = net_operating_profit + profit_from_other_activities`.

**4. Common Financial Calculations and Ratios:**
- **Net Change (for Balance Sheet items):**
    `SELECT (ending_2024_vnd - beginning_2024_vnd) AS net_change FROM balance_sheet WHERE line_item = 'desired_item'`
- **Year-over-Year Growth/Decline (for Income Statement/Cash Flow items):**
    `SELECT ((year_2024_vnd - year_2023_vnd) * 100.0 / year_2023_vnd) AS growth_percentage FROM income_statement WHERE line_item = 'desired_item'`
    *Note: Ensure division by non-zero 'year_2023_vnd' to avoid errors. If 'year_2023_vnd' is 0, growth cannot be calculated as a percentage.*
- **Gross Profit Margin:**
    `SELECT (T1.year_2024_vnd * 100.0 / T2.year_2024_vnd) AS gross_profit_margin_2024 FROM income_statement AS T1 JOIN income_statement AS T2 ON T1.line_item = 'gross_profit_from_sales_and_services' AND T2.line_item = 'net_revenue_from_sales_and_services'`
- **Current Ratio:**
    `SELECT (T1.ending_2024_vnd * 1.0 / T2.ending_2024_vnd) AS current_ratio_2024 FROM balance_sheet AS T1 JOIN balance_sheet AS T2 ON T1.line_item = 'current_assets' AND T2.line_item = 'current_liabilities'`
- **Debt-to-Equity Ratio:**
    `SELECT (T1.ending_2024_vnd * 1.0 / T2.ending_2024_vnd) AS debt_to_equity_2024 FROM balance_sheet AS T1 JOIN balance_sheet AS T2 ON T1.line_item = 'liabilities' AND T2.line_item = 'equity'`
- **Return on Assets (ROA):**
    `SELECT (T1.year_2024_vnd * 1.0 / ((T2_end.ending_2024_vnd + T2_beg.beginning_2024_vnd) / 2)) AS ROA_2024 FROM income_statement AS T1 JOIN balance_sheet AS T2_end ON T1.line_item = 'profit_after_tax' AND T2_end.line_item = 'total_assets' JOIN balance_sheet AS T2_beg ON T2_beg.line_item = 'total_assets'`
    *Note: For ROA, average total assets over the period (beginning + ending / 2) is commonly used.*

**5. Handling of Values and Parentheses Convention**:
All numerical values should be extracted as integers. Pay close attention to the sign of the numbers. In standard financial reporting, certain items (e.g., cash outflows, accumulated depreciation, provisions for doubtful debts/inventory devaluation, expenses) are often presented as negative values or within parentheses in the source PDF (e.g., `(1,000,000)`). When extracting, convert values presented in parentheses into negative numbers in the JSON output (e.g., `-1000000`). For example, `net_cash_flow_from_financing_activities` will often be a negative number if the company is repaying debt or paying dividends. Similarly, `basic_earnings_per_share` can be negative if the company reports a net loss.

**6. Querying Best Practices for LLM**:
- When a user asks for "change" or "growth" for balance sheet items, imply a comparison between 'ending_2024_vnd' and 'beginning_2024_vnd'.
- When a user asks for "change" or "growth" for income statement or cash flow statement items, imply a comparison between 'year_2024_vnd' and 'year_2023_vnd'.
- Pay close attention to specific year references (e.g., "for 2024", "at the end of 2023"). The 'beginning_2024_vnd' in the balance sheet is equivalent to the 'end of 2023'.
- If a query involves abstract financial concepts like "assets", "liabilities", "revenue", or "profit", interpret them by referring to the most appropriate 'line_item' from the respective tables. For instance, "total assets" refers to 'total_assets' in 'balance_sheet'.
- When calculating ratios, ensure the correct 'line_item' from the correct table is used, and apply appropriate mathematical operations (e.g., division, multiplication for percentages).
- Be mindful of potential division by zero when calculating percentages or ratios and handle them gracefully.
- Be particularly careful with the sign of the numbers when performing calculations involving contra-accounts (e.g., accumulated depreciation, provisions), as they are stored as negative values in the JSON.
- Do not omit any critical information required to generate high-quality SQL.
</evidence>
''',
            uploaded_file
        ]

def save_to_file(content: str, filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

def pdf_to_md(pdf_path: str, out_dir: str = ".") -> str:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise RuntimeError("Thiếu GEMINI_API_KEY trong .env")
    analyzer = GeminiAnalyzer(GEMINI_API_KEY)
    result = analyzer.analyze(pdf_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    out_file = os.path.join(out_dir, f"{base_name}_{timestamp}.md")
    save_to_file(result, out_file)
    return out_file

# Có thể import và gọi hàm pdf_to_md trong các pipeline tiếp theo 