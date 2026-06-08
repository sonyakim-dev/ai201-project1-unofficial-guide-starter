"""
Milestone 3 (part 1): Document ingestion / cleaning.

Each file in documents/ is a ~2 MB saved Yelp page. We do NOT keep the page.
Instead we extract only the three things that matter for the cafe-finder RAG:

  1. Business facts   -> from the JSON-LD <script> block (name, address, rating, phone)
  2. Amenities        -> from Yelp's hydration JSON ("displayText"/"alias" pairs)
  3. Reviews          -> from the <p class="comment..."> spans (~10-20 per page)

Everything else (CSS, nav, footer, images, buttons, ads, "people also viewed")
is discarded by construction -- we never include it in the first place.

Input:  documents/raw/*.html   (the saved Yelp pages)
Outputs (written to documents/):
  - documents/<cafe>.txt    human-readable clean copy, for eyeballing quality
  - documents/cafes.json    structured records consumed by the chunking step
"""

import glob
import html as ht
import json
import os
import re
from urllib.parse import unquote

from config import (CAFES_PATH, CHUNKS_PATH, DOCS_PATH, RAW_DOCS_PATH,
                    STAMP_PATH)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIME_RANGE = r"\d{1,2}:\d{2}\s?[AP]M\s*-\s*\d{1,2}:\d{2}\s?[AP]M|Closed"

# Map keyword(s) found in amenity text -> a boolean metadata flag.
# These flags let the retrieval step filter exactly ("which cafes have wifi?")
# instead of relying on fuzzy embedding similarity.
AMENITY_FLAGS = {
    "has_wifi":            ["wi-fi", "wifi"],
    "good_for_working":    ["good for working"],
    "has_outdoor_seating": ["outdoor seating"],
    "has_parking":         ["parking"],
    "free_street_parking": ["street parking"],
    "wheelchair_access":   ["wheelchair"],
    "ada_restroom":        ["ada-compliant restroom", "restroom"],
    "dogs_allowed":        ["dogs allowed"],
    "has_tv":              ["tv"],
    "drive_thru":          ["drive-thru"],
    "offers_delivery":     ["offers delivery"],
    "offers_takeout":      ["take-out", "takeout"],
    "accepts_credit":      ["accepts credit"],
}


def extract_business(raw):
    """Pull name / address / rating / phone from the JSON-LD block."""
    name = address = phone = None
    rating = review_count = None
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if "aggregateRating" not in item:
                continue
            name = ht.unescape(item.get("name") or "")
            phone = item.get("telephone")
            a = item.get("address") or {}
            address = ", ".join(
                re.sub(r"\s+", " ", p).strip()
                for p in [
                    a.get("streetAddress"),
                    a.get("addressLocality"),
                    a.get("addressRegion"),
                    a.get("postalCode"),
                ] if p
            )
            ar = item.get("aggregateRating") or {}
            rating = ar.get("ratingValue")
            review_count = ar.get("reviewCount")
    return name, address, phone, rating, review_count


def extract_amenities(raw):
    """Yelp stores amenity attributes as escaped JSON: displayText + alias."""
    txt = ht.unescape(raw)
    seen, out = set(), []
    for display, _alias in re.findall(r'"displayText":"([^"]+)","alias":"([^"]+)"', txt):
        display = display.strip()
        if display and display not in seen:
            seen.add(display)
            out.append(display)
    return out


def derive_flags(amenities):
    blob = " | ".join(amenities).lower()
    return {flag: any(kw in blob for kw in kws) for flag, kws in AMENITY_FLAGS.items()}


def extract_hours(raw):
    """Hours live in Yelp's hydration JSON as one OperationHoursForADayOfWeek
    object per day: {"hours":["9:00 AM - 12:00 AM (Next day)"], ...,
    "dayOfWeekShort":"Mon"}. We take the hours string(s) verbatim — whatever Yelp
    displays, including the "(Next day)" past-midnight marker — rather than
    re-parsing a fixed time format from the visible table."""
    txt = ht.unescape(raw)
    hours = {}
    for body, day in re.findall(
        r'"hours":\[([^\]]*)\][^{}]*?"dayOfWeekShort":"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)"',
        txt,
    ):
        ranges = re.findall(r'"([^"]+)"', body)   # one string, or several for split hours
        if ranges and day not in hours:           # keep the first object per day
            hours[day] = ", ".join(ranges)
    return hours


def format_hours(hours):
    """Collapse consecutive same-hours days: 'Mon-Fri 7:00 AM - 8:00 PM; Sat-Sun ...'."""
    if not hours:
        return None
    groups = []
    for d in DAYS:
        if d not in hours:
            continue
        v = hours[d]
        if groups and groups[-1][2] == v and DAYS.index(d) == DAYS.index(groups[-1][1]) + 1:
            groups[-1][1] = d
        else:
            groups.append([d, d, v])
    return "; ".join((a if a == b else f"{a}-{b}") + f" {v}" for a, b, v in groups)

def extract_website(raw):
    """Business website is an outbound Yelp redirect: /biz_redir?url=<encoded>."""
    m = re.search(r"biz_redir\?url=([^&\"']+)", raw)
    return unquote(m.group(1)) if m else None


def parse_last_updated(filename):
    """Filenames look like '... - Updated June 2026 - ...'."""
    m = re.search(r"Updated\s+([A-Z][a-z]+\s+\d{4})", filename)
    if m:
        return m.group(1)
    m = re.search(r"([A-Z][a-z]+\s+\d{4})", filename)
    return m.group(1) if m else None


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_id(name, address):
    """Location-aware id: the same cafe name can appear at different locations,
    so we fold the street address into the id to keep them distinct."""
    street = address.split(",")[0] if address else ""
    return slugify(f"{name}-{street}") or slugify(name)


def extract_reviews(raw):
    """Review text lives in <p class="comment..."><span>...</span>."""
    reviews = []
    for span in re.findall(r'<p class="comment[^"]*"[^>]*>\s*<span[^>]*>(.*?)</span>', raw, re.S):
        text = re.sub(r"<br\s*/?>", " ", span)   # line breaks -> spaces
        text = re.sub(r"<[^>]+>", " ", text)     # drop any remaining tags
        text = re.sub(r"\s+", " ", ht.unescape(text)).strip()
        if len(text) >= 40:                      # skip empty / stub spans
            reviews.append(text)
    return reviews


def raw_state():
    """Fingerprint of the raw folder: {filename: [mtime, size]}."""
    state = {}
    for path in glob.glob(os.path.join(RAW_DOCS_PATH, "*.html")):
        st = os.stat(path)
        state[os.path.basename(path)] = [st.st_mtime, st.st_size]
    return state


def is_stale():
    """True if a raw file was added, removed, or modified since the last build,
    or if any derived output is missing."""
    if not (os.path.exists(STAMP_PATH)
            and os.path.exists(CAFES_PATH)
            and os.path.exists(CHUNKS_PATH)):
        return True
    try:
        with open(STAMP_PATH, encoding="utf-8") as fh:
            return json.load(fh) != raw_state()
    except (json.JSONDecodeError, OSError):
        return True


def clean():
    os.makedirs(DOCS_PATH, exist_ok=True)
    files = sorted(glob.glob(os.path.join(RAW_DOCS_PATH, "*.html")))
    if not files:
        raise SystemExit(f"No .html files found in {RAW_DOCS_PATH}")

    cafes = []
    for path in files:
        raw = open(path, encoding="utf-8", errors="ignore").read()
        name, address, phone, rating, review_count = extract_business(raw)
        amenities = extract_amenities(raw)
        reviews = extract_reviews(raw)
        hours = extract_hours(raw)
        website = extract_website(raw)
        fname = os.path.basename(path)
        name = name or fname.split(" - ")[0].title()
        last_updated = parse_last_updated(fname)
        cafe_id = make_id(name, address)

        record = {
            "id": cafe_id,
            "name": name,
            "address": address,
            "phone": phone,
            "rating": rating,
            "review_count": review_count,
            "last_updated": last_updated,
            "website": website,
            "hours": hours,
            "hours_summary": format_hours(hours),
            "amenities": amenities,
            "flags": derive_flags(amenities),
            "reviews": reviews,
            "source_file": fname,
        }
        cafes.append(record)

        # Human-readable clean copy
        slug = cafe_id
        lines = [
            f"=== {name} ===",
            f"Address: {address}",
            f"Rating: {rating} ({review_count} reviews)",
            f"Phone: {phone}",
            f"Website: {website or '(N/A)'}",
            f"Hours: {format_hours(hours) or '(N/A)'}",
            f"Last updated: {last_updated}",
            "",
            "Amenities: " + (", ".join(amenities) if amenities else "(N/A)"),
            "",
        ]
        for i, r in enumerate(reviews, 1):
            lines.append(f"Review {i}: {r}")
        with open(os.path.join(DOCS_PATH, f"{slug}.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    with open(CAFES_PATH, "w", encoding="utf-8") as fh:
        json.dump(cafes, fh, ensure_ascii=False, indent=2)

    print(f"Extracted {len(cafes)} cafes -> {CAFES_PATH}")
    print(f"Clean text files -> {DOCS_PATH}/")
    print()
    for c in cafes:
        n_flags = sum(c["flags"].values())
        print(f"  {c['name'][:28]:30} rating={c['rating']:>3} "
              f"amenities={len(c['amenities']):>2} reviews={len(c['reviews']):>2} flags={n_flags}")


def build(force=False):
    """Re-clean only when the raw folder changed, then rebuild the chunks so
    chunks.jsonl never goes stale relative to the raw pages."""
    if not force and not is_stale():
        print("Raw documents unchanged — nothing to rebuild.")
        return False
    clean()
    import chunking  # rebuild chunks.jsonl from the fresh cafes.json
    chunking.main()
    with open(STAMP_PATH, "w", encoding="utf-8") as fh:
        json.dump(raw_state(), fh, indent=2)
    return True


def watch(interval=5.0):
    """Poll the raw folder and rebuild whenever a file is added/changed/removed."""
    import time
    print(f"Watching {RAW_DOCS_PATH} every {interval:g}s — Ctrl+C to stop.")
    build()                                   # initial build if needed
    try:
        while True:
            time.sleep(interval)
            if is_stale():
                print("\nChange detected — rebuilding...")
                build()
    except KeyboardInterrupt:
        print("\nStopped watching.")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--watch" in args:
        watch()
    else:
        build(force="--force" in args)
