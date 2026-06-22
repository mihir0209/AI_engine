"""
Request queue for handling rate-limited providers
Queues requests when rate limited and processes when available
"""
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from collections import deque


@dataclass
class QueuedRequest:
    """A queued request"""
    id: str
    provider: str
    func: Callable
    args: tuple
    kwargs: dict
    created_at: float = field(default_factory=time.time)
    callback: Optional[Callable] = None


class RequestQueue:
    """Queue for rate-limited requests"""
    
    def __init__(self, max_queue_size: int = 100, max_wait_time: int = 60):
        self.max_queue_size = max_queue_size
        self.max_wait_time = max_wait_time
        self.queues: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._processing = False
    
    def enqueue(self, provider: str, func: Callable, args: tuple = (), kwargs: dict = None) -> str:
        """Add a request to the queue"""
        import uuid
        request_id = str(uuid.uuid4())[:8]
        
        with self._lock:
            if provider not in self.queues:
                self.queues[provider] = deque(maxlen=self.max_queue_size)
            
            request = QueuedRequest(
                id=request_id,
                provider=provider,
                func=func,
                args=args,
                kwargs=kwargs or {}
            )
            
            self.queues[provider].append(request)
            return request_id
    
    def process_queue(self, provider: str, max_requests: int = 1) -> List[Any]:
        """Process queued requests for a provider"""
        results = []
        
        with self._lock:
            if provider not in self.queues or not self.queues[provider]:
                return results
            
            # Process up to max_requests
            for _ in range(min(max_requests, len(self.queues[provider]))):
                request = self.queues[provider].popleft()
                
                # Check if request has expired
                if time.time() - request.created_at > self.max_wait_time:
                    continue
                
                try:
                    result = request.func(*request.args, **request.kwargs)
                    results.append({"id": request.id, "result": result, "success": True})
                except Exception as e:
                    results.append({"id": request.id, "error": str(e), "success": False})
        
        return results
    
    def get_queue_size(self, provider: str = None) -> int:
        """Get queue size"""
        with self._lock:
            if provider:
                return len(self.queues.get(provider, deque()))
            return sum(len(q) for q in self.queues.values())
    
    def clear_queue(self, provider: str = None):
        """Clear queue for a provider or all providers"""
        with self._lock:
            if provider:
                self.queues.pop(provider, None)
            else:
                self.queues.clear()
    
    def get_stats(self) -> Dict:
        """Get queue statistics"""
        with self._lock:
            return {
                "total_queued": sum(len(q) for q in self.queues.values()),
                "by_provider": {name: len(q) for name, q in self.queues.items()},
                "max_queue_size": self.max_queue_size,
                "max_wait_time": self.max_wait_time
            }


# Global instance
request_queue = RequestQueue()
