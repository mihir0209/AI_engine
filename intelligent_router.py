"""
Intelligent routing module for AI Engine
Provides task-based model selection, cost optimization, latency tracking, and A/B testing
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
import random
import time
from collections import defaultdict


@dataclass
class TaskProfile:
    """Profile for a specific task type"""
    task_type: str
    recommended_models: List[str]
    max_tokens: int
    temperature: float
    cost_weight: float = 0.3
    quality_weight: float = 0.5
    speed_weight: float = 0.2


@dataclass
class ModelPricing:
    """Pricing information for a model"""
    model_name: str
    provider: str
    input_cost_per_1k: float  # Cost per 1000 input tokens
    output_cost_per_1k: float  # Cost per 1000 output tokens
    rpm_limit: int = 60
    daily_limit: int = 1000


@dataclass
class LatencyStats:
    """Latency statistics for a provider"""
    provider: str
    model: str
    total_requests: int = 0
    total_latency: float = 0.0
    min_latency: float = float('inf')
    max_latency: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    recent_latencies: List[float] = field(default_factory=list)

    def record(self, latency: float):
        """Record a latency measurement"""
        self.total_requests += 1
        self.total_latency += latency
        self.min_latency = min(self.min_latency, latency)
        self.max_latency = max(self.max_latency, latency)

        # Keep last 100 measurements for percentile calculation
        self.recent_latencies.append(latency)
        if len(self.recent_latencies) > 100:
            self.recent_latencies.pop(0)

        # Update percentiles
        if self.recent_latencies:
            sorted_lat = sorted(self.recent_latencies)
            n = len(sorted_lat)
            self.p50_latency = sorted_lat[n // 2]
            self.p95_latency = sorted_lat[int(n * 0.95)]
            self.p99_latency = sorted_lat[int(n * 0.99)]

    @property
    def avg_latency(self) -> float:
        """Average latency"""
        return self.total_latency / self.total_requests if self.total_requests > 0 else 0.0


# Task profiles for different use cases
TASK_PROFILES = {
    "coding": TaskProfile(
        task_type="coding",
        recommended_models=["gpt-4", "claude-3-opus", "gpt-4-turbo", "codestral"],
        max_tokens=4096,
        temperature=0.2,
        cost_weight=0.2,
        quality_weight=0.6,
        speed_weight=0.2
    ),
    "writing": TaskProfile(
        task_type="writing",
        recommended_models=["gpt-4", "claude-3-opus", "gpt-4-turbo"],
        max_tokens=4096,
        temperature=0.7,
        cost_weight=0.3,
        quality_weight=0.4,
        speed_weight=0.3
    ),
    "analysis": TaskProfile(
        task_type="analysis",
        recommended_models=["gpt-4", "claude-3-opus", "gpt-4-turbo"],
        max_tokens=2048,
        temperature=0.3,
        cost_weight=0.3,
        quality_weight=0.5,
        speed_weight=0.2
    ),
    "creative": TaskProfile(
        task_type="creative",
        recommended_models=["gpt-4", "claude-3-opus", "gpt-4-turbo"],
        max_tokens=2048,
        temperature=0.9,
        cost_weight=0.2,
        quality_weight=0.4,
        speed_weight=0.4
    ),
    "quick": TaskProfile(
        task_type="quick",
        recommended_models=["gpt-3.5-turbo", "gpt-4-mini", "claude-3-haiku", "llama-3-8b"],
        max_tokens=1024,
        temperature=0.5,
        cost_weight=0.5,
        quality_weight=0.2,
        speed_weight=0.3
    ),
    "summarization": TaskProfile(
        task_type="summarization",
        recommended_models=["gpt-4-mini", "claude-3-haiku", "gpt-3.5-turbo"],
        max_tokens=1024,
        temperature=0.3,
        cost_weight=0.4,
        quality_weight=0.4,
        speed_weight=0.2
    ),
    "translation": TaskProfile(
        task_type="translation",
        recommended_models=["gpt-4", "claude-3-opus", "gpt-4-turbo"],
        max_tokens=2048,
        temperature=0.3,
        cost_weight=0.3,
        quality_weight=0.5,
        speed_weight=0.2
    ),
    "math": TaskProfile(
        task_type="math",
        recommended_models=["gpt-4", "claude-3-opus", "gpt-4-turbo"],
        max_tokens=2048,
        temperature=0.0,
        cost_weight=0.2,
        quality_weight=0.6,
        speed_weight=0.2
    )
}

# Model pricing (approximate, should be updated from provider APIs)
MODEL_PRICING: List[ModelPricing] = [
    ModelPricing("gpt-4", "openai", 0.03, 0.06),
    ModelPricing("gpt-4-turbo", "openai", 0.01, 0.03),
    ModelPricing("gpt-4-mini", "openai", 0.00015, 0.0006),
    ModelPricing("gpt-3.5-turbo", "openai", 0.0005, 0.0015),
    ModelPricing("claude-3-opus", "anthropic", 0.015, 0.075),
    ModelPricing("claude-3-sonnet", "anthropic", 0.003, 0.015),
    ModelPricing("claude-3-haiku", "anthropic", 0.00025, 0.00125),
    ModelPricing("llama-3-8b", "groq", 0.0001, 0.0001),
    ModelPricing("llama-3-70b", "groq", 0.0009, 0.0009),
]


class IntelligentRouter:
    """Smart routing based on task type, cost, quality, and latency"""

    def __init__(self):
        self.task_profiles = TASK_PROFILES
        self.model_pricing = {f"{p.provider}/{p.model_name}": p for p in MODEL_PRICING}
        self.usage_cache = {}  # Track usage for cost optimization
        self.latency_stats: Dict[str, LatencyStats] = {}  # Track latency per provider
        self.ab_tests: Dict[str, Dict] = {}  # A/B test configurations
        self.ab_test_results: Dict[str, List[Dict]] = defaultdict(list)  # A/B test results

    def record_latency(self, provider: str, model: str, latency: float, success: bool = True):
        """Record latency for a provider"""
        key = f"{provider}/{model}"
        if key not in self.latency_stats:
            self.latency_stats[key] = LatencyStats(provider=provider, model=model)
        self.latency_stats[key].record(latency)

    def get_latency_stats(self, provider: str = None) -> Dict:
        """Get latency statistics"""
        if provider:
            return {k: v for k, v in self.latency_stats.items() if v.provider == provider}
        return {k: {
            "provider": v.provider,
            "model": v.model,
            "total_requests": v.total_requests,
            "avg_latency": round(v.avg_latency, 3),
            "p50_latency": round(v.p50_latency, 3),
            "p95_latency": round(v.p95_latency, 3),
            "p99_latency": round(v.p99_latency, 3),
            "min_latency": round(v.min_latency, 3) if v.min_latency != float('inf') else 0,
            "max_latency": round(v.max_latency, 3)
        } for k, v in self.latency_stats.items()}

    def create_ab_test(self, test_id: str, providers: List[str], traffic_split: List[float]):
        """Create an A/B test with traffic splitting"""
        if len(providers) != len(traffic_split):
            raise ValueError("providers and traffic_split must have same length")
        if abs(sum(traffic_split) - 1.0) > 0.01:
            raise ValueError("traffic_split must sum to 1.0")

        self.ab_tests[test_id] = {
            "providers": providers,
            "traffic_split": traffic_split,
            "created_at": datetime.now().isoformat(),
            "active": True
        }

    def select_ab_test_provider(self, test_id: str) -> Optional[str]:
        """Select provider for A/B test based on traffic split"""
        if test_id not in self.ab_tests or not self.ab_tests[test_id]["active"]:
            return None

        test = self.ab_tests[test_id]
        providers = test["providers"]
        split = test["traffic_split"]

        # Random selection based on traffic split
        rand = random.random()
        cumulative = 0.0
        for i, weight in enumerate(split):
            cumulative += weight
            if rand <= cumulative:
                return providers[i]

        return providers[-1]

    def record_ab_test_result(self, test_id: str, provider: str, success: bool, latency: float):
        """Record A/B test result"""
        self.ab_test_results[test_id].append({
            "provider": provider,
            "success": success,
            "latency": latency,
            "timestamp": datetime.now().isoformat()
        })

    def get_ab_test_results(self, test_id: str) -> Dict:
        """Get A/B test results summary"""
        if test_id not in self.ab_test_results:
            return {}

        results = self.ab_test_results[test_id]
        provider_stats = defaultdict(lambda: {"total": 0, "successes": 0, "latencies": []})

        for r in results:
            provider_stats[r["provider"]]["total"] += 1
            if r["success"]:
                provider_stats[r["provider"]]["successes"] += 1
            provider_stats[r["provider"]]["latencies"].append(r["latency"])

        summary = {}
        for provider, stats in provider_stats.items():
            latencies = stats["latencies"]
            summary[provider] = {
                "total_requests": stats["total"],
                "successes": stats["successes"],
                "success_rate": round(stats["successes"] / stats["total"], 4) if stats["total"] > 0 else 0,
                "avg_latency": round(sum(latencies) / len(latencies), 3) if latencies else 0,
                "p95_latency": round(sorted(latencies)[int(len(latencies) * 0.95)], 3) if len(latencies) > 1 else 0
            }

        return {
            "test_id": test_id,
            "config": self.ab_tests.get(test_id, {}),
            "results": summary,
            "total_requests": len(results)
        }

    def detect_task_type(self, messages: List[Dict]) -> str:
        """Automatically detect task type from messages"""
        if not messages:
            return "quick"

        # Get the last user message
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return "quick"

        last_message = user_messages[-1].get("content", "").lower()

        # Keyword-based detection
        coding_keywords = ["code", "function", "class", "debug", "error", "program", "script", "implement", "refactor"]
        writing_keywords = ["write", "essay", "story", "article", "blog", "content", "creative"]
        analysis_keywords = ["analyze", "compare", "evaluate", "explain", "explain why", "reason"]
        math_keywords = ["calculate", "solve", "equation", "math", "formula", "proof"]
        translation_keywords = ["translate", "translation", "language", "localize"]
        summary_keywords = ["summarize", "summary", "tldr", "brief", "overview"]

        if any(keyword in last_message for keyword in coding_keywords):
            return "coding"
        elif any(keyword in last_message for keyword in writing_keywords):
            return "writing"
        elif any(keyword in last_message for keyword in math_keywords):
            return "math"
        elif any(keyword in last_message for keyword in translation_keywords):
            return "translation"
        elif any(keyword in last_message for keyword in summary_keywords):
            return "summarization"
        elif any(keyword in last_message for keyword in analysis_keywords):
            return "analysis"

        # Check for creative prompts
        creative_indicators = ["story", "poem", "creative", "imagine", "fiction"]
        if any(indicator in last_message for indicator in creative_indicators):
            return "creative"

        return "quick"  # Default for short/simple queries

    def get_task_profile(self, task_type: str) -> TaskProfile:
        """Get profile for a specific task type"""
        return self.task_profiles.get(task_type, self.task_profiles["quick"])

    def calculate_model_score(
        self,
        model_name: str,
        provider: str,
        task_profile: TaskProfile,
        provider_stats: Dict = None
    ) -> float:
        """Calculate a score for a model based on task requirements"""
        pricing_key = f"{provider}/{model_name}"
        pricing = self.model_pricing.get(pricing_key)

        # Base score from task profile recommendation
        is_recommended = model_name in task_profile.recommended_models
        base_score = 1.0 if is_recommended else 0.5

        # Cost score (lower cost = higher score)
        cost_score = 1.0
        if pricing:
            avg_cost = (pricing.input_cost_per_1k + pricing.output_cost_per_1k) / 2
            cost_score = max(0.1, 1.0 - (avg_cost * 10))  # Normalize

        # Quality score (from provider stats if available)
        quality_score = 0.7  # Default
        if provider_stats:
            success_rate = provider_stats.get("success_rate", 0.7)
            quality_score = success_rate

        # Speed score (from response time if available)
        speed_score = 0.7  # Default
        if provider_stats:
            avg_response_time = provider_stats.get("avg_response_time", 2.0)
            speed_score = max(0.1, 1.0 - (avg_response_time / 10))  # Normalize

        # Weighted final score
        final_score = (
            base_score * 0.3 +
            cost_score * task_profile.cost_weight +
            quality_score * task_profile.quality_weight +
            speed_score * task_profile.speed_weight
        )

        return final_score

    def select_optimal_provider(
        self,
        messages: List[Dict],
        available_providers: List[Tuple[str, Dict]],
        provider_stats: Dict = None,
        task_type: str = None
    ) -> Tuple[str, str, TaskProfile]:
        """Select optimal provider based on task and metrics"""
        # Detect task type if not specified
        if not task_type:
            task_type = self.detect_task_type(messages)

        task_profile = self.get_task_profile(task_type)

        best_provider = None
        best_model = None
        best_score = -1

        for provider_name, config in available_providers:
            model = config.get("model", "unknown")
            score = self.calculate_model_score(
                model, provider_name, task_profile,
                provider_stats.get(provider_name) if provider_stats else None
            )

            if score > best_score:
                best_score = score
                best_provider = provider_name
                best_model = model

        return best_provider, best_model, task_profile

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost for a request"""
        pricing_key = f"{provider}/{model}"
        pricing = self.model_pricing.get(pricing_key)

        if not pricing:
            return 0.0

        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k

        return input_cost + output_cost

    def get_cost_comparison(
        self,
        task_type: str,
        input_tokens: int = 1000,
        output_tokens: int = 500
    ) -> List[Dict]:
        """Compare costs across providers for a task type"""
        task_profile = self.get_task_profile(task_type)
        comparisons = []

        for pricing in self.model_pricing.values():
            cost = self.estimate_cost(
                pricing.provider,
                pricing.model_name,
                input_tokens,
                output_tokens
            )

            comparisons.append({
                "provider": pricing.provider,
                "model": pricing.model_name,
                "estimated_cost": round(cost, 6),
                "recommended": pricing.model_name in task_profile.recommended_models
            })

        return sorted(comparisons, key=lambda x: x["estimated_cost"])


# Global instance
intelligent_router = IntelligentRouter()
