import re


def chunk_text(text: str, max_chars: int) -> list[dict]:
    """Split text into chunks at sentence boundaries.

    Returns list of {"text": str, "offset": int} dicts.
    The offset is the starting character position of this chunk
    in the original text. Used to adjust PII span offsets.

    Rules:
    - Each chunk is <= max_chars.
    - Splits at sentence boundaries (period/question/exclamation + space).
    - If a single sentence exceeds max_chars, split at the last space
      before max_chars.
    - Never splits mid-word.
    """
    if len(text) <= max_chars:
        return [{"text": text, "offset": 0}]

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = ""
    current_offset = 0
    pos = 0

    for sentence in sentences:
        # Handle sentences longer than max_chars
        if len(sentence) > max_chars:
            # Flush current chunk if non-empty
            if current_chunk:
                chunks.append({"text": current_chunk, "offset": current_offset})
                pos += len(current_chunk)
                # Account for the space/separator between chunks
                current_chunk = ""
                current_offset = pos

            # Split long sentence at spaces
            words = sentence.split(" ")
            sub_chunk = ""
            sub_offset = pos
            for word in words:
                test = (sub_chunk + " " + word).strip()
                if len(test) > max_chars:
                    if sub_chunk:
                        chunks.append({"text": sub_chunk, "offset": sub_offset})
                        pos = sub_offset + len(sub_chunk) + 1
                        sub_offset = pos
                    sub_chunk = word
                else:
                    sub_chunk = test
            if sub_chunk:
                current_chunk = sub_chunk
                current_offset = sub_offset
            continue

        test = (current_chunk + " " + sentence).strip() if current_chunk else sentence
        if len(test) > max_chars:
            chunks.append({"text": current_chunk, "offset": current_offset})
            pos = current_offset + len(current_chunk)
            # Find actual position of next sentence in original text
            separator_len = len(text[pos:]) - len(text[pos:].lstrip())
            pos += separator_len
            current_chunk = sentence
            current_offset = pos
        else:
            if not current_chunk:
                current_offset = pos
            current_chunk = test

    if current_chunk:
        chunks.append({"text": current_chunk, "offset": current_offset})

    return chunks
