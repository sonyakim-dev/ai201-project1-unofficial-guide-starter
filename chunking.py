"""
Milestone 3 (part 2): Chunking.

Reads documents/cafes.json (produced by clean_documents.py) and emits
documents/chunks.jsonl -- one chunk per line, ready for embedding.

Chunking is structure-aware, not a fixed token window:
  - 1 "fact_card" chunk per cafe  (name + address + rating + full amenities)
  - 1 "review"    chunk per review

Every chunk is prefixed with the cafe name (retrievable + self-attributing)
and carries flat metadata (scalars only, as ChromaDB requires) so retrieval
can filter exactly -- e.g. where={"has_wifi": True} -- and not just by
embedding similarity. No overlap: each chunk is a self-contained record.
"""

import json

from config import CAFES_PATH as CAFES
from config import CHUNKS_PATH as OUT


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def cafe_metadata(c):
    """Cafe-level scalars attached to every chunk for that cafe.
    ChromaDB metadata values must be str / int / float / bool."""
    meta = {
        "cafe": c["name"],
        "cafe_id": c["id"],
        "rating": to_float(c.get("rating")),
        "review_count": to_int(c.get("review_count")),
        "last_updated": c.get("last_updated"),
        "website": c.get("website"),
        "hours_summary": c.get("hours_summary"),
        "source_file": c.get("source_file"),
    }
    meta.update(c.get("flags", {}))          # has_wifi, good_for_working, ...
    return {k: v for k, v in meta.items() if v is not None}


def fact_card_text(c):
    head = c["name"]
    if c.get("address"):
        head += f" ({c['address']})"
    bits = [head + " —"]
    if c.get("rating"):
        bits.append(f"{c['rating']}★ from {c.get('review_count', '?')} reviews.")
    if c.get("hours_summary"):
        bits.append(f"Hours: {c['hours_summary']}.")
    if c.get("amenities"):
        bits.append("Amenities: " + ", ".join(c["amenities"]) + ".")
    if c.get("website"):
        bits.append(f"Website: {c['website']}.")
    if c.get("last_updated"):
        bits.append(f"(Updated {c['last_updated']})")
    return " ".join(bits)


def main():
    with open(CAFES, encoding="utf-8") as fh:
        cafes = json.load(fh)

    chunks = []
    for c in cafes:
        base = cafe_metadata(c)

        # 1) fact card
        chunks.append({
            "id": f"{c['id']}#card",
            "type": "fact_card",
            "text": fact_card_text(c),
            **base,
        })

        # 2) one chunk per review, prefixed with the cafe name
        for i, review in enumerate(c.get("reviews", []), 1):
            chunks.append({
                "id": f"{c['id']}#r{i}",
                "type": "review",
                "text": f"{c['name']} — {review}",
                **base,
            })

    with open(OUT, "w", encoding="utf-8") as fh:
        for ch in chunks:
            fh.write(json.dumps(ch, ensure_ascii=False) + "\n")

    n_cards = sum(1 for c in chunks if c["type"] == "fact_card")
    n_revs = sum(1 for c in chunks if c["type"] == "review")
    print(f"Wrote {len(chunks)} chunks -> {OUT}")
    print(f"  fact cards: {n_cards}")
    print(f"  reviews:    {n_revs}")


if __name__ == "__main__":
    main()
