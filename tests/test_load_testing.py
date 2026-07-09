"""Tests for load testing utilities.

Server endpoint integration coverage lives in tests/features/.
"""
import time


def test_load_tester_init():
    from core.load_test import LoadTester
    tester = LoadTester()
    assert len(tester.results) == 0


def test_load_tester_run():
    from core.load_test import LoadTester
    tester = LoadTester()

    def mock_func():
        time.sleep(0.001)
        return "ok"

    result = tester.run_load_test(
        test_name="Quick Test",
        func=mock_func,
        num_requests=10,
        concurrent_users=2
    )

    assert result.total_requests == 10
    assert result.successful_requests == 10
    assert result.failed_requests == 0
    assert result.error_rate == 0


def test_load_tester_with_errors():
    from core.load_test import LoadTester
    tester = LoadTester()

    call_count = 0
    def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise ValueError("Even calls fail")
        return "ok"

    result = tester.run_load_test(
        test_name="Error Test",
        func=failing_func,
        num_requests=10,
        concurrent_users=1
    )

    assert result.failed_requests > 0
    assert result.error_rate > 0


def test_load_tester_summary():
    from core.load_test import LoadTester
    tester = LoadTester()

    def mock_func():
        return "ok"

    tester.run_load_test("Test 1", mock_func, num_requests=5, concurrent_users=1)
    tester.run_load_test("Test 2", mock_func, num_requests=5, concurrent_users=1)

    summary = tester.get_summary()
    assert summary["total_tests"] == 2
    assert summary["total_requests"] == 10


def test_load_tester_print(capsys):
    from core.load_test import LoadTester
    tester = LoadTester()

    def mock_func():
        return "ok"

    result = tester.run_load_test("Print Test", mock_func, num_requests=5, concurrent_users=1)
    tester.print_results(result)

    captured = capsys.readouterr()
    assert "Print Test" in captured.out
    assert "Total Requests" in captured.out