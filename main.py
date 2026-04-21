import asyncio
import json
import os
import time
from engine.runner import BenchmarkRunner, BenchmarkConfig
from engine.retrieval_eval import RetrievalEvaluator
from engine.llm_judge import LLMJudge
from agent.main_agent import MainAgent


class ExpertEvaluator:
    """Đánh giá retrieval thực sự: Hit Rate + MRR tính theo từng case."""

    def __init__(self, retrieval_eval: RetrievalEvaluator):
        self.retrieval_eval = retrieval_eval

    async def score(self, case, resp):
        expected_ids = case.get("expected_retrieval_ids", [])
        retrieved_ids = resp.get("retrieved_ids", [])

        hit_rate = self.retrieval_eval.calculate_hit_rate(expected_ids, retrieved_ids)
        mrr = self.retrieval_eval.calculate_mrr(expected_ids, retrieved_ids)

        return {
            "faithfulness": 0.9,
            "relevancy": 0.8,
            "retrieval": {"hit_rate": hit_rate, "mrr": mrr},
        }


async def run_benchmark_with_results(agent_version: str):
    print(f"Khoi dong Benchmark cho {agent_version}...")

    if not os.path.exists("data/golden_set.jsonl"):
        print("Thieu data/golden_set.jsonl. Hay chay 'python data/synthetic_gen.py' truoc.")
        return None, None

    with open("data/golden_set.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("File data/golden_set.jsonl rong. Hay tao it nhat 1 test case.")
        return None, None

    # Build shared vector store một lần dùng cho cả Agent và Evaluator
    retrieval_eval = RetrievalEvaluator()
    retrieval_eval.build_store_from_dataset(dataset)

    agent = MainAgent(vector_store=retrieval_eval.vector_store)
    evaluator = ExpertEvaluator(retrieval_eval=retrieval_eval)
    judge = LLMJudge()

    # Config cho benchmark
    config = BenchmarkConfig(
        batch_size=5,
        max_retries=3,
        timeout_seconds=60,
        rate_limit_delay=0.1,
        max_concurrent_requests=10,
        enable_progress_tracking=True
    )

    # Use async context manager for proper resource cleanup
    async with BenchmarkRunner(agent, evaluator, judge, config) as runner:
        results = await runner.run_all(dataset)
        
        # Lấy thống kê chi tiết từ runner
        stats = runner.get_statistics()

    total = len(results)
    summary = {
        "metadata": {
            "version": agent_version,
            "total": total,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {
            "avg_score": sum(r["judge"]["final_score"] for r in results) / total,
            "hit_rate": sum(r["ragas"]["retrieval"]["hit_rate"] for r in results) / total,
            "agreement_rate": sum(r["judge"]["agreement_rate"] for r in results) / total
        },
        "performance": {
            "success_rate": stats["success_rate"],
            "average_test_time": stats["average_test_time"],
            "retry_rate": stats["retry_rate"],
            "total_execution_time": stats["total_time"],
            "successful_tests": stats["successful_tests"],
            "failed_tests": stats["failed_tests"]
        }
    }
    return results, summary


async def run_benchmark(version):
    _, summary = await run_benchmark_with_results(version)
    return summary


async def main():
    v1_summary = await run_benchmark("Agent_V1_Base")
    v2_results, v2_summary = await run_benchmark_with_results("Agent_V2_Optimized")

    if not v1_summary or not v2_summary:
        print("Khong the chay Benchmark. Kiem tra lai data/golden_set.jsonl.")
        return

    print("\n📊 --- KẾT QUẢ SO SÁNH (REGRESSION) ---")
    
    # Calculate deltas
    score_delta = v2_summary["metrics"]["avg_score"] - v1_summary["metrics"]["avg_score"]
    hit_rate_delta = v2_summary["metrics"]["hit_rate"] - v1_summary["metrics"]["hit_rate"]
    agreement_delta = v2_summary["metrics"]["agreement_rate"] - v1_summary["metrics"]["agreement_rate"]
    
    # Performance comparison
    v1_success_rate = v1_summary.get("performance", {}).get("success_rate", 0)
    v2_success_rate = v2_summary.get("performance", {}).get("success_rate", 0)
    success_rate_delta = v2_success_rate - v1_success_rate
    
    print(f"📈 Score Delta: {score_delta:+.3f} ({v1_summary['metrics']['avg_score']:.3f} → {v2_summary['metrics']['avg_score']:.3f})")
    print(f"🎯 Hit Rate Delta: {hit_rate_delta:+.3f} ({v1_summary['metrics']['hit_rate']:.3f} → {v2_summary['metrics']['hit_rate']:.3f})")
    print(f"⚖️ Agreement Delta: {agreement_delta:+.3f} ({v1_summary['metrics']['agreement_rate']:.3f} → {v2_summary['metrics']['agreement_rate']:.3f})")
    print(f"✅ Success Rate Delta: {success_rate_delta:+.3f} ({v1_success_rate:.3f} → {v2_success_rate:.3f})")
    
    # Cost estimation (mock for now)
    v1_cost = v1_summary.get("performance", {}).get("total_execution_time", 0) * 0.001  # $0.001 per second
    v2_cost = v2_summary.get("performance", {}).get("total_execution_time", 0) * 0.001
    cost_delta = v2_cost - v1_cost
    print(f"💰 Cost Delta: ${cost_delta:+.4f} (${v1_cost:.4f} → ${v2_cost:.4f})")

    os.makedirs("reports", exist_ok=True)
    
    # Enhanced reports with regression data
    v2_summary["regression_analysis"] = {
        "score_delta": score_delta,
        "hit_rate_delta": hit_rate_delta,
        "agreement_delta": agreement_delta,
        "success_rate_delta": success_rate_delta,
        "cost_delta": cost_delta,
        "v1_metrics": v1_summary["metrics"],
        "v1_performance": v1_summary.get("performance", {})
    }
    
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v2_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(v2_results, f, ensure_ascii=False, indent=2)

    # Auto-gate logic with multiple criteria
    print("\n🚪 --- AUTO-GATE DECISION ---")
    
    # Define thresholds
    MIN_SCORE_IMPROVEMENT = 0.01  # 1% minimum improvement
    MAX_COST_INCREASE = 0.10      # 10% max cost increase
    MIN_SUCCESS_RATE = 0.95       # 95% minimum success rate
    
    gate_decision = "APPROVE"
    reasons = []
    
    if score_delta < MIN_SCORE_IMPROVEMENT:
        gate_decision = "BLOCK"
        reasons.append(f"Score improvement {score_delta:.3f} < {MIN_SCORE_IMPROVEMENT}")
    
    if cost_delta > MAX_COST_INCREASE:
        if gate_decision == "APPROVE":
            gate_decision = "REVIEW"
        reasons.append(f"Cost increase ${cost_delta:.4f} > ${MAX_COST_INCREASE}")
    
    if v2_success_rate < MIN_SUCCESS_RATE:
        gate_decision = "BLOCK"
        reasons.append(f"Success rate {v2_success_rate:.3f} < {MIN_SUCCESS_RATE}")
    
    if hit_rate_delta < 0:
        if gate_decision == "APPROVE":
            gate_decision = "REVIEW"
        reasons.append(f"Hit rate decreased by {abs(hit_rate_delta):.3f}")
    
    # Final decision
    if gate_decision == "APPROVE":
        print("✅ QUYẾT ĐỊNH: CHẤP NHẬN BẢN CẬP NHẬT (APPROVE)")
        print("🎉 Agent V2 meets all quality criteria!")
    elif gate_decision == "REVIEW":
        print("⚠️  QUYẾT ĐỊNH: CẦN REVIEW (MANUAL REVIEW)")
        print(f"🔍 Issues: {', '.join(reasons)}")
    else:
        print("❌ QUYẾT ĐỊNH: TỪ CHỐI (BLOCK RELEASE)")
        print(f"🚫 Blocking reasons: {', '.join(reasons)}")
    
    # Store decision in summary
    v2_summary["release_gate"] = {
        "decision": gate_decision,
        "reasons": reasons,
        "thresholds": {
            "min_score_improvement": MIN_SCORE_IMPROVEMENT,
            "max_cost_increase": MAX_COST_INCREASE,
            "min_success_rate": MIN_SUCCESS_RATE
        }
    }
    
    # Update summary file with decision
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v2_summary, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
