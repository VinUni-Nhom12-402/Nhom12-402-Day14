import math
import re
from collections import Counter
from typing import List, Dict


class SimpleVectorStore:
    """
    Vector store đơn giản dùng TF-IDF + Cosine Similarity.
    Không cần API bên ngoài, chạy hoàn toàn local.
    """

    def __init__(self):
        self.chunks: Dict[str, str] = {}       # chunk_id -> content
        self.idf: Dict[str, float] = {}
        self.tfidf_vectors: Dict[str, Dict[str, float]] = {}

    def add_chunk(self, chunk_id: str, content: str):
        self.chunks[chunk_id] = content

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def build_index(self):
        """Tính TF-IDF cho toàn bộ corpus đã nạp."""
        N = len(self.chunks)
        if N == 0:
            return

        doc_freq: Counter = Counter()
        tf_vectors: Dict[str, Dict[str, float]] = {}

        for cid, content in self.chunks.items():
            tokens = self._tokenize(content)
            if not tokens:
                tf_vectors[cid] = {}
                continue
            tf = Counter(tokens)
            total = len(tokens)
            tf_vectors[cid] = {t: count / total for t, count in tf.items()}
            for term in set(tokens):
                doc_freq[term] += 1

        # IDF = log(N / df)
        for term, df in doc_freq.items():
            self.idf[term] = math.log(N / df)

        # TF-IDF vector
        for cid, tf in tf_vectors.items():
            self.tfidf_vectors[cid] = {
                t: tf[t] * self.idf.get(t, 0.0) for t in tf
            }

    def _cosine_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        common_terms = set(vec_a) & set(vec_b)
        dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Trả về danh sách chunk_id được xếp hạng theo độ tương đồng với query."""
        tokens = self._tokenize(query)
        if not tokens:
            return []

        tf = Counter(tokens)
        total = len(tokens)
        query_vec = {
            t: (tf[t] / total) * self.idf.get(t, 0.0) for t in tf
        }

        scores = {
            cid: self._cosine_similarity(query_vec, vec)
            for cid, vec in self.tfidf_vectors.items()
        }
        ranked = sorted(scores, key=lambda x: scores[x], reverse=True)
        return ranked[:top_k]


class RetrievalEvaluator:

    def __init__(self):
        self.vector_store = SimpleVectorStore()
        self._index_built = False

    def build_store_from_dataset(self, dataset: List[Dict]):
        """
        Xây dựng Vector Store từ golden dataset.
        Mỗi chunk chỉ được nạp 1 lần (dedup theo chunk_id).
        """
        seen_ids = set()
        for case in dataset:
            chunk_id = case.get("metadata", {}).get("source_chunk_id")
            context = case.get("context", "")
            if chunk_id and chunk_id not in seen_ids and context:
                self.vector_store.add_chunk(chunk_id, context)
                seen_ids.add(chunk_id)

        self.vector_store.build_index()
        self._index_built = True
        print(f"[OK] Vector Store da index {len(seen_ids)} chunks.")

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Hit Rate = 1 nếu ít nhất 1 expected_id nằm trong top_k retrieved_ids.
        """
        top_retrieved = retrieved_ids[:top_k]
        return 1.0 if any(doc_id in top_retrieved for doc_id in expected_ids) else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """
        MRR = 1 / (vị trí đầu tiên tìm thấy expected_id), tính từ 1.
        Trả về 0 nếu không tìm thấy.
        """
        for rank, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in expected_ids:
                return 1.0 / rank
        return 0.0

    async def evaluate_batch(self, dataset: List[Dict], top_k: int = 3) -> Dict:
        """
        Tính Hit Rate và MRR thực sự cho toàn bộ dataset.
        """
        if not self._index_built:
            self.build_store_from_dataset(dataset)

        hit_rates = []
        mrrs = []
        per_case_results = []

        for case in dataset:
            expected_ids = case.get("expected_retrieval_ids", [])
            query = case.get("question", "")

            retrieved_ids = self.vector_store.retrieve(query, top_k=top_k)

            hit = self.calculate_hit_rate(expected_ids, retrieved_ids, top_k)
            mrr = self.calculate_mrr(expected_ids, retrieved_ids)

            hit_rates.append(hit)
            mrrs.append(mrr)
            per_case_results.append({
                "question": query,
                "expected_ids": expected_ids,
                "retrieved_ids": retrieved_ids,
                "hit": hit,
                "mrr": mrr,
            })

        avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0
        avg_mrr = sum(mrrs) / len(mrrs) if mrrs else 0.0

        return {
            "avg_hit_rate": avg_hit_rate,
            "avg_mrr": avg_mrr,
            "total_evaluated": len(hit_rates),
            "per_case": per_case_results,
        }
