import json
import asyncio
import os
import uuid
from typing import List, Dict
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[Dict]:
    """
    Chia nhỏ văn bản thành các đoạn (chunks) với độ chồng lấp.
    Mỗi đoạn được gán một ID duy nhất.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk_content = text[start:end]
        chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
        chunks.append({"id": chunk_id, "content": chunk_content})
        start += chunk_size - overlap
    return chunks

async def generate_qa_from_chunk(chunk: Dict) -> List[Dict]:
    """
    Sử dụng OpenAI/Anthropic API để tạo các cặp (Question, Expected Answer, Context)
    từ đoạn văn bản cho trước.
    Yêu cầu: Tạo ít nhất 1 câu hỏi 'lừa' (adversarial) hoặc cực khó.
    """
    prompt = f"""
Dựa trên đoạn văn bản sau đây (đoạn {chunk['id']}), hãy tạo ra 4 cặp Câu hỏi và Trả lời.
Yêu cầu JSON format chính xác tuyệt đối như sau:
{{
  "qa_pairs": [
    {{
      "question": "Câu hỏi...",
      "expected_answer": "Câu trả lời..."
    }}
  ]
}}

Văn bản:
\"\"\"
{chunk['content']}
\"\"\"
"""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates high-quality RAG evaluation datasets. Respond only with JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        qa_list = data.get("qa_pairs", [])
        
        # Nếu LLM trả về format khác, cố gắng bóc tách
        if not qa_list and isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    qa_list = val
                    break
        
        # Gán thêm metadata và ground truth
        results = []
        for qa in qa_list:
            # Linh hoạt với tên key
            q = qa.get("question") or qa.get("query")
            a = qa.get("expected_answer") or qa.get("answer")
            
            if q and a:
                results.append({
                    "question": q,
                    "expected_answer": a,
                    "expected_retrieval_ids": [chunk["id"]],
                    "context": chunk["content"],
                    "metadata": {
                        "difficulty": "medium",
                        "type": "retrieval-focused",
                        "source_chunk_id": chunk["id"]
                    }
                })
        return results
    except Exception as e:
        print(f"Error generating QA for chunk {chunk['id']}: {e}")
        return []

async def main():
    source_path = "data/source_docs.txt"
    if not os.path.exists(source_path):
        print(f"❌ Không tìm thấy file {source_path}. Vui lòng tạo file này trước.")
        return

    with open(source_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    print("📄 Chunks text...")
    chunks = chunk_text(full_text)
    print(f"✅ Đã tạo {len(chunks)} chunks.")

    all_qa_pairs = []
    print(f"🚀 Bắt đầu tạo QA pairs (Mục tiêu 50+)...")
    
    # Chạy theo nhóm để tránh rate limit
    batch_size = 5
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        tasks = [generate_qa_from_chunk(c) for c in batch]
        results = await asyncio.gather(*tasks)
        for res in results:
            all_qa_pairs.extend(res)
        print(f"⏳ Đã tạo được {len(all_qa_pairs)} cases...")
        
        if len(all_qa_pairs) >= 150: # Dừng khi đã đủ mục tiêu (nhiều data hơn)
            break

    # Lưu kết quả
    os.makedirs("data", exist_ok=True)
    with open("data/golden_set.jsonl", "w", encoding="utf-8") as f:
        for pair in all_qa_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    
    print(f"🎉 Hoàn thành! Đã lưu {len(all_qa_pairs)} cases vào data/golden_set.jsonl")

if __name__ == "__main__":
    asyncio.run(main())
