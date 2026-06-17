"""
Infrastructure utilities for AI Engine
Circuit breaker, retry logic, and enhanced health checks
"""
import time
import random
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
import threading


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    name: str
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3
    
    # Internal state
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False
            
            if self.state == CircuitState.HALF_OPEN:
                # Allow limited calls to test recovery
                return self.success_count < self.half_open_max_calls
            
            return False
    
    def record_success(self):
        """Record a successful call"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0  # Reset on success
    
    def record_failure(self):
        """Record a failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery, back to open
                self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state"""
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.OPEN:
            self.success_count = 0
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change
        }
    
    def reset(self):
        """Reset circuit breaker to closed state"""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)


class RetryHandler:
    """Retry logic with exponential backoff"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add jitter (±25%)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    time.sleep(delay)
        
        raise last_exception


# Circuit breaker registry
circuit_breakers: Dict[str, CircuitBreaker] = {}
retry_handlers: Dict[str, RetryHandler] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker"""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
    return circuit_breakers[name]


def get_retry_handler(name: str = "default", **kwargs) -> RetryHandler:
    """Get or create a retry handler"""
    if name not in retry_handlers:
        retry_handlers[name] = RetryHandler(**kwargs)
    return retry_handlers[name]


def circuit_protected(name: str = None):
    """Decorator to add circuit breaker protection"""
    def decorator(func):
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            cb = get_circuit_breaker(breaker_name)
            
            if not cb.can_execute():
                raise Exception(f"Circuit breaker {breaker_name} is OPEN")
            
            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                raise
        
        wrapper.circuit_breaker = get_circuit_breaker(breaker_name)
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, **retry_kwargs):
    """Decorator to add retry logic"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rh = get_retry_handler(func.__name__, max_retries=max_retries, **retry_kwargs)
            return rh.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


class HealthChecker:
    """Enhanced health checking"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, Dict] = {}
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func
    
    def run_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.health_checks.items():
            try:
                result = check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "timestamp": datetime.now().isoformat()
                }
                if not result:
                    overall_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                overall_healthy = False
        
        self.last_results = results
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "checks": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_last_results(self) -> Dict:
        """Get last health check results"""
        return self.last_results


# Global instances
health_checker = HealthChecker()


# Register default health checks
def check_database():
    """Check database connectivity"""
    try:
        from chat_module.db import ChatDB
        db = ChatDB()
        # Simple query to test connection
        conn = db.get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception:
        return False


def check_providers():
    """Check if any providers are available"""
    from config import AI_CONFIGS
    enabled = [name for name, config in AI_CONFIGS.items() if config.get('enabled', True)]
    return len(enabled) > 0


health_checker.register_check("database", check_database)
health_checker.register_check("providers", check_providers)
