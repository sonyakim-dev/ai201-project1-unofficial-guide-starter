from config import GROQ_API_KEY, LLM_MODEL
from groq import Groq

_client = Groq(api_key=GROQ_API_KEY)


def generate_response(query, retrieved_chunks):
    """
    Generate a grounded answer from retrieved rule chunks.

    `retrieved_chunks` is the list returned by retrieve(). Each item is a dict:
      - "text"     : the chunk text
      - "metadata" : flat metadata, incl. "cafe" (name) and "type" (fact_card/review)
      - "distance" : similarity score (you can use this to filter weak matches)

    Return the response as a plain string.
    """
    if not retrieved_chunks:
        return (
            "I couldn't find anything relevant in the loaded cafes list. "
            "Try rephrasing your question — or check that your ingestion pipeline is working."
        )

    context = "\n\n".join(
        f"[{chunk['metadata'].get('cafe', '?')}]\n{chunk['text']}"
        for chunk in retrieved_chunks
    )

    system_prompt = (
        """
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
        At the end, append the the short description of the cafe, in the format
        "---------------------------
        [CAFE NAME] / Rating: [RATING]
        [ADDRESS]
        [PHONE NUMBER if exists or omit]
        [WEBSITE if exists or omit]
        \n(Last updated: [Month] [Year])".
        """
    )

    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content
