import asyncio
from typing import List, Dict


class MainAgent:
    """
    Agent RAG đơn giản. Nhận Vector Store từ bên ngoài để thực hiện retrieval thực sự,
    sau đó dùng context tìm được để tạo câu trả lời.
    """

    def __init__(self, vector_store=None):
        self.name = "SupportAgent-v1"
        self.vector_store = vector_store  # SimpleVectorStore instance

    async def query(self, question: str, top_k: int = 3) -> Dict:
        """
        RAG pipeline:
        1. Retrieval: Dùng Vector Store tìm top-K chunk liên quan.
        2. Generation: Tạo câu trả lời từ các chunk đó (mô phỏng LLM call).
        """
        await asyncio.sleep(0.1)  # mô phỏng độ trễ mạng

        retrieved_ids: List[str] = []
        contexts: List[str] = []

        if self.vector_store and self.vector_store.chunks:
            retrieved_ids = self.vector_store.retrieve(question, top_k=top_k)
            contexts = [
                self.vector_store.chunks[cid]
                for cid in retrieved_ids
                if cid in self.vector_store.chunks
            ]
        else:
            # fallback khi chưa có vector store
            contexts = ["Đoạn văn bản trích dẫn mẫu..."]

        context_text = "\n---\n".join(contexts) if contexts else "Không tìm thấy context liên quan."
        answer = f"Dựa trên tài liệu: {context_text[:200]}..."

        return {
            "answer": answer,
            "contexts": contexts,
            "retrieved_ids": retrieved_ids,
            "metadata": {
                "model": "gpt-4o-mini",
                "tokens_used": 150 + len(question) // 4,
                "sources": ["source_docs.txt"],
            },
        }


if __name__ == "__main__":
    async def test():
        agent = MainAgent()
        resp = await agent.query("Bệnh tiểu đường là gì?")
        print(resp)
    asyncio.run(test())
