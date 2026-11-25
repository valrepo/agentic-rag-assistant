# Contract: User interface (Streamlit)

Two tabs (FR-001). The UI only calls the services in [app-service.md](app-service.md).

## Tab "Knowledge"

- File picker: multiple files; accepted extensions shown (`.txt`, `.pdf`, `.md`).
- Button "Index files"; while running, `st.status` with one line per file.
- Result table: file name, status (`indexed (N chunks)`, with the note "already present"
  when the same content was indexed before, `rejected (reason)`, `failed (reason)`), duration.
- Overall message: success when at least one file was indexed and none failed; otherwise a
  warning or error naming the problem files (FR-010).
- Knowledge base contents list and "Clear knowledge base" button (SHOULD, FR-011).

## Tab "Ask"

- Text area for the question; button "Ask", disabled while a run is in progress.
- Processing indicator for the whole crew run (FR-014).
- Answer area:
  - `answered`: statements with inline citations `[file, chunk N, p. X]`, then an
    "Uncertain or missing" section if not empty.
  - `abstained`: exactly "I could not find this in the uploaded knowledge.", then an
    optional "Related passages" section listing chunk references only.
  - `failed`: the user message from the service.
- Retrieved chunks panel: rank, file, chunk id, page, score (FR-021).
- Request id shown under the answer (FR-023).
- If the knowledge base is empty: message asking to upload first; no crew run (FR-022).
