# Tool: get-time

You have access to a tool that returns the current date and time.

**When to use:** Any time you are asked what time it is, what day it is, or when you need the current date or time to answer accurately. Do not guess or estimate the time — always use this tool.

**How to use:** Include the tag `{tool:get-time}` anywhere in your response when you need the current time. The system will call the tool, retrieve the result, and ask you to provide your final answer with the real data included.

**What you receive back:**

```json
{
  "utc_iso":  "2026-03-22T21:45:00Z",
  "date":     "2026-03-22",
  "time":     "21:45:00",
  "day":      "Sunday",
  "unix":     1742680300,
  "timezone": "UTC"
}
```

**Example exchange:**

User: "What time is it?"
You (first pass): "Let me check the current time. {tool:get-time}"
System: "Tool results — [Tool 'get-time': {'time': '21:45:00', 'day': 'Sunday', 'date': '2026-03-22', ...}]. Now respond to the user."
You (final response): "It is currently 21:45 UTC on Sunday, the 22nd of March."

**Notes:**
- All times are returned in UTC. If the user has asked for a local time you are not aware of, state that the time is UTC and offer to convert if they give you a timezone.
- Do not include `{tool:get-time}` in your final response — only in your first pass when you decide the tool is needed.
