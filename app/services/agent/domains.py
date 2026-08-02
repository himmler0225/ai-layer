from app.services.agent.constants import _TIKTOK, _YOUTUBE

# Nguồn duy nhất cho danh sách domain/worker của multi-agent.
# Thêm/xoá domain (vd "instagram") chỉ cần sửa mảng này — build.py, nodes.py,
# supervisor.py đều tự suy ra danh sách + logic route từ đây, không hard-code
# tên domain ở đâu khác nữa.
#
# capabilities: loại ý định domain này phục vụ được — supervisor dùng để suy
#   ra "ý định X thì route domain nào" thay vì viết tay tên domain:
#   - "review": có thể tìm/tổng hợp review từ nguồn của domain
#   - "catalog": có thể tra cứu metadata/catalog phim
# mention_re: regex nhận diện domain được nhắc tên trong câu hỏi (None nếu
#   domain không có cách nhận diện qua từ khoá, như "movies" — nó được chọn
#   qua wants_catalog() ngữ nghĩa, không phải qua tên riêng).
#
# Vẫn cần làm thêm khi thêm domain mới (không tránh được, domain mới = năng
# lực mới):
#   1. Định nghĩa tool cho domain đó trong app/tools/*_definitions.py
#   2. Thêm key tương ứng vào TOOL_SETS trong app/tools/definitions.py
#   3. (Tuỳ chọn) thêm regex riêng (như _YOUTUBE/_TIKTOK) vào constants.py rồi
#      gán vào "mention_re" nếu muốn NLU tự phát hiện qua tên gọi — không có
#      vẫn dùng được qua tools="<id>" tường minh.
DOMAINS: list[dict] = [
    {
        "id": "youtube",
        "tool_set": "youtube",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia chuyên tra cứu thông tin trên Youtube - chỉ dùng tool youtube_*, không bàn Tiktok/phim",
        "search_tool": "youtube_search",
        "search_arg": "keyword",
        "capabilities": ["review"],
        "mention_re": _YOUTUBE,
    },
    {
        "id": "tiktok",
        "tool_set": "tiktok",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia chuyên tra cứu thông tin trên Tiktok - chỉ dùng tool tiktok_*, không bàn Youtube/phim",
        "search_tool": "tiktok_search",
        "search_arg": "keyword",
        "capabilities": ["review"],
        "mention_re": _TIKTOK,
    },
    {
        "id": "movies",
        "tool_set": "movies",
        "role_prompt": "[Vai trò] Bạn là một chuyên gia chuyên tra cứu thông tin về phim (kkphim/ophim), không bàn Youtube/Tiktok",
        "search_tool": None,
        "search_arg": None,
        "capabilities": ["catalog"],
        "mention_re": None,
    },
]

DOMAIN_IDS: list[str] = [d["id"] for d in DOMAINS]
DOMAIN_BY_ID: dict[str, dict] = {d["id"]: d for d in DOMAINS}
