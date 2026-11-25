"""Streamlit UI (contracts/ui.md). Rendering, input, and progress state only.

Run with: uv run streamlit run app/ui.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# `streamlit run app/ui.py` puts app/ on sys.path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app.config import Config  # noqa: E402
from app.errors import SUPPORTED_EXTENSIONS, AppError  # noqa: E402
from app.guardrail import SAFE_RESPONSE  # noqa: E402
from app.service import (  # noqa: E402
    FileResult,
    QuestionRunResult,
    Services,
    UploadedFile,
    build_services,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@st.cache_resource(show_spinner="Starting services...")
def get_services() -> Services:
    return build_services(Config.from_env())


def _status_label(result: FileResult) -> str:
    if result.status == "indexed":
        label = f"indexed ({result.chunk_count} chunks)"
        return label + ", already present" if result.already_present else label
    return f"{result.status} ({result.reason})"


def knowledge_tab(services: Services) -> None:
    st.subheader("Upload knowledge files")
    supported = ", ".join(SUPPORTED_EXTENSIONS)
    st.caption(f"Supported types: {supported}. Other files are rejected.")
    uploads = st.file_uploader(
        "Choose one or more files", accept_multiple_files=True, key="uploader"
    )
    if st.button("Index files", type="primary", disabled=not uploads):
        results: list[FileResult] = []
        with st.status("Indexing files...", expanded=True) as status:
            for upload in uploads:
                st.write(f"{upload.name}: processing")
                result = services.knowledge.ingest(
                    [UploadedFile(name=upload.name, data=upload.getvalue())]
                )[0]
                results.append(result)
                st.write(f"{upload.name}: {_status_label(result)}")
            status.update(label="Indexing finished", state="complete", expanded=False)
        st.session_state["last_results"] = results

    results = st.session_state.get("last_results")
    if results:
        st.table(
            [
                {
                    "File": r.original_name,
                    "Status": _status_label(r),
                    "Message": r.user_message or "",
                    "Duration (ms)": r.duration_ms,
                }
                for r in results
            ]
        )
        indexed = [r for r in results if r.status == "indexed"]
        problems = [r.original_name for r in results if r.status != "indexed"]
        if indexed and not problems:
            st.success(f"{len(indexed)} file(s) indexed successfully.")
        elif indexed:
            st.warning(f"{len(indexed)} file(s) indexed. Not indexed: {', '.join(problems)}.")
        else:
            st.error(f"No file was indexed. Problem files: {', '.join(problems)}.")

    st.subheader("Knowledge base contents")
    files = services.knowledge.list_files()
    if files:
        st.table([{"File": f.source_file, "Chunks": f.chunk_count} for f in files])
        if st.button("Clear knowledge base"):
            services.knowledge.clear()
            st.session_state.pop("last_results", None)
            st.rerun()
    else:
        st.info("The knowledge base is empty.")


def _render_answer(run: QuestionRunResult) -> None:
    answer = run.answer
    if run.status == "failed" or answer is None:
        st.error(run.user_message or "The question could not be answered.")
    elif run.status == "abstained":
        st.warning(SAFE_RESPONSE)
        if answer.related_passages:
            st.markdown("**Related passages**")
            for chunk in answer.related_passages:
                st.markdown(f"- {chunk.reference()}")
    else:
        st.markdown("**Answer**")
        for statement in answer.statements:
            refs = " ".join(c.reference() for c in statement.citations)
            st.markdown(f"- {statement.text} {refs}")
        if answer.uncertain:
            st.markdown("**Uncertain or missing**")
            for item in answer.uncertain:
                st.markdown(f"- {item}")

    if run.retrieved:
        with st.expander("Retrieved chunks", expanded=run.status != "answered"):
            st.table(
                [
                    {
                        "Rank": c.rank,
                        "File": c.source_file,
                        "Chunk id": c.chunk_id,
                        "Page": str(c.page) if c.page is not None else "-",
                        "Score": f"{c.score:.3f}",
                        "Evidence": "yes" if c.above_min_score else "below minimum score",
                    }
                    for c in run.retrieved
                ]
            )
    trace = f" | Trace id: `{run.trace_id}`" if run.trace_id else ""
    st.caption(f"Request id: `{run.request_id}`{trace}")


def _start_run() -> None:
    st.session_state["running"] = True


def ask_tab(services: Services) -> None:
    if services.knowledge.is_empty():
        st.info("The knowledge base is empty. Upload and index knowledge files first.")
        return
    # Clicking "Ask" only sets the flag; the rerun that follows renders the input and the
    # button disabled while the crew runs, then a final rerun enables them again.
    running = st.session_state.get("running", False)
    st.text_area("Your question", key="question", disabled=running)
    st.button("Ask", type="primary", disabled=running, on_click=_start_run)
    if running:
        try:
            with st.status("The agents are searching and verifying...", expanded=False) as status:
                st.session_state["last_run"] = services.answers.ask(
                    st.session_state.get("question", "")
                )
                st.session_state.pop("last_error", None)
                status.update(label="Done", state="complete")
        except AppError as exc:
            st.session_state.pop("last_run", None)
            st.session_state["last_error"] = exc.user_message
        finally:
            st.session_state["running"] = False
        st.rerun()
    if st.session_state.get("last_error"):
        st.error(st.session_state["last_error"])
    run = st.session_state.get("last_run")
    if run is not None:
        _render_answer(run)


def main() -> None:
    st.set_page_config(page_title="Agentic RAG Knowledge Assistant")
    st.title("Agentic RAG Knowledge Assistant")
    st.caption("Local development tool: no authentication. Answers use only uploaded knowledge.")
    services = get_services()
    knowledge, ask = st.tabs(["Knowledge", "Ask"])
    with knowledge:
        knowledge_tab(services)
    with ask:
        ask_tab(services)


main()
