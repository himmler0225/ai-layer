import hashlib
from app.ingest.processing.quality import is_indexable_comment
from app.ingest.schemas import ChunkItem

_WORDS_PER_CHUNK = 400
_OVERLAP_WORDS = 50


def make_chunk_id(video_id: str, chunk_type: str, content: str) -> str:
    """Derive a stable, content-addressed id for a chunk.

    Args:
        video_id: Id of the video the chunk was derived from.
        chunk_type: Kind of chunk, e.g. "transcript" or "comment".
        content: Chunk text content, hashed to make the id deterministic.

    Returns:
        A "{video_id}:{hash}" id string.
    """
    digest = hashlib.sha256(f"{video_id}:{chunk_type}:{content}".encode()).hexdigest()[:20]
    return f"{video_id}:{digest}"


def chunk_transcript(video_id: str, text: str, *, language: str = "") -> list[ChunkItem]:
    """Split a transcript into overlapping word-based chunks for embedding.

    Slides a window of `_WORDS_PER_CHUNK` words over the transcript, stepping by
    `_WORDS_PER_CHUNK - _OVERLAP_WORDS` words each iteration, and skips any chunk
    shorter than 20 characters.

    Args:
        video_id: Id of the video the transcript belongs to.
        text: Full transcript text.
        language: Optional transcript language code, stored in each chunk's metadata.

    Returns:
        A list of ChunkItem with chunk_type="transcript"; [] if `text` is empty.
    """
    words = (text or "").split()
    if not words:
        return []
    chunks: list[ChunkItem] = []
    step = max(_WORDS_PER_CHUNK - _OVERLAP_WORDS, 1)
    for start in range(0, len(words), step):
        piece = " ".join(words[start : start + _WORDS_PER_CHUNK]).strip()
        if len(piece) < 20:
            continue
        chunks.append(
            ChunkItem(
                id=make_chunk_id(video_id, "transcript", piece),
                content=piece,
                chunk_type="transcript",
                metadata={"language": language, "word_offset": start},
            )
        )
        if start + _WORDS_PER_CHUNK >= len(words):
            break
    return chunks


def comment_chunks(video_id: str, comments: list[dict]) -> list[ChunkItem]:
    """Build one embeddable chunk per indexable comment.

    Filters out comments that fail `is_indexable_comment` (too short, spammy, or
    with too few alphanumeric characters), then wraps each remaining comment's
    content as a ChunkItem.

    Args:
        video_id: Id of the video the comments belong to.
        comments: Normalized comment dicts (as produced by `map_comment`).

    Returns:
        A list of ChunkItem with chunk_type="comment", carrying comment_id, author,
        and likes in metadata.
    """
    items: list[ChunkItem] = []
    for comment in comments:
        content = (comment.get("content") or "").strip()
        if not is_indexable_comment(content):
            continue
        items.append(
            ChunkItem(
                id=make_chunk_id(video_id, "comment", content),
                content=content,
                chunk_type="comment",
                metadata={
                    "comment_id": comment.get("id"),
                    "author": comment.get("author", ""),
                    "likes": comment.get("likes", 0),
                },
            )
        )
    return items
