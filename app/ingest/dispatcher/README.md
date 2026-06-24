# Dispatcher

Sau mỗi tool call của agent → quyết định publish job nào.

## Flow

```
schedule_tool_ingest(tool, inputs, result, task)
    → unwrap_result()
    → routes.route_tool()   # map tool name → publish.*
    → producer.publish()
```

`product_hint` = câu hỏi hiện tại (tối đa 120 ký tự), gắn metadata RAG.

Gọi từ `app/services/agent.py` — không block nếu RabbitMQ down.
