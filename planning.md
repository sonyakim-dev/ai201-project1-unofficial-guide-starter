# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->

**Finding the Best West LA cafe for study !**

I have been going to all the different cafes in West LA and all cafes have different condition. Once I prompt a cafe name, I want to know if the cafe has wifi/outlets/free parking/restroom/seating/etc. Or I want to get a list of cafes if I am looking for a cafe that has a specific condition.

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| #   | Source | Description          | URL or location                                                                                   |
| --- | ------ | -------------------- | ------------------------------------------------------------------------------------------------- |
| 1   | Yelp   | 10 Speed Coffee      | https://www.yelp.com/biz/10-speed-coffee-sawtelle-los-angeles-2?osq=10+Speed+Coffee+Sawtelle      |
| 2   | Yelp   | Board House Coffee   | https://www.yelp.com/biz/board-house-coffee-los-angeles?osq=Board+House+Coffee                    |
| 3   | Yelp   | Bolivar Coffee       | https://www.yelp.com/biz/bolivar-coffee-arepa-bar-santa-monica-4?osq=bolivar+coffee+%2B+arepa+bar |
| 4   | Yelp   | Bonsai Coffee Bar    | https://www.yelp.com/biz/bonsai-coffee-bar-los-angeles-5?osq=Bonsai+Coffee+Bar                    |
| 5   | Yelp   | Dialog Cafe          | https://www.yelp.com/biz/dialog-cafe-los-angeles-5?osq=Dialog+Cafe                                |
| 6   | Yelp   | Expressoteric Coffee | https://www.yelp.com/biz/espressoteric-coffee-los-angeles-5?osq=Espressoteric+Coffee              |
| 7   | Yelp   | Motoring Coffee      | https://www.yelp.com/biz/motoring-coffee-los-angeles?osq=Motoring+Coffee                          |
| 8   | Yelp   | Noun                 | https://www.yelp.com/biz/noun-marina-del-rey-2?osq=Noun                                           |
| 9   | Yelp   | Organico             | https://www.yelp.com/biz/organico-los-angeles-7?osq=organico                                      |
| 10  | Yelp   | The Boy & The Bear   | https://www.yelp.com/biz/the-boy-and-the-bear-los-angeles-7?osq=The+Boy+%26+The+Bear              |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:** Structure-aware (one semantic unit per chunk, not a fixed token window)

- **Fact card** — one per cafe: name + address + rating + hours + full amenities list + website
- **Review** — one per review, each prefixed with the cafe name

Every chunk also carries flat metadata (`cafe_id`, `rating`, `hours_summary`, and boolean amenity flags like `has_wifi`, `good_for_working`) so retrieval can filter exactly, not just by similarity.

**Overlap:** None. Here each chunk is already a discrete, self-contained record, so there is nothing to bleed across a boundary.

**Reasoning:**
The raw HTML files are ~2 MB each and full of noise (header, footer, CSS, images, buttons, ads, "people also viewed"). Rather than strip tags off the whole page, I extract only the three things that matter and discard everything else by construction:

- **Business metadata** — from `<script>` block: name, address, rating, phone (hours and website are scraped from the page body).
- **Amenities** — structured flags (Free Wi-Fi, Outdoor seating, Valet/Garage/Street parking, ADA-compliant restroom, "Good for working"…), embedded as `"displayText":"Free Wi-Fi","alias":"wifi_..."`.
- **Reviews** — from `<p class="comment...">`, ~10–21 per page, 4–5 sentences each.

I chunk one review per chunk for two reasons: (1) `all-MiniLM-L6-v2` truncates at 256 tokens, so a merged 20-review block would be silently cut off; (2) one focused vector per review keeps specific signals (e.g. a single mention of "outlets") from being averaged away.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:** `all-MiniLM-L6-v2`

**Top-k:** 5–8. Small enough to stay grounded, large enough that a "which cafes…" query pulls in several different cafes.

**Production tradeoff reflection:**
If cost weren't a constraint I'd weigh:

- **Context length** — MiniLM's 256-token cap forces review-level chunking. A longer-context model would let me embed whole-cafe chunks without truncation, simplifying retrieval at some cost to precision.
- **Domain accuracy** — a larger model captures nuanced review language (sarcasm, "great except…") more faithfully, improving ranking on subjective queries.
- **Multilingual** — some reviews contain non-English phrases; a multilingual model would handle those instead of treating them as near-noise.
- **Latency & privacy** — local MiniLM is instant and keeps review text on-device; a hosted API adds network latency, rate limits, and sends data to a third party. For a small personal tool, local wins; at scale the accuracy gains might justify the API.

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| #   | Question                                               | Expected answer                                                                                                                                                             |
| --- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Does Dialog Cafe have Wi-Fi, and what are its hours?   | Yes — Free Wi-Fi. Hours: Mon–Fri 7:00 AM–8:00 PM, Sat–Sun 7:00 AM–5:00 PM. (It's located behind the Equinox front desk.)                                                    |
| 2   | Which cafes are good for working on a laptop?          | Cafes tagged "Good for working": 10 Speed, Board House, Bolivar, Bonsai, Espressoteric, Motoring, The Boy & The Bear. (Reviews also confirm 10 Speed for laptop work.)      |
| 3   | Do reviewers mention power outlets at 10 Speed Coffee? | Yes — a review says "Plenty of outlets" and "fast internet," calling it a perfect laptop spot. (Outlets are not in Yelp's amenity list — this fact lives only in a review.) |
| 4   | Is Bolivar Coffee open on Sundays?                     | No — closed Sunday (Mon–Fri 7:30 AM–7:00 PM, Sat 8:00 AM–7:00 PM).                                                                                                          |
| 5   | Which cafe is open the latest?                         | Organico — open until 12:00 AM (midnight) every day.                                                                                                                        |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. **Key facts split between the amenity list and the reviews.** Some conditions I care about (e.g. _outlets_, _how crowded it gets_, _study vibe_) are not in Yelp's structured amenity list — they only appear in free-text reviews. If I relied on amenity flags alone I'd answer "unknown" for outlets even though reviews mention them. Mitigation: keep reviews as their own chunks so review-only facts stay retrievable.

2. **"List all cafes with X" is hard for pure semantic top-k.** A query like "which cafes have free parking" can return several chunks from the _same_ cafe and miss others, because similarity doesn't guarantee coverage across cafes. Mitigation: store amenities as boolean metadata and use an exact ChromaDB `where` filter for attribute questions, rather than relying on embedding similarity alone.

3. **Truncation / dilution from chunk sizing.** `all-MiniLM-L6-v2` silently truncates past 256 tokens, and averaging many topics into one vector weakens specific signals. This is _why_ I chose one-review-per-chunk; the risk is real if chunking is changed later.

4. **Stale or ambiguous source data.** Yelp pages carry only a month-level "Updated" stamp, and the same cafe name can exist at multiple locations. Mitigation: location-aware chunk IDs (name + street) and a freshness manifest that flags pages older than ~1 month.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

1. Ingestion
   - Input: `documents/raw/*.html`
   - Cleaning: `clean_documents.py`
   - Output: `cafes.json`

2. Chunking
   - Input: `cafes.json`
   - Chunking: `chunk_documents.py`
   - Output: `chunks.jsonl`
     - fact card + 1/review + metadatda flags

3. Embedding + Vector Store
   - all-MiniLM-L6-v2
   - ChromaDB

4. Retrieval
   - ChromaDB query
   - Top-K 5-8 + metadata
   - `where` filter on flags

5. Generation + Interface
   - Groq LLM, grounded on retrieved chunks
   - Cites cafe name + source
   - Refuses if no match
   - UI: Gradio / Streamlit

---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

I gave Claude the Chunking Strategy section plus a sample raw Yelp HTML file and asked it to inspect the real structure before writing code. It found the JSON-LD block, the `displayText`/`alias` amenity pairs, and the `<p class="comment...">` reviews, then produced `clean_documents.py` (extract → `cafes.json` + clean `.txt`) and `chunk_documents.py` (→ `chunks.jsonl`). I verified by spot-checking output across all 10 files and overrode the design to use one-review-per-chunk JSONL (with metadata flags) instead of plain newline-split text, after we established the 256-token truncation limit.

**Milestone 4 — Embedding and retrieval:**

I'll give Claude this Retrieval Approach section + `chunks.jsonl` and ask it to (1) embed each chunk's `text` with `all-MiniLM-L6-v2`, (2) load them into ChromaDB with the flat metadata as the `where`-filterable fields, and (3) write a `retrieve(query, k=5)` that supports an optional metadata filter. I'll verify against my 5 eval questions — especially that #2/#5 (list/aggregation) return multiple distinct cafes.

**Milestone 5 — Generation and interface:**

I'll give Claude the retrieved-chunk format and ask it to build a Groq generation step with a grounding system prompt (answer only from retrieved context, cite the cafe name, say "I don't have that info" when nothing relevant is retrieved), plus a Gradio/Streamlit UI. I'll verify by running the eval questions end-to-end and checking the failure case in the README.
