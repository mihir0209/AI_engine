"""
Batch processing for AI Engine
Process multiple prompts in parallel
"""
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class BatchRequest:
    """Single request in a batch"""
    id: int
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a batch request"""
    id: int
    success: bool
    content: str = ""
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    response_time: float = 0.0


class BatchProcessor:
    """Process multiple requests in parallel"""

    def __init__(self, engine, max_concurrent: int = 5):
        self.engine = engine
        self.max_concurrent = max_concurrent

    async def process_batch(
        self,
        requests: List[Dict[str, Any]],
        model: str = None,
        provider: str = None
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of requests in parallel.

        Args:
            requests: List of request dicts with 'messages' key
            model: Default model for all requests
            provider: Default provider for all requests

        Returns:
            List of result dicts
        """
        if not requests:
            return []

        # Limit batch size
        if len(requests) > 100:
            requests = requests[:100]

        results = []

        # Process in parallel with concurrency limit
        async def process_single(req_data):
            try:
                messages = req_data.get("messages", [])
                req_model = req_data.get("model", model)
                req_provider = req_data.get("provider", provider)

                # Run in thread pool
                result = await asyncio.to_thread(
                    self.engine.chat_completion,
                    messages=messages,
                    model=req_model,
                    preferred_provider=req_provider
                )

                return {
                    "success": result.success,
                    "content": result.content if result.success else None,
                    "error": result.error_message if not result.success else None,
                    "provider": result.provider_used,
                    "model": result.model_used,
                    "response_time": result.response_time
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "provider": None,
                    "model": None,
                    "response_time": 0.0
                }

        # Create semaphore for concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def limited_process(req_data):
            async with semaphore:
                return await process_single(req_data)

        # Process all requests
        tasks = [limited_process(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "success": False,
                    "error": str(result),
                    "provider": None,
                    "model": None,
                    "response_time": 0.0
                })
            else:
                final_results.append(result)

        return final_results


# Global instance
batch_processor = None


def get_batch_processor(engine):
    """Get or create batch processor instance"""
    global batch_processor
    if batch_processor is None:
        batch_processor = BatchProcessor(engine)
    return batch_processor
