import importlib
import os
import threading
import time

import gradio as gr

from config import CAFES_PATH, CHUNKS_PATH, DOCS_PATH
from retrieval import build_index, retrieve
from generator import generate_response

INGESTION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingestion.py")
WATCHED_FILES = [INGESTION_PATH, CAFES_PATH, CHUNKS_PATH]
APP_STAMP_PATH = os.path.join(DOCS_PATH, ".app_rebuild_manifest.json")
REBUILD_INTERVAL_SECONDS = 2.0

index_lock = threading.RLock()


def file_state(path):
    if not os.path.exists(path):
        return None
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def snapshot():
    return {path: file_state(path) for path in WATCHED_FILES}


def load_last_snapshot():
    try:
        import json
        with open(APP_STAMP_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return {path: tuple(state) if state is not None else None for path, state in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def save_snapshot():
    import json
    os.makedirs(DOCS_PATH, exist_ok=True)
    with open(APP_STAMP_PATH, "w", encoding="utf-8") as fh:
        json.dump(snapshot(), fh, indent=2)


def rebuild_pipeline(changed_paths=None):
    """Refresh derived files and rebuild Chroma for changed local inputs."""
    changed_paths = set(changed_paths or [])
    with index_lock:
        if INGESTION_PATH in changed_paths:
            print("ingestion.py changed - re-running ingestion, chunking, and Chroma rebuild.")
            import ingestion
            importlib.reload(ingestion)
            ingestion.build(force=True)
            build_index(rebuild=True)
        elif CAFES_PATH in changed_paths:
            print("cafes.json changed - rebuilding chunks and Chroma index.")
            import chunking
            importlib.reload(chunking)
            chunking.main()
            build_index(rebuild=True)
        elif CHUNKS_PATH in changed_paths:
            print("chunks.jsonl changed - rebuilding Chroma index.")
            build_index(rebuild=True)
        else:
            build_index()
        save_snapshot()


def watch_for_rebuilds():
    previous = snapshot()
    while True:
        time.sleep(REBUILD_INTERVAL_SECONDS)
        current = snapshot()
        changed = [path for path in WATCHED_FILES if current[path] != previous[path]]
        if changed:
            try:
                rebuild_pipeline(changed)
            except Exception as exc:
                print(f"Automatic rebuild failed: {exc}")
            finally:
                previous = snapshot()


last_snapshot = load_last_snapshot()
startup_snapshot = snapshot()
startup_changes = [
    path for path in WATCHED_FILES if startup_snapshot.get(path) != last_snapshot.get(path)
]

# Embed chunks.jsonl into ChromaDB on startup, then keep it current while the app
# is running when ingestion.py, cafes.json, or chunks.jsonl changes.
rebuild_pipeline(startup_changes)
threading.Thread(target=watch_for_rebuilds, daemon=True).start()


def handle_query(question):
    with index_lock:
        chunks = retrieve(question)
    answer = generate_response(question, chunks)
    # De-duplicate the cafes the answer was drawn from, preserving order.
    seen, sources = set(), []
    for c in chunks:
        cafe = c["metadata"].get("cafe", "?")
        if cafe not in seen:
            seen.add(cafe)
            sources.append(f"• {cafe}")
    return answer, "\n".join(sources)


with gr.Blocks() as demo:
    title = gr.Markdown("# ☕️ Find the best West LA cafe for study!")
    inp = gr.Textbox(label="Your question")
    btn = gr.Button("Ask")
    answer = gr.Textbox(label="Answer", lines=8)
    sources = gr.Textbox(label="Retrieved from", lines=4)
    btn.click(handle_query, inputs=inp, outputs=[answer, sources])
    inp.submit(handle_query, inputs=inp, outputs=[answer, sources])

demo.launch()
