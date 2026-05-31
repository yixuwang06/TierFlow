"""Completion evaluation module."""

from dataclasses import dataclass
from typing import List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CompletionMetrics:
    """Metrics for completion evaluation."""

    correctness_score: float  # 0-1: 结果正确性
    completeness_score: float  # 0-1: 任务完整性
    quality_score: float  # 0-1: 代码/输出质量
    progress_score: float  # 0-1: 相比上轮的进展
    overall_score: float  # 0-1: 综合得分
    confidence: float  # 0-1: 评估置信度


@dataclass
class CompletionDecision:
    """Completion decision result."""

    should_complete: bool
    reason: str
    metrics: CompletionMetrics
    next_steps: List[str]
    partial_success: bool  # 部分成功
    can_continue: bool  # 是否可以继续改进


class CompletionEvaluator:
    """Enhanced completion evaluation with multi-dimensional assessment."""

    def __init__(
        self,
        min_overall_score: float = 0.8,
        min_correctness: float = 0.7,
        min_completeness: float = 0.8,
        enable_partial_success: bool = True,
        stagnation_threshold: int = 3,  # 连续多少轮无进展视为停滞
    ):
        self.min_overall_score = min_overall_score
        self.min_correctness = min_correctness
        self.min_completeness = min_completeness
        self.enable_partial_success = enable_partial_success
        self.stagnation_threshold = stagnation_threshold

        self.history_scores: List[float] = []
        self.stagnation_count = 0

    def evaluate(
        self,
        evaluation_result: dict,
        round_results: List[dict],
        iteration: int,
    ) -> CompletionDecision:
        """Evaluate completion with multiple criteria."""

        # 提取评估指标
        metrics = self._extract_metrics(evaluation_result, round_results)

        # 记录历史得分
        self.history_scores.append(metrics.overall_score)

        # 检测停滞
        is_stagnant = self._detect_stagnation()

        # 检查失败的子任务数量
        failed_count = sum(1 for r in round_results if r.get("status") == "failed")
        total_count = len(round_results)
        success_rate = (total_count - failed_count) / total_count if total_count > 0 else 0

        # 多维度判断
        should_complete = False
        reason = ""
        partial_success = False
        can_continue = True
        next_steps = evaluation_result.get("next_steps", [])

        # 1. 完美完成：所有指标达标
        if (
            metrics.overall_score >= self.min_overall_score
            and metrics.correctness_score >= self.min_correctness
            and metrics.completeness_score >= self.min_completeness
            and evaluation_result.get("complete", False)
        ):
            should_complete = True
            reason = "All quality metrics met and task marked complete"
            logger.info(
                "perfect_completion",
                iteration=iteration,
                overall_score=metrics.overall_score,
            )

        # 2. 高质量完成：主要指标达标，允许小瑕疵
        elif (
            metrics.overall_score >= self.min_overall_score * 0.95
            and metrics.correctness_score >= self.min_correctness
            and success_rate >= 0.9
        ):
            should_complete = True
            reason = "High quality completion with minor imperfections"
            logger.info(
                "high_quality_completion",
                iteration=iteration,
                overall_score=metrics.overall_score,
            )

        # 3. 部分成功：核心功能完成，但有改进空间
        elif (
            self.enable_partial_success
            and metrics.correctness_score >= self.min_correctness * 0.9
            and metrics.completeness_score >= 0.6
            and success_rate >= 0.7
        ):
            partial_success = True
            if is_stagnant or iteration >= 50:
                should_complete = True
                reason = "Partial success - core functionality complete, stopping due to stagnation or iteration limit"
                logger.info(
                    "partial_success_completion",
                    iteration=iteration,
                    correctness=metrics.correctness_score,
                    completeness=metrics.completeness_score,
                )
            else:
                reason = "Partial success - continuing to improve"
                logger.info(
                    "partial_success_continue",
                    iteration=iteration,
                    next_steps=next_steps,
                )

        # 4. 停滞检测：连续多轮无明显进展
        elif is_stagnant:
            should_complete = True
            reason = f"Stagnation detected - no progress in {self.stagnation_count} iterations"
            can_continue = False
            logger.warning(
                "stagnation_detected",
                iteration=iteration,
                stagnation_count=self.stagnation_count,
                recent_scores=self.history_scores[-5:],
            )

        # 5. 低质量但无改进方向：没有明确的next_steps
        elif not next_steps and iteration >= 10:
            should_complete = True
            reason = "No clear next steps identified after multiple iterations"
            can_continue = False
            logger.warning(
                "no_next_steps",
                iteration=iteration,
                overall_score=metrics.overall_score,
            )

        # 6. 持续失败：成功率过低
        elif success_rate < 0.3 and iteration >= 5:
            should_complete = True
            reason = f"Low success rate ({success_rate:.2%}) - task may be infeasible"
            can_continue = False
            logger.error(
                "low_success_rate",
                iteration=iteration,
                success_rate=success_rate,
                failed_count=failed_count,
            )

        else:
            reason = "Continuing - quality metrics not yet met"
            logger.info(
                "continuing_iteration",
                iteration=iteration,
                overall_score=metrics.overall_score,
                next_steps_count=len(next_steps),
            )

        return CompletionDecision(
            should_complete=should_complete,
            reason=reason,
            metrics=metrics,
            next_steps=next_steps,
            partial_success=partial_success,
            can_continue=can_continue,
        )

    def _extract_metrics(
        self, evaluation_result: dict, round_results: List[dict]
    ) -> CompletionMetrics:
        """Extract metrics from evaluation result."""

        # 从Claude评估结果中提取
        overall_score = evaluation_result.get("score", 0.5)

        # 尝试提取细分指标，如果没有则使用overall_score估算
        correctness = evaluation_result.get("correctness_score", overall_score)
        completeness = evaluation_result.get("completeness_score", overall_score)
        quality = evaluation_result.get("quality_score", overall_score)
        confidence = evaluation_result.get("confidence", 0.7)

        # 计算进展得分
        progress = self._calculate_progress()

        return CompletionMetrics(
            correctness_score=correctness,
            completeness_score=completeness,
            quality_score=quality,
            progress_score=progress,
            overall_score=overall_score,
            confidence=confidence,
        )

    def _calculate_progress(self) -> float:
        """Calculate progress score based on history."""
        if len(self.history_scores) < 2:
            return 0.5

        recent = self.history_scores[-3:]
        if len(recent) < 2:
            return 0.5

        # 计算最近几轮的平均改进
        improvements = [recent[i] - recent[i-1] for i in range(1, len(recent))]
        avg_improvement = sum(improvements) / len(improvements)

        # 归一化到0-1
        progress = 0.5 + (avg_improvement * 5)  # 放大改进幅度
        return max(0.0, min(1.0, progress))

    def _detect_stagnation(self) -> bool:
        """Detect if progress has stagnated."""
        if len(self.history_scores) < self.stagnation_threshold + 1:
            return False

        recent = self.history_scores[-self.stagnation_threshold:]

        # 检查最近几轮的得分变化
        max_score = max(recent)
        min_score = min(recent)
        score_range = max_score - min_score

        # 如果得分变化很小（<0.05），认为停滞
        if score_range < 0.05:
            self.stagnation_count += 1
            return self.stagnation_count >= self.stagnation_threshold
        else:
            self.stagnation_count = 0
            return False

    def reset(self):
        """Reset evaluator state."""
        self.history_scores.clear()
        self.stagnation_count = 0
