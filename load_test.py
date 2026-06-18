"""
Load testing framework for AI Engine
Simulates concurrent users and measures performance
"""
import time
import statistics
from typing import Dict, List, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import json


@dataclass
class LoadTestResult:
    """Result of a load test"""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    total_duration: float
    errors: List[str] = field(default_factory=list)


class LoadTester:
    """Load testing framework"""

    def __init__(self):
        self.results: List[LoadTestResult] = []

    def run_load_test(
        self,
        test_name: str,
        func: Callable,
        num_requests: int = 100,
        concurrent_users: int = 10,
        timeout: float = 300
    ) -> LoadTestResult:
        """Run a load test with concurrent requests"""
        response_times = []
        errors = []
        start_time = time.time()

        def make_request():
            try:
                req_start = time.time()
                result = func()
                req_time = time.time() - req_start
                return req_time, None
            except Exception as e:
                return 0, str(e)

        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]

            for future in as_completed(futures, timeout=timeout):
                try:
                    req_time, error = future.result(timeout=10)
                    if error:
                        errors.append(error)
                    else:
                        response_times.append(req_time)
                except Exception as e:
                    errors.append(str(e))

        total_duration = time.time() - start_time

        # Calculate statistics
        sorted_times = sorted(response_times) if response_times else [0]

        result = LoadTestResult(
            test_name=test_name,
            total_requests=num_requests,
            successful_requests=len(response_times),
            failed_requests=len(errors),
            avg_response_time=statistics.mean(sorted_times) if sorted_times else 0,
            min_response_time=min(sorted_times) if sorted_times else 0,
            max_response_time=max(sorted_times) if sorted_times else 0,
            p50_response_time=sorted_times[len(sorted_times) // 2] if sorted_times else 0,
            p95_response_time=sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0,
            p99_response_time=sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0,
            requests_per_second=num_requests / total_duration if total_duration > 0 else 0,
            error_rate=len(errors) / num_requests * 100 if num_requests > 0 else 0,
            total_duration=total_duration,
            errors=errors[:10]  # Keep first 10 errors
        )

        self.results.append(result)
        return result

    def print_results(self, result: LoadTestResult):
        """Print load test results"""
        print(f"\n{'='*60}")
        print(f"Load Test: {result.test_name}")
        print(f"{'='*60}")
        print(f"Total Requests:      {result.total_requests}")
        print(f"Successful:          {result.successful_requests}")
        print(f"Failed:              {result.failed_requests}")
        print(f"Error Rate:          {result.error_rate:.2f}%")
        print(f"Duration:            {result.total_duration:.2f}s")
        print(f"Requests/sec:        {result.requests_per_second:.2f}")
        print(f"\nResponse Times:")
        print(f"  Average:           {result.avg_response_time*1000:.2f}ms")
        print(f"  Min:               {result.min_response_time*1000:.2f}ms")
        print(f"  Max:               {result.max_response_time*1000:.2f}ms")
        print(f"  P50:               {result.p50_response_time*1000:.2f}ms")
        print(f"  P95:               {result.p95_response_time*1000:.2f}ms")
        print(f"  P99:               {result.p99_response_time*1000:.2f}ms")

        if result.errors:
            print(f"\nSample Errors:")
            for error in result.errors[:5]:
                print(f"  - {error[:100]}")

        print(f"{'='*60}\n")

    def get_summary(self) -> Dict:
        """Get summary of all test results"""
        if not self.results:
            return {}

        return {
            "total_tests": len(self.results),
            "total_requests": sum(r.total_requests for r in self.results),
            "overall_success_rate": sum(r.successful_requests for r in self.results) /
                                    sum(r.total_requests for r in self.results) * 100,
            "avg_response_time": statistics.mean([r.avg_response_time for r in self.results]),
            "tests": [
                {
                    "name": r.test_name,
                    "requests": r.total_requests,
                    "success_rate": (r.successful_requests / r.total_requests * 100) if r.total_requests > 0 else 0,
                    "rps": r.requests_per_second,
                    "avg_ms": r.avg_response_time * 1000
                }
                for r in self.results
            ]
        }

    def export_results(self, filepath: str):
        """Export results to JSON"""
        summary = self.get_summary()
        with open(filepath, "w") as f:
            json.dump(summary, f, indent=2)


# Example load test functions for AI Engine

def mock_api_request():
    """Mock API request for testing"""
    time.sleep(0.01)  # Simulate network delay
    return {"status": "ok"}


def mock_chat_request():
    """Mock chat request"""
    time.sleep(0.05)  # Simulate AI processing
    return {"content": "Response"}


def run_quick_load_test():
    """Run a quick load test"""
    tester = LoadTester()

    # Test API endpoints
    result = tester.run_load_test(
        test_name="API Health Check",
        func=mock_api_request,
        num_requests=50,
        concurrent_users=5
    )
    tester.print_results(result)

    return tester


if __name__ == "__main__":
    tester = run_quick_load_test()
    print("\nSummary:", json.dumps(tester.get_summary(), indent=2))
