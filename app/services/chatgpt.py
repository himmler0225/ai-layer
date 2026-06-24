"""Re-export hàm gọi OpenAI trả text/JSON."""

from app.utils.openai_responses import complete, complete_json

__all__ = ["complete", "complete_json"]
