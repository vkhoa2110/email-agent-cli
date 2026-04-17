# Email Draft Agent

Một agent CLI nhỏ để:
- hỏi thêm khi thiếu thông tin,
- soạn email,
- lưu draft ra file JSON trong thư mục `drafts/`,
- gửi email thật qua SMTP khi người dùng yêu cầu rõ là gửi,
- chạy linh động với `OpenAI` hoặc `Gemini` chỉ bằng cấu hình `.env`.

## Cấu trúc thư mục

```text
email_draft_agent/
├── app.py
├── agent.py
├── prompts.py
├── tools.py
├── requirements.txt
├── .env.example
├── drafts/
└── sent_emails/
```

## 1. Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Cấu hình provider và API key

Copy file mẫu:

```bash
cp .env.example .env
```

Sau đó sửa `.env` theo provider bạn muốn dùng:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Hoặc:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4
```

Lưu ý:
- Với Gemini, app ưu tiên `GEMINI_API_KEY` trong project nhưng vẫn chấp nhận `GOOGLE_API_KEY` nếu máy đã có sẵn.
- Nếu model Gemini đang quá tải, bạn có thể thử `GEMINI_MODEL=gemini-2.5-flash-lite`.

## 3. Cấu hình gửi email qua Gmail SMTP

Thêm vào `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_FROM_NAME=Your Name
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password_here
```

Lưu ý:
- Với Gmail, `SMTP_PASSWORD` phải là App Password, không phải mật khẩu đăng nhập Gmail thường.
- Nếu chưa bật 2-Step Verification trên tài khoản Google thì bạn sẽ chưa tạo được App Password.
- Khi gửi thành công, app sẽ lưu log vào `sent_emails/`.

## 4. Chạy app

```bash
python app.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python app.py
```

App sẽ in provider và model hiện tại khi khởi động.

## 5. Cách dùng

Ví dụ chỉ soạn draft:

```text
Soạn email xin dời lịch họp tối nay sang ngày mai, giọng lịch sự, gửi cho vankhoa373737@gmail.com.
```

Ví dụ gửi thật:

```text
Gửi email cho vankhoa373737@gmail.com với nội dung chào hỏi ngắn, lịch sự.
```

Agent chỉ gửi email khi bạn yêu cầu rõ là gửi. Nếu bạn chỉ nói “soạn”, app sẽ chỉ lưu draft.

## 6. Kết quả nằm ở đâu

- Draft được lưu trong `drafts/`
- Email gửi thành công được log trong `sent_emails/`

Ví dụ draft:

```text
drafts/draft_ab12cd34.json
```

Ví dụ log gửi:

```text
sent_emails/sent_ab12cd34.json
```

## 7. Lệnh hữu ích

- `/reset`: xóa ngữ cảnh cuộc hội thoại hiện tại.
- `/exit`: thoát chương trình.
