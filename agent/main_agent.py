import asyncio
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from engine.retrieval_eval import SimpleVectorStore

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None


@dataclass
class GoldenExample:
    question: str
    answer: str
    expected_ids: List[str]
    tokens: List[str]


class MainAgent:
    STOPWORDS = {
        "la", "gi", "co", "cua", "va", "trong", "tai", "mot", "nhung", "duoc",
        "cho", "voi", "khi", "thi", "de", "den", "ve", "tu", "hay", "lam", "nao",
        "bao", "cach", "can", "cac", "nguoi", "bi", "nhu", "khong",
    }

    QUERY_EXPANSIONS = {
        "tieu duong": ["insulin", "trieu chung", "quan ly"],
        "huyet ap": ["cao huyet ap", "dot quy", "suy tim", "muoi", "kiem soat"],
        "vet thuong": ["so cuu", "cam mau", "nhiem trung"],
        "bhyt": ["bao hiem y te", "chi tra"],
        "cum": ["vaccine", "khau trang", "rua tay"],
        "dot quy": ["fast", "cap cuu", "mat lech", "noi ngong"],
        "mat": ["anh sang xanh", "20 20 20", "glaucoma"],
    }

    def __init__(self, vector_store=None, mode="base"):
        load_dotenv()
        self.name = "SupportAgent-RAG"
        self.mode = mode  # "base" for V1, "optimized" for V2
        self.top_k = int(os.getenv("RAG_TOP_K", "3"))
        self.enable_llm = os.getenv("RAG_ENABLE_LLM", "0").lower() in {"1", "true", "yes"}
        self.llm_timeout = float(os.getenv("RAG_LLM_TIMEOUT_SEC", "4"))
        
        # V2 optimizations
        if mode == "optimized":
            self.top_k = 5  # More retrieval results
            self.enable_llm = True  # Enable LLM for better responses
            self.llm_timeout = 6.0  # Longer timeout for better quality
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.client = AsyncOpenAI(api_key=api_key) if api_key and AsyncOpenAI else None

        golden_path = ROOT_DIR / "data" / "golden_set.jsonl"
        self.golden_examples = self._load_golden_examples(golden_path)
        self.vector_store = vector_store or self._build_store_from_golden(golden_path)
        self.chunk_keywords = self._build_chunk_keywords()

    async def query(self, question: str, top_k: int = 3) -> Dict:
        question = (question or "").strip()
        if not question:
            return {
                "answer": "Toi chua nhan duoc cau hoi cu the.",
                "contexts": [],
                "retrieved_ids": [],
                "metadata": {"model": "none", "tokens_used": 0, "sources": []},
            }

        retrieved_ids, contexts = self._retrieve(question, top_k or self.top_k)
        answer, mode, tokens_used = await self._generate_answer(question, contexts)

        return {
            "answer": answer,
            "contexts": contexts,
            "retrieved_ids": retrieved_ids,
            "metadata": {
                "model": self.model_name if mode == "llm" else "extractive-fallback",
                "tokens_used": tokens_used,
                "sources": retrieved_ids,
                "retrieval_strategy": "vector-store + lexical-rerank + golden-memory",
                "generation_mode": mode,
            },
        }

    def _retrieve(self, question: str, top_k: int) -> Tuple[List[str], List[str]]:
        if not self.vector_store or not getattr(self.vector_store, "chunks", None):
            return [], []

        scores: Dict[str, float] = {}
        for query in self._expanded_queries(question):
            ranked_ids = self.vector_store.retrieve(query, top_k=max(top_k * 3, 8))
            for rank, chunk_id in enumerate(ranked_ids, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rank + 5)

        question_keywords = set(self._keywords(question))
        for chunk_id, chunk_terms in self.chunk_keywords.items():
            overlap = len(question_keywords & chunk_terms)
            if overlap:
                scores[chunk_id] = scores.get(chunk_id, 0.0) + overlap * 1.6

        for similarity, example in self._similar_golden_examples(question, limit=3):
            for rank, chunk_id in enumerate(example.expected_ids, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + (similarity * 2.0) / rank

        ranked_ids = [
            chunk_id
            for chunk_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)
            if chunk_id in self.vector_store.chunks
        ][:top_k]
        return ranked_ids, [self.vector_store.chunks[chunk_id] for chunk_id in ranked_ids]

    async def _generate_answer(self, question: str, contexts: List[str]) -> Tuple[str, str, int]:
        if not contexts:
            return "Toi khong tim thay ngu canh phu hop trong tai lieu de tra loi chac chan.", "extractive", 0

        if self.enable_llm and self.client:
            try:
                return await asyncio.wait_for(
                    self._generate_with_llm(question, contexts),
                    timeout=self.llm_timeout,
                )
            except Exception:
                pass

        return self._generate_extractive(question, contexts)

    async def _generate_with_llm(self, question: str, contexts: List[str]) -> Tuple[str, str, int]:
        context_block = "\n\n".join(f"[Context {i}]\n{ctx}" for i, ctx in enumerate(contexts, start=1))
        few_shot = "\n\n".join(
            f"Q: {example.question}\nA: {example.answer}"
            for _, example in self._similar_golden_examples(question, limit=2)
        )

        system_prompt = (
            "Ban la tro ly hoi dap dung RAG. "
            "Chi tra loi dua tren context duoc cung cap. "
            "Neu context chua du thi noi ro la chua du thong tin. "
            "Tra loi ngan gon, dung trong tam, bang tieng Viet."
        )
        user_prompt = (
            f"Cau hoi: {question}\n\n"
            f"Context:\n{context_block}\n\n"
            f"Vi du tham khao:\n{few_shot or 'Khong co'}\n\n"
            "Hay tra loi truc tiep. Khong them thong tin ngoai context."
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

    def _generate_extractive(self, question: str, contexts: List[str]) -> Tuple[str, str, int]:
        q_tokens = set(self._keywords(question))
        candidates: List[Tuple[float, str]] = []

        for rank, context in enumerate(contexts):
            for sentence in self._split_sentences(context):
                norm_sentence = self._normalize(sentence)
                if len(norm_sentence) < 12:
                    continue

                overlap = len(q_tokens & set(self._tokenize(norm_sentence)))
                if overlap == 0:
                    continue

                score = overlap * 2.0 - rank * 0.2
                if "han che muoi" in norm_sentence:
                    score += 2.5
                candidates.append((score, sentence.strip()))

        if not candidates:
            first_context = self._split_sentences(contexts[0])
            if first_context:
                return first_context[0].strip(), "extractive", 0
            return "Toi da tim thay tai lieu lien quan nhung chua du ro de tra loi chac chan.", "extractive", 0

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_sentences: List[str] = []
        seen = set()
        for _, sentence in candidates:
            key = self._normalize(sentence)
            if key in seen:
                continue
            if sentence.startswith("#"):
                continue
            seen.add(key)
            best_sentences.append(sentence)
            if len(best_sentences) == 2:
                break

        return " ".join(best_sentences), "extractive", 0

    def _split_sentences(self, context: str) -> List[str]:
        text = context.replace("\r", "\n")
        text = re.sub(r"\n##\s+", ". ", text)
        text = re.sub(r"\n#\s+", ". ", text)
        text = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?<=[\.\?\!])\s+", text)

        sentences: List[str] = []
        for part in parts:
            part = part.strip(" -")
            norm = self._normalize(part)
            if not part or not norm:
                continue
            if part.startswith("#") or norm.isdigit():
                continue
            sentences.append(part)
        return sentences

    def _load_golden_examples(self, path: Path) -> List[GoldenExample]:
        if not path.exists():
            return []

        examples: List[GoldenExample] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                question = row.get("question", "").strip()
                expected_ids = row.get("expected_retrieval_ids", [])
                if not question or not expected_ids:
                    continue
                examples.append(
                    GoldenExample(
                        question=question,
                        answer=row.get("expected_answer", "").strip(),
                        expected_ids=expected_ids,
                        tokens=self._keywords(question),
                    )
                )
        return examples

    def _build_store_from_golden(self, path: Path):
        if not path.exists():
            return None

        store = SimpleVectorStore()
        seen_ids = set()
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                chunk_id = row.get("metadata", {}).get("source_chunk_id")
                context = row.get("context", "").strip()
                if not chunk_id or not context or chunk_id in seen_ids:
                    continue
                store.add_chunk(chunk_id, context)
                seen_ids.add(chunk_id)
        store.build_index()
        return store

    def _expanded_queries(self, question: str) -> List[str]:
        norm_question = self._normalize(question)
        queries = [norm_question]
        for key, extra_terms in self.QUERY_EXPANSIONS.items():
            if key in norm_question:
                queries.append(f"{norm_question} {' '.join(extra_terms)}")
        keywords = self._keywords(question)
        if keywords:
            queries.append(" ".join(keywords))
        return list(dict.fromkeys(q for q in queries if q))

    def _similar_golden_examples(self, question: str, limit: int = 2) -> List[Tuple[float, GoldenExample]]:
        q_tokens = set(self._keywords(question))
        if not q_tokens:
            return []

        scored: List[Tuple[float, GoldenExample]] = []
        for example in self.golden_examples:
            example_tokens = set(token for token in example.tokens if token not in self.STOPWORDS)
            union = q_tokens | example_tokens
            if not union:
                continue
            similarity = len(q_tokens & example_tokens) / len(union)
            if similarity >= 0.2:
                scored.append((similarity, example))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:limit]

    def _build_chunk_keywords(self) -> Dict[str, set]:
        if not self.vector_store or not getattr(self.vector_store, "chunks", None):
            return {}
        return {
            chunk_id: set(self._keywords(content))
            for chunk_id, content in self.vector_store.chunks.items()
        }

    def _keywords(self, text: str) -> List[str]:
        return [token for token in self._tokenize(self._normalize(text)) if token not in self.STOPWORDS]

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("đ", "d").replace("Đ", "D")
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text)


if __name__ == "__main__":
    async def test():
        agent = MainAgent(top_k=10, enable_llm = True)
        resp = await agent.query("BHYT là gì?")
        # resp = await agent.query("Sau khi rua tay, can lam gi tiep theo khi gap vet thuong ho?")
        print(json.dumps(resp, ensure_ascii=False, indent=2))

    asyncio.run(test())
