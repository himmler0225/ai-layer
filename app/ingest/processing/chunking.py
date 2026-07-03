import hashlib
from app.ingest.processing.quality import is_indexable_comment
from app.ingest.schemas import ChunkItem

_WORDS_PER_CHUNK = 400
_OVERLAP_WORDS = 50


def make_chunk_id(video_id: str, chunk_type: str, content: str) -> str:
    """Make chunk id.

    Args:
        video_id: (str) Tham số `video_id`.
        chunk_type: (str) Tham số `chunk_type`.
        content: (str) Tham số `content`.

    Returns:
        (str) Kết quả trả về."""
    digest = hashlib.sha256(f"{video_id}:{chunk_type}:{content}".encode()).hexdigest()[:20]
    return f"{video_id}:{digest}"


def chunk_transcript(video_id: str, text: str, *, language: str = "") -> list[ChunkItem]:
    """Chunk transcript.

    Args:
        video_id: (str) Tham số `video_id`.
        text: (str) Tham số `text`.
        language: (str, mặc định '') Tham số `language`.

    Returns:
        (list[ChunkItem]) Kết quả trả về."""
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
    """Comment chunks.

    Args:
        video_id: (str) Tham số `video_id`.
        comments: (list[dict]) Tham số `comments`.

    Returns:
        (list[ChunkItem]) Kết quả trả về."""
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
