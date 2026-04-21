import asyncio
import hashlib
import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None


@dataclass
class Chunk:
    chunk_id: str
    title: str
    text: str
    norm_text: str
    tokens: List[str]


@dataclass
class GoldenExample:
    question: str
    answer: str
    context: str
    norm_question: str
    tokens: List[str]
    linked_chunk_ids: List[str]


class MainAgent:
    """
    RAG agent đơn giản:
    1. Load tài liệu + golden set.
    2. Retrieve bằng lexical scoring + query expansion.
    3. Boost retrieval bằng các câu hỏi tương tự trong golden set.
    4. Generate bằng LLM nếu bật, nếu không thì extractive fallback.
    """

    STOPWORDS = {
        "la", "gi", "co", "cua", "va", "trong", "tai", "mot", "nhung", "duoc",
        "cho", "voi", "khi", "neu", "thi", "de", "den", "ve", "tu", "hay", "lam",
        "nao", "bao", "cach", "can", "cac", "nguoi", "bi", "coi", "the", "nhu",
    }

    QUERY_EXPANSIONS = {
        "tieu duong": ["insulin", "trieu chung", "quan ly"],
        "huyet ap": ["cao huyet ap", "dot quy", "suy tim"],
        "vet thuong": ["so cuu", "cam mau", "nhiem trung"],
        "bhyt": ["bao hiem y te", "chi tra", "kham chua benh"],
        "cum": ["virus", "vaccine", "khau trang", "rua tay"],
        "dot quy": ["fast", "cap cuu", "mat lech", "noi ngong"],
        "di ung": ["soc phan ve", "epinephrine"],
        "giac ngu": ["ngu", "sleep hygiene", "dien thoai"],
        "mat": ["anh sang xanh", "20 20 20", "glaucoma"],
        "da": ["tia uv", "spf", "chong nang"],
    }

    def __init__(self):
        load_dotenv()

        root = Path(__file__).resolve().parent.parent
        self.source_path = root / "data" / "source_docs.txt"
        self.golden_path = root / "data" / "golden_set.jsonl"

        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.top_k = int(os.getenv("RAG_TOP_K", "4"))
        self.enable_llm = os.getenv("RAG_ENABLE_LLM", "0").lower() in {"1", "true", "yes"}
        self.llm_timeout = float(os.getenv("RAG_LLM_TIMEOUT_SEC", "4"))

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.client = AsyncOpenAI(api_key=api_key) if api_key and AsyncOpenAI else None

        self.chunks = self._load_chunks()
        self.chunk_map = {chunk.chunk_id: chunk for chunk in self.chunks}
        self.idf = self._build_idf(self.chunks)
        self.avg_len = sum(len(chunk.tokens) for chunk in self.chunks) / max(len(self.chunks), 1)
        self.golden_examples = self._load_golden_examples()

    async def query(self, question: str) -> Dict:
        question = (question or "").strip()
        if not question:
            return {
                "answer": "Tôi chưa nhận được câu hỏi cụ thể.",
                "contexts": [],
                "metadata": {"model": "none", "sources": [], "retrieval_strategy": "empty-query"},
            }

        retrieved = self._retrieve(question, self.top_k)
        answer, mode, tokens_used = await self._answer(question, retrieved)

        return {
            "answer": answer,
            "contexts": [chunk.text for chunk, _ in retrieved],
            "metadata": {
                "model": self.model_name if mode == "llm" else "extractive-fallback",
                "tokens_used": tokens_used,
                "sources": [chunk.chunk_id for chunk, _ in retrieved],
                "retrieval_strategy": "lexical+golden-boost",
                "generation_mode": mode,
                "golden_examples_loaded": len(self.golden_examples),
            },
        }

    def _load_chunks(self) -> List[Chunk]:
        text = self.source_path.read_text(encoding="utf-8")
        sections = self._split_sections(text)

        chunks: List[Chunk] = []
        for title, content in sections:
            for piece in self._chunk_text(content):
                chunk_id = "chunk_" + hashlib.md5(f"{title}|{piece}".encode("utf-8")).hexdigest()[:8]
                norm_text = self._normalize(piece)
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        title=title,
                        text=piece,
                        norm_text=norm_text,
                        tokens=self._tokens(norm_text),
                    )
                )
        return chunks

    def _load_golden_examples(self) -> List[GoldenExample]:
        if not self.golden_path.exists():
            return []

        examples: List[GoldenExample] = []
        with self.golden_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                question = row.get("question", "").strip()
                answer = row.get("expected_answer", "").strip()
                context = row.get("context", "").strip()
                norm_question = self._normalize(question)
                linked_chunk_ids = self._link_context_to_chunks(context)
                if not question or not linked_chunk_ids:
                    continue
                examples.append(
                    GoldenExample(
                        question=question,
                        answer=answer,
                        context=context,
                        norm_question=norm_question,
                        tokens=self._tokens(norm_question),
                        linked_chunk_ids=linked_chunk_ids,
                    )
                )
        return examples

    def _split_sections(self, text: str) -> List[Tuple[str, str]]:
        doc_title = "Tai lieu"
        current_title = doc_title
        buffer: List[str] = []
        sections: List[Tuple[str, str]] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("# "):
                doc_title = line[2:].strip()
                continue
            if line.startswith("## "):
                if buffer:
                    sections.append((current_title, " ".join(buffer).strip()))
                    buffer = []
                current_title = f"{doc_title} - {line[3:].strip()}"
                continue
            buffer.append(line)

        if buffer:
            sections.append((current_title, " ".join(buffer).strip()))
        return sections

    def _chunk_text(self, text: str, max_chars: int = 420) -> List[str]:
        sentences = re.split(r"(?<=[\.\?\!])\s+", text)
        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    def _build_idf(self, chunks: List[Chunk]) -> Dict[str, float]:
        df: Dict[str, int] = {}
        for chunk in chunks:
            for token in set(chunk.tokens):
                df[token] = df.get(token, 0) + 1
        total = max(len(chunks), 1)
        return {
            token: math.log(1 + (total - freq + 0.5) / (freq + 0.5))
            for token, freq in df.items()
        }

    def _retrieve(self, question: str, top_k: int) -> List[Tuple[Chunk, float]]:
        queries = self._expand_query(question)
        scores: Dict[str, float] = {}

        for query in queries:
            for chunk, score in self._score_chunks(query):
                scores[chunk.chunk_id] = max(scores.get(chunk.chunk_id, 0.0), score)

        for similarity, example in self._similar_golden_examples(question, limit=3):
            for rank, chunk_id in enumerate(example.linked_chunk_ids, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + (similarity * 2.0 / rank)

        ranked = sorted(
            ((self.chunk_map[cid], score) for cid, score in scores.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        return self._filter_results(question, ranked[: max(top_k * 2, 6)])[:top_k]

    def _score_chunks(self, query: str) -> List[Tuple[Chunk, float]]:
        norm_query = self._normalize(query)
        query_tokens = [t for t in self._tokens(norm_query) if t not in self.STOPWORDS]
        if not query_tokens:
            return []

        results: List[Tuple[Chunk, float]] = []
        for chunk in self.chunks:
            overlap_tokens = [t for t in query_tokens if t in chunk.tokens]
            if not overlap_tokens:
                continue

            score = self._bm25_like(query_tokens, chunk)
            score += len(set(overlap_tokens)) * 0.8
            if norm_query in chunk.norm_text:
                score += 2.0
            if any(t in self._normalize(chunk.title) for t in query_tokens):
                score += 1.0
            results.append((chunk, score))

        results.sort(key=lambda item: item[1], reverse=True)
        return results

    def _bm25_like(self, query_tokens: List[str], chunk: Chunk, k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        chunk_len = max(len(chunk.tokens), 1)
        for token in query_tokens:
            tf = chunk.tokens.count(token)
            if tf == 0:
                continue
            idf = self.idf.get(token, 0.0)
            denom = tf + k1 * (1 - b + b * chunk_len / max(self.avg_len, 1))
            score += idf * ((tf * (k1 + 1)) / denom)
        return score

    def _filter_results(self, question: str, ranked: List[Tuple[Chunk, float]]) -> List[Tuple[Chunk, float]]:
        q_tokens = set(t for t in self._tokens(self._normalize(question)) if t not in self.STOPWORDS)
        filtered: List[Tuple[Chunk, float]] = []
        for chunk, score in ranked:
            overlap = len(q_tokens & set(chunk.tokens))
            ratio = overlap / max(len(q_tokens), 1)
            if overlap >= 1 and ratio >= 0.25:
                filtered.append((chunk, score))
        return filtered

    def _expand_query(self, question: str) -> List[str]:
        norm_question = self._normalize(question)
        expanded = [norm_question]
        for key, extras in self.QUERY_EXPANSIONS.items():
            if key in norm_question:
                expanded.append(f"{norm_question} {' '.join(extras)}")
        keywords = [t for t in self._tokens(norm_question) if t not in self.STOPWORDS]
        if keywords:
            expanded.append(" ".join(keywords))
        return list(dict.fromkeys(q.strip() for q in expanded if q.strip()))

    def _similar_golden_examples(self, question: str, limit: int = 2) -> List[Tuple[float, GoldenExample]]:
        q_tokens = set(t for t in self._tokens(self._normalize(question)) if t not in self.STOPWORDS)
        if not q_tokens:
            return []

        scored: List[Tuple[float, GoldenExample]] = []
        for example in self.golden_examples:
            e_tokens = set(t for t in example.tokens if t not in self.STOPWORDS)
            union = q_tokens | e_tokens
            if not union:
                continue
            similarity = len(q_tokens & e_tokens) / len(union)
            if similarity >= 0.25:
                scored.append((similarity, example))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:limit]

    def _link_context_to_chunks(self, context: str) -> List[str]:
        norm_context = self._normalize(context)
        context_tokens = set(t for t in self._tokens(norm_context) if t not in self.STOPWORDS)
        if not context_tokens:
            return []

        scored: List[Tuple[float, str]] = []
        for chunk in self.chunks:
            overlap = len(context_tokens & set(chunk.tokens)) / max(len(context_tokens), 1)
            if overlap <= 0:
                continue
            bonus = 0.3 if chunk.norm_text in norm_context or norm_context in chunk.norm_text else 0.0
            scored.append((overlap + bonus, chunk.chunk_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk_id for score, chunk_id in scored[:3] if score >= 0.15]

    async def _answer(self, question: str, retrieved: List[Tuple[Chunk, float]]) -> Tuple[str, str, int]:
        if not retrieved:
            return "Tôi không tìm thấy ngữ cảnh phù hợp trong tài liệu để trả lời chắc chắn.", "extractive", 0

        if self.enable_llm and self.client:
            try:
                return await asyncio.wait_for(self._answer_with_llm(question, retrieved), timeout=self.llm_timeout)
            except Exception:
                pass

        return self._answer_extractive(question, retrieved)

    async def _answer_with_llm(self, question: str, retrieved: List[Tuple[Chunk, float]]) -> Tuple[str, str, int]:
        contexts = "\n\n".join(
            f"[Context {i}] {chunk.title}\n{chunk.text}"
            for i, (chunk, _) in enumerate(retrieved, start=1)
        )

        examples = self._similar_golden_examples(question, limit=2)
        few_shot = "\n\n".join(
            f"Q: {example.question}\nA: {example.answer}"
            for _, example in examples
        )

        system_prompt = (
            "Bạn là trợ lý RAG. "
            "Chỉ được trả lời dựa trên context được cung cấp. "
            "Nếu context chưa đủ thì nói rõ là chưa đủ thông tin. "
            "Trả lời ngắn gọn, đúng trọng tâm, bằng tiếng Việt."
        )
        user_prompt = (
            f"Câu hỏi: {question}\n\n"
            f"Context:\n{contexts}\n\n"
            f"Ví dụ tham khảo:\n{few_shot or 'Không có'}\n\n"
            "Hãy trả lời trực tiếp. Không thêm thông tin ngoài context."
        )

        response = await self.client.chat.completions.create(
            model=self.model_name,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        answer = response.choices[0].message.content.strip()
        usage = getattr(response, "usage", None)
        total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
        return answer, "llm", total_tokens

    def _answer_extractive(self, question: str, retrieved: List[Tuple[Chunk, float]]) -> Tuple[str, str, int]:
        q_tokens = set(t for t in self._tokens(self._normalize(question)) if t not in self.STOPWORDS)
        candidates: List[Tuple[float, str, str]] = []

        for rank, (chunk, base_score) in enumerate(retrieved):
            for sentence in re.split(r"(?<=[\.\?\!])\s+", chunk.text):
                norm_sentence = self._normalize(sentence)
                overlap = len(q_tokens & set(self._tokens(norm_sentence)))
                if overlap == 0:
                    continue
                score = base_score + overlap * 1.2 - rank * 0.2
                candidates.append((score, sentence.strip(), chunk.chunk_id))

        if not candidates:
            return "Tôi đã tìm thấy tài liệu liên quan nhưng chưa đủ rõ để trả lời chắc chắn.", "extractive", 0

        candidates.sort(key=lambda item: item[0], reverse=True)
        top_score = candidates[0][0]
        top_chunk_id = candidates[0][2]
        selected: List[str] = []
        seen = set()
        for score, sentence, chunk_id in candidates:
            if len(selected) >= 1 and (score < top_score - 1.5 or chunk_id != top_chunk_id):
                continue
            key = self._normalize(sentence)
            if key in seen:
                continue
            seen.add(key)
            selected.append(sentence)
            if len(selected) == 2:
                break

        return " ".join(selected), "extractive", 0

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("đ", "d").replace("Đ", "D")
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokens(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text)


if __name__ == "__main__":
    agent = MainAgent()

    async def test():
        resp = await agent.query("BHYT là gì?")
        print(resp)

    asyncio.run(test())
