# PyAIL chat integration and export design

Status: implemented

The implementation described here is available on `PyAIL`; this document
records the current behavior rather than a future proposal.

## Public API

The existing `PyAIL` client and its `_prepare_request()` / `_check_json_response()`
pipeline remain the only HTTP client architecture.

Low-level, one-page methods:

```python
get_chat_instances(page=1, page_size=50)
get_chats(instance_uuid, languages=None, page=1, page_size=50)
get_chat_messages(instance_uuid, id, languages=None, page=1, page_size=500)
get_chat_subchannel_messages(instance_uuid, id, languages=None,
                             page=1, page_size=500)
get_chat_thread_messages(instance_uuid, id, languages=None,
                         page=1, page_size=500)
```

High-level methods:

```python
get_chat_content(instance_uuid, id, languages=None, page_size=500)
export_chat(instance_uuid, id, output_directory, languages=None,
            page_size=500)
export_chat_instance(instance_uuid, output_directory, languages=None,
                     page_size=500, discovery_page_size=50)
```

`languages` accepts a comma-separated string or a sequence. PyAIL does not
validate the tags: it passes them unchanged to every applicable request so AIL
can validate them.

## Traversal and schemas

Each container is fetched from page 1 through its own reported `page_count`.
Message arrays are appended, without sorting, under their server-provided date
keys. The first chat response discovers direct threads and subchannels; the
first response for each subchannel discovers that subchannel's direct threads.

A complete chat document has this shape:

```json
{
  "chat": {},
  "messages": {"YYYY/MM/DD": []},
  "subchannels": [
    {
      "subchannel": {},
      "messages": {"YYYY/MM/DD": []},
      "threads": [{"thread": {}, "messages": {"YYYY/MM/DD": []}}]
    }
  ],
  "threads": [{"thread": {}, "messages": {"YYYY/MM/DD": []}}]
}
```

The original IDs remain in the metadata objects. An instance export writes no
complete chat data to `metadata.json`; it contains the instance metadata,
language and page-size options, and an ordered `chats` list mapping each
original ID to a relative JSON filename.

## Filesystem behavior

Single-chat exports and files within instance exports use the sanitized original
chat ID as `<sanitized-chat-id>.json`. Instance exports create a
`<sanitized-instance-uuid>/` root under `output_directory`. Sanitization uses a
conservative ASCII allowlist, so path separators, traversal components, control
characters, and platform-sensitive punctuation cannot escape the export root.
If two different chat IDs produce the same filename, a random UUIDv4 is appended
to the later colliding name. `metadata.json` records every original ID and final
relative filename, and the original unsanitized ID remains in each chat's
metadata.

Exports overwrite an existing destination. Data is first written to a temporary
sibling. A failed API request, malformed paginated response, or filesystem write
removes that staging path and leaves the existing final destination untouched.
A fully staged export replaces the old file or directory only after collection
succeeds. `export_chat()` returns the created JSON file path;
`export_chat_instance()` returns the sanitized instance directory path.

## Implementation status

- The five low-level methods use the existing request and JSON-response helpers.
- `get_chat_content()` assembles all independently paginated containers in
  memory and is shared by both export methods.
- `export_chat()` writes one sanitized JSON filename and returns that file path.
- `export_chat_instance()` paginates chat discovery, writes `metadata.json` and
  one file per chat beneath `chats/`, and returns the sanitized instance root.
- Export writes are staged and existing destinations are replaced only after a
  complete export has been assembled successfully.

## Test coverage

The implemented tests mock the established request helper for endpoint and
parameter checks. Scripted low-level responses cover multi-page hierarchy
traversal, language propagation, empty data, and mid-export failures. Temporary
directories cover unsafe and colliding IDs, UUIDv4 collision suffixes, original
ID preservation, traversal prevention, return values, and destination
replacement.
