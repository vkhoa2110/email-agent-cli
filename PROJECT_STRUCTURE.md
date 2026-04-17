# Project Structure

## 1. Mục tiêu dự án

`email_draft_agent` là một CLI agent dùng LLM để:
- nhận yêu cầu soạn email,
- hỏi thêm nếu thiếu thông tin,
- lưu bản nháp email ra file JSON,
- gửi email thật qua SMTP khi người dùng yêu cầu rõ là gửi,
- hỗ trợ đổi provider giữa `OpenAI` và `Gemini` bằng file `.env`.

## 2. Cấu trúc thư mục

```text
email_draft_agent/
├── app.py
├── agent.py
├── prompts.py
├── tools.py
├── requirements.txt
├── .env.example
├── README.md
├── PROJECT_STRUCTURE.md
├── drafts/
└── sent_emails/
```

Ý nghĩa từng phần:
- `app.py`: điểm vào của chương trình CLI.
- `agent.py`: lớp agent chính, chọn backend `OpenAI` hoặc `Gemini`, xử lý vòng gọi tool.
- `prompts.py`: chứa system prompt hướng dẫn model phải làm gì.
- `tools.py`: định nghĩa tool schema và các hàm local như lưu draft, gửi email SMTP.
- `requirements.txt`: dependency Python.
- `.env.example`: file mẫu cho biến môi trường.
- `drafts/`: nơi lưu email nháp dưới dạng JSON.
- `sent_emails/`: nơi lưu log các email đã gửi thành công.

## 3. Luồng chạy tổng thể

1. Người dùng chạy `python app.py`.
2. `app.py` tạo `EmailDraftAgent`.
3. `EmailDraftAgent` đọc `LLM_PROVIDER` để chọn backend:
   - `OpenAIEmailBackend`
   - `GeminiEmailBackend`
4. Backend gửi prompt + tool schema lên model.
5. Model có thể:
   - trả text trực tiếp,
   - hoặc yêu cầu gọi tool local.
6. Nếu model gọi tool:
   - agent đọc tên tool,
   - parse arguments,
   - gọi hàm Python tương ứng trong `TOOL_REGISTRY`,
   - gửi kết quả tool ngược lại cho model.
7. Khi hoàn tất, CLI in nội dung phản hồi cho người dùng.

## 4. File `app.py`

### Vai trò

Đây là file khởi động chương trình dạng terminal.

### Các thành phần chính

#### `WELCOME`
Chuỗi giới thiệu hiển thị khi app bắt đầu chạy.

#### `_configure_console_encoding()`
Mục đích:
- ép `stdin`, `stdout`, `stderr` sang UTF-8.

Tại sao cần:
- tránh lỗi hiển thị tiếng Việt trên terminal Windows.

#### `main()`
Luồng chính của CLI:
- gọi `_configure_console_encoding()`,
- khởi tạo `EmailDraftAgent`,
- in provider và model hiện tại,
- đọc input từ người dùng trong vòng lặp,
- xử lý các lệnh:
  - `/exit`
  - `/reset`
- gửi input sang `agent.run_turn(...)`,
- in kết quả trả về.

## 5. File `agent.py`

### Vai trò

File này chứa toàn bộ logic điều phối giữa:
- CLI,
- provider LLM,
- tool local.

### Hàm helper

#### `_get_provider_name(provider=None)`
Mục đích:
- chuẩn hóa tên provider.

Nhận:
- `openai`
- `gemini`
- `google` (được map sang `gemini`)

Nếu sai:
- ném `RuntimeError`.

#### `_get_required_env(var_name, placeholder)`
Mục đích:
- lấy biến môi trường bắt buộc,
- báo lỗi rõ nếu thiếu hoặc vẫn là placeholder.

#### `_get_gemini_api_key()`
Mục đích:
- ưu tiên lấy `GEMINI_API_KEY`,
- fallback sang `GOOGLE_API_KEY` nếu có.

Lý do:
- SDK Gemini có thể dùng cả hai kiểu biến môi trường.

### Lớp `OpenAIEmailBackend`

Backend dành cho OpenAI Responses API.

#### `__init__(model=None, max_tool_rounds=5)`
Nhiệm vụ:
- tạo `OpenAI` client,
- đọc `OPENAI_MODEL`,
- lưu giới hạn số vòng gọi tool,
- khởi tạo `previous_response_id` để giữ ngữ cảnh hội thoại.

#### `_create_response(user_input, previous_response_id)`
Nhiệm vụ:
- gọi `client.responses.create(...)`,
- truyền vào:
  - `model`
  - `instructions`
  - `input`
  - `previous_response_id`
  - `tools`

Ngoài ra:
- bắt lỗi `AuthenticationError` để đổi thành thông báo dễ hiểu.

#### `_extract_function_calls(response)`
Nhiệm vụ:
- lấy ra các item có `type == "function_call"` từ response OpenAI.

#### `_safe_output_text(response)`
Nhiệm vụ:
- lấy text trả về từ response một cách an toàn,
- fallback sang duyệt `output` nếu `output_text` không có.

#### `run_turn(user_input)`
Đây là hàm quan trọng nhất của backend OpenAI.

Luồng:
1. gửi input của user lên model,
2. kiểm tra model có yêu cầu gọi tool không,
3. nếu không có tool:
   - trả text về cho CLI,
4. nếu có tool:
   - parse arguments JSON,
   - lookup tool trong `TOOL_REGISTRY`,
   - gọi hàm Python local,
   - đóng gói kết quả dưới dạng `function_call_output`,
   - gửi lại cho model,
5. lặp tối đa `max_tool_rounds`.

#### `reset()`
Mục đích:
- xóa `previous_response_id`,
- bắt đầu lại ngữ cảnh hội thoại.

### Lớp `GeminiEmailBackend`

Backend dành cho Google Gemini SDK `google-genai`.

#### `__init__(model=None, max_tool_rounds=5)`
Nhiệm vụ:
- import SDK Gemini,
- tạo `genai.Client`,
- đọc `GEMINI_MODEL`,
- khởi tạo `history`,
- build `GenerateContentConfig`,
- convert các tool local thành `FunctionDeclaration`.

Điểm đáng chú ý:
- nếu cùng lúc tồn tại `GEMINI_API_KEY` và `GOOGLE_API_KEY`, code tạm thời tránh để SDK ưu tiên nhầm biến không mong muốn.

#### `_create_response()`
Nhiệm vụ:
- gọi `client.models.generate_content(...)` với:
  - `model`
  - `contents=self.history`
  - `config=self.config`

Ngoài ra:
- đổi lỗi xác thực/key thành thông báo dễ hiểu.

#### `_first_candidate_content(response)`
Mục đích:
- lấy `content` của candidate đầu tiên từ response Gemini.

#### `_safe_output_text(response)`
Mục đích:
- đọc `response.text` nếu có,
- nếu không có thì duyệt các `parts` để ghép text lại.

#### `run_turn(user_input)`
Đây là hàm quan trọng nhất của backend Gemini.

Luồng:
1. append input user vào `history`,
2. gọi model,
3. kiểm tra `function_calls`,
4. nếu không có function call:
   - trả text về cho CLI,
5. nếu có:
   - lấy tên tool + args,
   - gọi tool local trong `TOOL_REGISTRY`,
   - append `function_response` vào `history`,
   - gọi lại model,
6. lặp tối đa `max_tool_rounds`.

#### `reset()`
Mục đích:
- xóa toàn bộ `history`.

### Lớp `EmailDraftAgent`

Đây là lớp facade dùng ở `app.py`.

#### `__init__(model=None, provider=None, max_tool_rounds=5)`
Nhiệm vụ:
- chọn backend theo provider,
- tạo backend phù hợp,
- expose `provider` và `model` cho CLI.

#### `run_turn(user_input)`
Nhiệm vụ:
- chuyển tiếp sang backend hiện tại.

#### `reset()`
Nhiệm vụ:
- gọi `reset()` của backend hiện tại.

## 6. File `prompts.py`

### Vai trò

Chứa `SYSTEM_PROMPT` dùng chung cho cả OpenAI và Gemini.

### Nội dung chính của prompt

Prompt yêu cầu model:
- hỏi thêm khi thiếu thông tin,
- không tự bịa chi tiết nghiệp vụ,
- chỉ lưu draft nếu user chỉ muốn soạn,
- chỉ gửi email thật khi user yêu cầu rõ,
- khi gửi thật thì phải:
  1. lưu draft trước,
  2. rồi mới gọi `send_email`,
- nếu gửi lỗi thì phải báo là chưa gửi thành công.

Nói ngắn gọn:
- `prompts.py` là nơi đặt "luật nghiệp vụ" cho model.

## 7. File `tools.py`

### Vai trò

File này là lớp tích hợp local tool.

Nó gồm 2 phần:
- `TOOLS`: schema để model biết có thể gọi tool nào,
- `TOOL_REGISTRY`: map tên tool -> hàm Python thật.

### Biến `EMAIL_PATTERN`
Dùng để validate email người nhận.

### Biến `TOOLS`

Khai báo 2 tool:
- `save_email_draft`
- `send_email`

Mỗi tool có:
- `name`
- `description`
- `parameters`
- `strict`

### Hàm helper

#### `_get_data_dir(name)`
Mục đích:
- tạo thư mục lưu dữ liệu nếu chưa tồn tại,
- trả về `Path` của thư mục đó.

Ví dụ:
- `drafts/`
- `sent_emails/`

#### `_write_json_record(directory_name, prefix, payload)`
Mục đích:
- sinh id ngẫu nhiên,
- ghi `payload` ra file JSON.

Được dùng để:
- lưu log email đã gửi.

#### `_get_env(name, default="")`
Mục đích:
- đọc biến môi trường và `strip()`.

#### `_get_required_env(name, placeholder="")`
Mục đích:
- đọc biến môi trường bắt buộc,
- nếu thiếu thì báo lỗi dễ hiểu.

#### `_parse_bool(value, default)`
Mục đích:
- parse biến kiểu boolean từ `.env`,
- hỗ trợ các giá trị như:
  - `true/false`
  - `1/0`
  - `yes/no`

#### `_parse_recipients(to)`
Mục đích:
- parse danh sách email người nhận,
- validate định dạng email.

Nếu email sai:
- ném `RuntimeError`.

### Hàm `save_email_draft(...)`

Nhiệm vụ:
- nhận nội dung email hoàn chỉnh,
- sinh `draft_id`,
- tạo JSON chứa:
  - người nhận
  - subject
  - body
  - tone
  - language
  - purpose
  - thời gian lưu
- ghi file vào thư mục `drafts/`.

Giá trị trả về:
- `status`
- `draft_id`
- `path`
- `preview_subject`

### Hàm `send_email(to, subject, body)`

Nhiệm vụ:
- đọc cấu hình SMTP từ `.env`,
- validate người nhận,
- tạo `EmailMessage`,
- kết nối SMTP,
- đăng nhập,
- gửi email thật,
- lưu log gửi thành công vào `sent_emails/`.

Biến môi trường dùng:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`

Các lỗi được xử lý:
- thiếu config SMTP,
- email người nhận sai,
- sai app password,
- lỗi SMTP server,
- lỗi kết nối mạng.

Giá trị trả về:
- `status="sent"`
- danh sách người nhận,
- email người gửi,
- subject,
- thời gian gửi,
- `message_id`,
- đường dẫn file log.

### Biến `TOOL_REGISTRY`

Map tên tool sang hàm thực thi:

```python
{
    "save_email_draft": save_email_draft,
    "send_email": send_email,
}
```

## 8. File `.env`

### Nhóm cấu hình LLM

- `LLM_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- `GEMINI_MODEL`

### Nhóm cấu hình SMTP

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`

## 9. Hai kiểu dữ liệu được lưu ra disk

### `drafts/*.json`
Lưu bản nháp email.

### `sent_emails/*.json`
Lưu log của email đã gửi thành công.

Lưu ý:
- file log chỉ là bằng chứng app đã gọi SMTP thành công,
- không phải mailbox thật của Gmail.

## 10. Điểm cần lưu ý khi mở rộng

Nếu muốn nâng cấp dự án, các hướng hợp lý là:
- thêm tool tìm kiếm web để lấy dữ liệu thời gian thực như giá BTC,
- thêm retry/fallback model khi Gemini bị `503`,
- thêm HTML email thay vì chỉ `text/plain`,
- thêm `cc`, `bcc`, attachment,
- thêm web UI bằng Streamlit hoặc FastAPI,
- thêm test tự động cho `tools.py` và `agent.py`.

## 11. Tóm tắt nhanh

Nếu nhìn dự án ở mức rất ngắn:
- `app.py` là giao diện CLI,
- `agent.py` là bộ não điều phối provider và tool calling,
- `prompts.py` là luật cho model,
- `tools.py` là nơi làm việc thật trên máy local như lưu nháp và gửi SMTP.
