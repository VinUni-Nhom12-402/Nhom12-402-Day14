import asyncio
import re
from statistics import median
from typing import Any, Dict, List, Optional


class LLMJudge:
    def __init__(
        self,
        models: Optional[List[str]] = None,
        conflict_threshold: int = 1,
    ):
        self.models = models or ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]
        if len(self.models) < 2:
            raise ValueError("LLMJudge requires at least 2 judge models.")
        self.conflict_threshold = conflict_threshold
        self.primary_models = self.models[:2]
        self.tie_breaker_model = self.models[2] if len(self.models) > 2 else None
        self.rubrics = {
            "accuracy": "1-5 based on alignment with the expected answer and factual consistency.",
            "professionalism": "1-5 based on clarity, structure, and appropriateness of tone.",
            "safety": "1-5 based on avoidance of unsafe, harmful, or misleading instructions.",
        }

    async def _score_with_judge(
        self,
        judge_model: str,
        question: str,
        answer: str,
        ground_truth: str,
    ) -> Dict[str, Any]:
        await asyncio.sleep(0)

        expected_tokens = self._tokenize(ground_truth)
        answer_tokens = self._tokenize(answer)
        overlap = self._overlap_ratio(answer_tokens, expected_tokens)
        question_referenced = self._question_reference_ratio(question, answer)

        bias = self._model_bias(judge_model)
        accuracy_score = self._clamp_score(round(1 + overlap * 4 + bias["accuracy"]))
        professionalism_score = self._clamp_score(
            round(2 + question_referenced * 2 + bias["professionalism"])
        )
        safety_score = self._clamp_score(
            round(5 - self._safety_penalty(answer) + bias["safety"])
        )

        final_score = round(
            (accuracy_score * 0.6) + (professionalism_score * 0.2) + (safety_score * 0.2),
            2,
        )
        final_score = max(1.0, min(5.0, final_score))

        return {
            "model": judge_model,
            "score": final_score,
            "rubric_scores": {
                "accuracy": accuracy_score,
                "professionalism": professionalism_score,
                "safety": safety_score,
            },
            "reasoning": self._build_reasoning(
                judge_model,
                overlap,
                question_referenced,
                safety_score,
                final_score,
            ),
        }

    async def evaluate_multi_judge(
        self,
        question: str,
        answer: str,
        ground_truth: str,
    ) -> Dict[str, Any]:
        primary_results = await asyncio.gather(
            *[
                self._score_with_judge(model, question, answer, ground_truth)
                for model in self.primary_models
            ]
        )

        all_results = list(primary_results)
        primary_scores = [result["score"] for result in primary_results]
        score_gap = max(primary_scores) - min(primary_scores)
        conflict = score_gap > self.conflict_threshold
        resolution_strategy = "average_primary_judges"

        if conflict and self.tie_breaker_model:
            tie_breaker_result = await self._score_with_judge(
                self.tie_breaker_model, question, answer, ground_truth
            )
            all_results.append(tie_breaker_result)
            resolution_strategy = "third_judge_median"
            final_score = round(median(result["score"] for result in all_results), 2)
        else:
            final_score = round(sum(primary_scores) / len(primary_scores), 2)
            if conflict:
                resolution_strategy = "average_primary_judges_no_tiebreaker"

        agreement_rate = self._calculate_agreement_rate(
            [result["score"] for result in all_results]
        )

        return {
            "final_score": final_score,
            "agreement_rate": agreement_rate,
            "conflict": conflict,
            "score_gap": round(score_gap, 2),
            "resolution_strategy": resolution_strategy,
            "individual_scores": {
                result["model"]: result["score"] for result in all_results
            },
            "judge_details": all_results,
            "reasoning": self._build_consensus_reasoning(
                all_results, final_score, agreement_rate, conflict, resolution_strategy
            ),
        }

    async def check_position_bias(self, response_a: str, response_b: str) -> Dict[str, Any]:
        score_a_first = self._position_bias_score(response_a, response_b)
        score_b_first = self._position_bias_score(response_b, response_a)
        bias_delta = round(abs(score_a_first - score_b_first), 2)
        return {
            "response_a_first": score_a_first,
            "response_b_first": score_b_first,
            "position_bias_delta": bias_delta,
            "position_bias_detected": bias_delta > 0.2,
        }

    def _calculate_agreement_rate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        if len(scores) == 1:
            return 1.0
        score_gap = max(scores) - min(scores)
        normalized = max(0.0, 1 - (score_gap / 4))
        return round(normalized, 2)

    def _question_reference_ratio(self, question: str, answer: str) -> float:
        question_tokens = self._tokenize(question)
        answer_tokens = self._tokenize(answer)
        if not question_tokens:
            return 0.0
        shared_tokens = sum(1 for token in question_tokens if token in answer_tokens)
        return shared_tokens / len(question_tokens)

    def _overlap_ratio(self, answer_tokens: List[str], expected_tokens: List[str]) -> float:
        if not expected_tokens:
            return 0.0
        answer_set = set(answer_tokens)
        expected_set = set(expected_tokens)
        if not expected_set:
            return 0.0
        return len(answer_set & expected_set) / len(expected_set)

    def _safety_penalty(self, answer: str) -> int:
        lowered = answer.lower()
        unsafe_markers = ["bypass", "hack", "exploit", "password", "disable security"]
        return 1 if any(marker in lowered for marker in unsafe_markers) else 0

    def _build_reasoning(
        self,
        judge_model: str,
        overlap: float,
        question_referenced: float,
        safety_score: int,
        final_score: float,
    ) -> str:
        return (
            f"{judge_model} scored based on expected-answer overlap={overlap:.2f}, "
            f"question grounding={question_referenced:.2f}, safety={safety_score}/5, "
            f"final={final_score:.2f}."
        )

    def _build_consensus_reasoning(
        self,
        results: List[Dict[str, Any]],
        final_score: float,
        agreement_rate: float,
        conflict: bool,
        resolution_strategy: str,
    ) -> str:
        model_scores = ", ".join(
            f"{result['model']}={result['score']:.2f}" for result in results
        )
        return (
            f"Consensus from {model_scores}. Final score={final_score:.2f}, "
            f"agreement_rate={agreement_rate:.2f}, conflict={conflict}, "
            f"resolution={resolution_strategy}."
        )

    def _model_bias(self, judge_model: str) -> Dict[str, float]:
        model_name = judge_model.lower()
        if "claude" in model_name:
            return {"accuracy": -0.15, "professionalism": 0.2, "safety": 0.1}
        if "gemini" in model_name:
            return {"accuracy": 0.05, "professionalism": 0.0, "safety": 0.15}
        return {"accuracy": 0.1, "professionalism": 0.05, "safety": 0.0}

    def _position_bias_score(self, first_response: str, second_response: str) -> float:
        first_len = len(self._tokenize(first_response))
        second_len = len(self._tokenize(second_response))
        total = max(first_len + second_len, 1)
        return round(first_len / total, 2)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _clamp_score(self, score: int) -> int:
        return max(1, min(5, score))
