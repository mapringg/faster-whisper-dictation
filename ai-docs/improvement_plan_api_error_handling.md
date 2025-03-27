# Improvement Plan: Enhance API Error Handling and Feedback

**Goal:** Improve the handling of errors received from the transcription APIs (OpenAI, Groq) by distinguishing between different error types, stopping retries for unrecoverable errors, and providing better feedback.

**Affected Files:**

- `src/services/transcriber.py`
- `src/core/app.py`
- `src/services/status_indicator.py`

**Steps:**

1.  **Refine `make_api_request` Error Handling (`transcriber.py`):**

    - Keep the existing retry loop and exponential backoff.
    - Inside the loop, after receiving a `response`:
      - **Success (200):** Process as before, return `result`.
      - **Rate Limit (429):** Process as before (log, sleep, continue retrying).
      - **Client Errors (4xx, excluding 429):**
        - `401 Unauthorized`: Log specific "Invalid API Key" error. `break` the retry loop.
        - `403 Forbidden`: Log specific "Permission Denied" error. `break` the retry loop.
        - `400 Bad Request`: Log "Bad Request" and include details from `response.text` if available. `break` the retry loop.
        - `413 Payload Too Large`: Log specific "Audio file too large" error (mention limit if known). `break` the retry loop.
        - _Other 4xx_: Log generic "Client Error [status_code]" with `response.text`. Consider breaking the loop as retries are unlikely to help.
      - **Server Errors (5xx):**
        - Log "Server Error [status_code]" with `response.text`. Continue retrying with backoff as implemented.
      - **Network Errors (`requests.exceptions.RequestException`):**
        - Log specific error type (e.g., `ConnectionError`, `Timeout`). Continue retrying with backoff.

2.  **Return Error Indication:**

    - Modify `make_api_request` to return a more informative value on failure, instead of just `None`. For example, return a tuple `(success: bool, result_or_error_info: dict | str)`.
    - On success: `return (True, response.json())`.
    - On retryable failure after max retries (e.g., persistent 5xx or network error): `return (False, "Max retries exceeded for server/network error")`.
    - On non-retryable client error (e.g., 401, 400): `return (False, "Client error: [details from response]")`.

3.  **Update `transcribe` Method (`transcriber.py`):**

    - Call `success, result_or_error = self.make_api_request(...)`.
    - Check `if success:`. If true, process `result_or_error` (the JSON result) as before and call `self.callback(segments=segments)`.
    - Check `else:`. If false:
      - Log the `result_or_error` string containing the error info.
      - Call `self.callback(segments=[], error=result_or_error)` - add an `error` parameter to the callback data.

4.  **Update `App` State Transition (`app.py`):**

    - Modify `App._on_enter_replaying` (which is triggered by `finish_transcribing`):
      - Check if `event.kwargs.get('error')` exists and is not None.
      - If an error exists:
        - Log the error.
        - Update the `StatusIcon` to the `ERROR` state (use queue/main thread).
        - Immediately transition back to `READY`: `self.m.to_READY()`.
        - Do _not_ proceed with replaying.
      - If no error:
        - Proceed with `self._safe_start_replay(event)` as before.

5.  **Update Status Icon (`status_indicator.py`):**
    - Ensure the `ERROR` state provides some generic error feedback in its tooltip (e.g., "Error during transcription. Check logs.").

**Rationale:** This provides more granular error handling. It prevents pointless retries for errors like invalid API keys or malformed requests. It also surfaces error information better, allowing the `App` to react appropriately (show error state, skip replay) instead of just failing silently or with empty results.
