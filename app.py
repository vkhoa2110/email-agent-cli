import sys

from agent import EmailDraftAgent


WELCOME = """
Email Draft Agent CLI
- Gõ yêu cầu soạn thư/email bằng tiếng Việt hoặc tiếng Anh.
- Có thể gửi email thật nếu bạn đã cấu hình SMTP và yêu cầu gửi rõ ràng.
- Hỗ trợ chọn provider qua biến môi trường LLM_PROVIDER=openai|gemini.
- Gõ /reset để xóa ngữ cảnh hội thoại hiện tại.
- Gõ /exit để thoát.
""".strip()


def _configure_console_encoding() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def main() -> None:
    _configure_console_encoding()

    try:
        agent = EmailDraftAgent()
    except Exception as exc:
        print(f"Không thể khởi động agent: {exc}")
        return

    print(WELCOME)
    print(f"Provider: {agent.provider} | Model: {agent.model}")
    print("-" * 60)

    while True:
        try:
            user_input = input("Bạn: ").strip()
        except EOFError:
            print("\nTạm biệt.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"/exit", "exit", "quit"}:
            print("Tạm biệt.")
            break

        if user_input.lower() == "/reset":
            agent.reset()
            print("Agent: Đã reset ngữ cảnh hội thoại.\n")
            continue

        try:
            result = agent.run_turn(user_input)
        except Exception as exc:
            print(f"Agent gặp lỗi: {exc}\n")
            continue

        print("\nAgent:\n")
        print(result["text"] or "(Không có nội dung trả về)")
        print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    main()
