"""
Milestone 4: Embedding + Vector Store + Retrieval.

Reads documents/chunks.jsonl (produced by chunking.py), embeds each chunk's
`text` with all-MiniLM-L6-v2, and loads them into a persistent ChromaDB
collection. Every chunk's flat metadata (cafe, rating, hours_summary, the
boolean amenity flags, source_file, ...) is stored alongside it so retrieval
can filter exactly with a ChromaDB `where` clause, not only by similarity.

  build_index()              -> embed + (re)load chunks.jsonl into ChromaDB
  retrieve(query, k=5, where=...)  -> top-k chunks, with optional metadata filter

The same SentenceTransformer model embeds both the stored chunks and the
incoming query (Chroma calls the embedding function on query_texts), so the
two live in the same vector space.

CLI:
  python retrieval.py            # build index if empty, then run sample queries
  python retrieval.py --rebuild  # drop and re-embed everything from scratch
"""

import json

import chromadb
from chromadb.utils import embedding_functions
from config import (CHROMA_COLLECTION, CHROMA_PATH, CHUNKS_PATH,
                    EMBEDDING_MODEL, N_RESULTS)

# Keys that are the chunk itself, not filterable metadata.
NON_META = {"id", "text"}

_embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)


def load_chunks(path=CHUNKS_PATH):
    """Read chunks.jsonl into ids / documents / metadatas, the three parallel
    lists ChromaDB's add() expects."""
    ids, docs, metas = [], [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ch = json.loads(line)
            ids.append(ch["id"])
            docs.append(ch["text"])
            # Everything except id/text is scalar metadata (chunking.py already
            # dropped Nones and kept only str/int/float/bool, as Chroma requires).
            metas.append({k: v for k, v in ch.items() if k not in NON_META})
    return ids, docs, metas

def get_collection(client=None):
    """Open (or create) the cafes collection bound to the MiniLM embedder.
    Binding the embedding function here means query_texts are embedded with the
    same model that embedded the documents."""
    client = client or chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=_embedder,
        metadata={"hnsw:space": "cosine"},   # cosine matches sentence-transformers
    )


def build_index(rebuild=False, batch_size=128):
    """Embed every chunk and upsert it into ChromaDB.

    Idempotent: a normal run only embeds when the collection is empty or its
    count no longer matches chunks.jsonl. Pass rebuild=True to drop and rebuild.
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    if rebuild:
        try:
            client.delete_collection(CHROMA_COLLECTION)
        except Exception:
            pass

    col = get_collection(client)
    ids, docs, metas = load_chunks()

    if not rebuild and col.count() == len(ids):
        print(f"Index already current ({col.count()} chunks) — nothing to embed.")
        return col

    print(f"Embedding {len(ids)} chunks with {EMBEDDING_MODEL} ...")
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        col.upsert(
            ids=ids[start:end],
            documents=docs[start:end],
            metadatas=metas[start:end],
        )
        print(f"  upserted {min(end, len(ids))}/{len(ids)}")

    print(f"Done. Collection '{CHROMA_COLLECTION}' holds {col.count()} chunks -> {CHROMA_PATH}/")
    return col


def retrieve(query, k=N_RESULTS, where=None, where_document=None):
    """Return the top-k chunks for `query`.

    query          natural-language question
    k              number of chunks to return (planning.md targets 5-8)
    where          optional exact metadata filter, e.g. {"has_wifi": True}
                   or {"cafe_id": "dialog-cafe-1835-s-sepulveda-blvd"}
    where_document optional full-text filter, e.g. {"$contains": "outlets"}

    Each result: {"id", "text", "metadata", "distance"} (lower distance = closer).
    """
    col = get_collection()
    res = col.query(
        query_texts=[query],
        n_results=k,
        where=where or None,
        where_document=where_document or None,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for i in range(len(res["ids"][0])):
        out.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            "distance": res["distances"][0][i],
        })
    return out


def _print_hits(query, hits):
    print(f"\nQ: {query}")
    for h in hits:
        m = h["metadata"]
        tag = f"[{m.get('type', '?')}] {m.get('cafe', '?')}"
        print(f"  {h['distance']:.3f}  {tag}")
        print(f"         {h['text'][:140]}{'...' if len(h['text']) > 140 else ''}")


def _demo():
    """Sanity-check against a few of the planning.md eval questions."""
    _print_hits(
        "Does Dialog Cafe have wifi and what are its hours?",
        retrieve("Does Dialog Cafe have wifi and what are its hours?", k=3),
    )
    # Attribute question -> exact metadata filter, not just similarity.
    _print_hits(
        "Which cafes are good for working on a laptop? (filtered: good_for_working)",
        retrieve("good for working on a laptop", k=8,
                 where={"$and": [{"good_for_working": True}, {"type": "fact_card"}]}),
    )
    # Review-only fact (outlets aren't in Yelp's amenity list).
    _print_hits(
        "Do reviewers mention power outlets at 10 Speed Coffee?",
        retrieve("power outlets", k=3, where_document={"$contains": "outlet"}),
    )


if __name__ == "__main__":
    import sys
    build_index(rebuild="--rebuild" in sys.argv[1:])
    # _demo()
