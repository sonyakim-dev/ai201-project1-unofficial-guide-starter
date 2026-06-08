# The Unofficial Guide — Project 1

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

**Finding the Best West LA cafe for study !**

I have been going to all the different cafes in West LA and all cafes have different condition. Once I prompt a cafe name, I want to know if the cafe has wifi/outlets/free parking/restroom/seating/etc. Or I want to get a list of cafes if I am looking for a cafe that has a specific condition.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| #   | Source | Type                 | URL or file path                                                                                  |
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

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** Structure-aware (one semantic unit per chunk, not a fixed token window)

- **Fact card** — one per cafe: name + address + rating + hours + full amenities list + website
- **Review** — one per review, each prefixed with the cafe name

Every chunk also carries flat metadata (`cafe_id`, `rating`, `hours_summary`, and boolean amenity flags like `has_wifi`, `good_for_working`) so retrieval can filter exactly, not just by similarity.

**Overlap:** None. Here each chunk is already a discrete, self-contained record, so there is nothing to bleed across a boundary.

**Why these choices fit your documents:**
The raw HTML files are ~2 MB each and full of noise (header, footer, CSS, images, buttons, ads, "people also viewed"). Rather than strip tags off the whole page, I extract only the three things that matter and discard everything else by construction:

- **Business metadata** — from `<script>` block: name, address, rating, phone (hours and website are scraped from the page body).
- **Amenities** — structured flags (Free Wi-Fi, Outdoor seating, Valet/Garage/Street parking, ADA-compliant restroom, "Good for working"…), embedded as `"displayText":"Free Wi-Fi","alias":"wifi_..."`.
- **Reviews** — from `<p class="comment...">`, ~10–21 per page, 4–5 sentences each.

I chunk one review per chunk for two reasons: (1) `all-MiniLM-L6-v2` truncates at 256 tokens, so a merged 20-review block would be silently cut off; (2) one focused vector per review keeps specific signals (e.g. a single mention of "outlets") from being averaged away.

**Final chunk count:** 134

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** `all-MiniLM-L6-v2`

**Production tradeoff reflection:**
If cost weren't a constraint I'd weigh:

- **Context length** — MiniLM's 256-token cap forces review-level chunking. A longer-context model would let me embed whole-cafe chunks without truncation, simplifying retrieval at some cost to precision.
- **Domain accuracy** — a larger model captures nuanced review language (sarcasm, "great except…") more faithfully, improving ranking on subjective queries.
- **Multilingual** — some reviews contain non-English phrases; a multilingual model would handle those instead of treating them as near-noise.
- **Latency & privacy** — local MiniLM is instant and keeps review text on-device; a hosted API adds network latency, rate limits, and sends data to a third party. For a small personal tool, local wins; at scale the accuracy gains might justify the API.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

You are CafesBot, a cafe recommendation assistant.
Answer the user's question using ONLY the rule excerpts provided in the context.
Do not use any outside knowledge, even if you think you know the cafe.
Each excerpt is labeled with its cafe name in square brackets — name the relevant cafe in your answer.
If the context does not contain the answer, say so plainly (e.g. "That isn't covered in the loaded cafes.") rather than guessing.
A confident wrong answer is worse than an honest 'I don't know.'
Do not include any other cafes that are irrelevant to the question, even if they are in the context.
If you need to list multiple cafes, use bullet points for better readability and list them in the order the most relevant cafe appears in the context to the least relevant.
If the information is conflicting between the amenities and reviews, prioritize the amenities information, but mention the review information.
If there are multiple same named cafes, tell them apart by their location in paranthesis and notify the user that there are multiple cafes with the same name.
Note that times marked "(Next day)" are after midnight and are later than same-day PM closing times.
At the end, append the last update date of the information in the context, in the format "\n(Last updated: [Month] [Year])".

**How source attribution is surfaced in the response:**

It prevents the LLM from answering beyond the retrieved documents.
If it outputs multiple cafes, it will list them in the order the most relevant to least relevant.
Also, it instructs the format of output and it prints the last updated date to inform the latestness of the information.

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| #   | Question                                               | Expected answer                                                      | System response (summarized) | Retrieval quality | Response accuracy |
| --- | ------------------------------------------------------ | -------------------------------------------------------------------- | ---------------------------- | ----------------- | ----------------- |
| 1   | Does Dialog Cafe have Wi-Fi, and what are its hours?   | Free Wi-Fi, Mon–Fri 7AM–8PM, Sat–Sun 7AM–5PM                         | As expected                  | Relevant          | Accurate          |
| 2   | Which cafes are good for working on a laptop?          | 10 Speed, Board House, Bolivar, Bonsai, Espressoteric, Motoring, etc | 10 Speed, Motoring, Bolivar  | Relevant          | Accurate          |
| 3   | Do reviewers mention power outlets at 10 Speed Coffee? | Yes                                                                  | Yes                          | Relevant          | Accurate          |
| 4   | Is Bolivar Coffee open on Sundays?                     | No                                                                   | No                           | Relevant          | Accurate          |
| 5   | Which cafe is open the latest?                         | Organico                                                             | Dialog Cafe                  | Relevant          | Inaccurate        |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:** Which cafe is open the latest?

**What the system returned:** Dialog Cafe

**Root cause (tied to a specific pipeline stage):** Organico opens until 12AM (Next day), but I belive the model cannot interpret the '(Next day)' properly.

**What you would change to fix it:**
I tried putting 'Note that times marked "(Next day)" are after midnight and are later than same-day PM closing times.' in system prompt, however, it did not work. I would calculate and generate a `lastest closing time` flag when cleaning/ingesting.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

**One way your implementation diverged from the spec, and why:**

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- _What I gave the AI:_ I asked AI to automatically rerun cleaning and chunking when the files are updated.
- _What it produced:_ `.raw_manifest.json` and `.app_rebuild_manifest.json` to snapshot the files' timestamp and automatically recall ingestion chunking function.
- _What I changed or overrode:_ None

**Instance 2**

- _What I gave the AI:_ I asked AI to look into raw HTML files and extract the necesary information that I need to process.
- _What it produced:_ It produced `txt` file to review the cleaned version of HTML and JSON formatted chunks.
- _What I changed or overrode:_ I updated to add additional information which are last updated date, website, etc.
