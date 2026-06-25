import re
import json
import os
import time
import threading
from typing import Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StressTestMixin:
    """Stress testing and priority optimization methods."""

    def stress_test_providers(self, test_iterations: int = 3, ask_for_priority_change: bool = True, use_threading: bool = True) -> Dict[str, Any]:
        """
        Run stress test on all providers and optionally ask user for priority changes
        Enhanced with threading for faster execution
        """
        enabled_providers = {name: config for name, config in self.providers.items() if config.get('enabled', True)}

        print(f"🧪 Starting stress test on {len(enabled_providers)} enabled providers...")
        print(f"📝 Test iterations: {test_iterations}")
        print(f"⚡ Threading enabled: {use_threading}")
        print()

        test_prompt = "Hello! Please respond with exactly: 'Test successful - AI Engine v3.0 working!'"
        results = {}

        if use_threading and len(enabled_providers) > 1:
            # Use threading for faster stress testing
            results = self._stress_test_threaded(enabled_providers, test_iterations, test_prompt)
        else:
            # Sequential testing (original method)
            results = self._stress_test_sequential(enabled_providers, test_iterations, test_prompt)

        # Calculate overall stats
        total_providers = len(results)
        passed_providers = sum(1 for r in results.values() if r['passed'])
        pass_rate = (passed_providers / total_providers) * 100 if total_providers > 0 else 0

        print(f"\n📊 STRESS TEST SUMMARY:")
        print(f"Providers tested: {total_providers}")
        print(f"Providers passed: {passed_providers}")
        print(f"Overall pass rate: {pass_rate:.1f}%")

        # Show detailed results
        print(f"\n📋 DETAILED RESULTS:")
        print(f"{'Provider':<15} {'Status':<6} {'Success Rate':<12} {'Avg Time':<10} {'Priority'}")
        print("-" * 65)

        # Sort by current priority for display
        sorted_results = sorted(results.items(), key=lambda x: self.providers.get(x[0], {}).get('priority', 999))

        for provider_name, result in sorted_results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            success_rate = f"{result['success_rate']:.1f}%"
            avg_time = f"{result['avg_response_time']:.2f}s"
            priority = self.providers.get(provider_name, {}).get('priority', '?')

            print(f"{provider_name:<15} {status:<6} {success_rate:<12} {avg_time:<10} {priority}")

        # Ask user about priority changes if requested
        if ask_for_priority_change and passed_providers > 0:
            print(f"\n🔄 Priority Optimization Available")
            print(f"Current priority ranking vs. performance-based ranking could be optimized.")
            print(f"This will update both in-memory priorities and save changes to config.py.")

            response = input("Enter 'y' to optimize priorities or 'n' to keep current: ").lower().strip()

            if response == 'y':
                self._optimize_priorities(results)
            else:
                print("📌 Keeping current priorities")

        return results

    def _stress_test_sequential(self, providers: Dict, test_iterations: int, test_prompt: str) -> Dict[str, Any]:
        """Sequential stress testing (original method)"""
        results = {}

        for provider_name, provider_config in providers.items():
            print(f"Testing {provider_name}...", end=" ")

            provider_results = {
                'provider': provider_name,
                'total_tests': test_iterations,
                'successful_tests': 0,
                'failed_tests': 0,
                'response_times': [],
                'errors': []
            }

            for i in range(test_iterations):
                start_time = time.time()
                result = self._make_request(
                    provider_name,
                    provider_config,
                    [{"role": "user", "content": test_prompt}]
                )
                response_time = time.time() - start_time

                if result.success:
                    provider_results['successful_tests'] += 1
                    provider_results['response_times'].append(response_time)
                else:
                    provider_results['failed_tests'] += 1
                    provider_results['errors'].append({
                        'iteration': i + 1,
                        'error': result.error_message,
                        'error_type': result.error_type
                    })

            # Calculate metrics
            success_rate = (provider_results['successful_tests'] / test_iterations) * 100
            avg_response_time = sum(provider_results['response_times']) / len(provider_results['response_times']) if provider_results['response_times'] else 0

            provider_results.update({
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'min_response_time': min(provider_results['response_times']) if provider_results['response_times'] else 0,
                'max_response_time': max(provider_results['response_times']) if provider_results['response_times'] else 0,
                'passed': success_rate >= 75  # 75% success threshold
            })

            results[provider_name] = provider_results

            status = "✅ PASS" if provider_results['passed'] else "❌ FAIL"
            print(f"{status} ({success_rate:.1f}%, {avg_response_time:.2f}s)")

        return results

    def _stress_test_threaded(self, providers: Dict, test_iterations: int, test_prompt: str) -> Dict[str, Any]:
        """Threaded stress testing for faster execution"""
        results = {}
        max_workers = min(len(providers), 8)  # Limit concurrent tests

        print(f"⚡ Running threaded stress test with {max_workers} workers...")

        def test_provider(provider_item):
            provider_name, provider_config = provider_item
            provider_results = {
                'provider': provider_name,
                'total_tests': test_iterations,
                'successful_tests': 0,
                'failed_tests': 0,
                'response_times': [],
                'errors': []
            }

            print(f"🧪 Testing {provider_name}...")

            for i in range(test_iterations):
                start_time = time.time()
                try:
                    result = self._make_request(
                        provider_name,
                        provider_config,
                        [{"role": "user", "content": test_prompt}]
                    )
                    response_time = time.time() - start_time

                    if result.success:
                        provider_results['successful_tests'] += 1
                        provider_results['response_times'].append(response_time)
                    else:
                        provider_results['failed_tests'] += 1
                        provider_results['errors'].append({
                            'iteration': i + 1,
                            'error': result.error_message,
                            'error_type': getattr(result, 'error_type', 'unknown')
                        })
                except Exception as e:
                    response_time = time.time() - start_time
                    provider_results['failed_tests'] += 1
                    provider_results['errors'].append({
                        'iteration': i + 1,
                        'error': str(e),
                        'error_type': 'exception'
                    })

            # Calculate metrics
            success_rate = (provider_results['successful_tests'] / test_iterations) * 100
            avg_response_time = sum(provider_results['response_times']) / len(provider_results['response_times']) if provider_results['response_times'] else 0

            provider_results.update({
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'min_response_time': min(provider_results['response_times']) if provider_results['response_times'] else 0,
                'max_response_time': max(provider_results['response_times']) if provider_results['response_times'] else 0,
                'passed': success_rate >= 75  # 75% success threshold
            })

            status = "✅ PASS" if provider_results['passed'] else "❌ FAIL"
            print(f"✅ {provider_name}: {status} ({success_rate:.1f}%, {avg_response_time:.2f}s)")

            return provider_name, provider_results

        # Execute tests in parallel
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_provider = {
                executor.submit(test_provider, provider_item): provider_item[0]
                for provider_item in providers.items()
            }

            for future in concurrent.futures.as_completed(future_to_provider):
                try:
                    provider_name, provider_results = future.result(timeout=60)  # 60 second timeout per provider
                    results[provider_name] = provider_results
                except Exception as e:
                    provider_name = future_to_provider[future]
                    print(f"❌ {provider_name} test failed with exception: {e}")
                    # Create a failed result
                    results[provider_name] = {
                        'provider': provider_name,
                        'total_tests': test_iterations,
                        'successful_tests': 0,
                        'failed_tests': test_iterations,
                        'response_times': [],
                        'errors': [{'iteration': 'all', 'error': str(e), 'error_type': 'timeout_exception'}],
                        'success_rate': 0,
                        'avg_response_time': 0,
                        'min_response_time': 0,
                        'max_response_time': 0,
                        'passed': False
                    }

        total_time = time.time() - start_time
        print(f"⏱️ Threaded stress test completed in {total_time:.2f}s")

        return results

    def _optimize_priorities(self, test_results: Dict[str, Any]):
        """Optimize provider priorities based on test results"""
        # Sort providers by performance score
        provider_scores = []

        for provider_name, result in test_results.items():
            if result['passed']:
                # Calculate performance score (success rate 60%, speed 40%)
                success_weight = result['success_rate'] * 0.6
                speed_score = max(0, 100 - (result['avg_response_time'] * 20))  # Penalize slow responses
                speed_weight = speed_score * 0.4

                total_score = success_weight + speed_weight
                provider_scores.append((provider_name, total_score, result['avg_response_time']))

        # Sort by score (higher is better)
        provider_scores.sort(key=lambda x: x[1], reverse=True)

        print(f"\n🏆 OPTIMIZED PRIORITY RANKING:")
        print(f"{'Rank':<4} {'Provider':<15} {'Score':<6} {'Time':<7} {'Old Pri':<7} {'New Pri'}")
        print("-" * 60)

        # Update priorities and prepare changes to save
        priority_changes = {}
        for i, (provider_name, score, avg_time) in enumerate(provider_scores, 1):
            old_priority = self.providers[provider_name].get('priority', 999)
            new_priority = i

            # Update in-memory configuration
            self.providers[provider_name]['priority'] = new_priority

            # Track changes for file saving
            if old_priority != new_priority:
                priority_changes[provider_name] = new_priority

            print(f"{i:2d}   {provider_name:15} {score:5.1f}  {avg_time:5.2f}s  {old_priority:5d}   {new_priority:5d}")

        # Save changes to config.py file
        if priority_changes:
            try:
                self._save_priority_changes_to_config(priority_changes)
                print(f"\n✅ Priority changes saved to config.py")
                print(f"📝 Updated {len(priority_changes)} provider priorities")
            except Exception as e:
                print(f"\n⚠️ Failed to save priority changes to config.py: {e}")
                print(f"📝 In-memory priorities updated, but file changes not saved")
        else:
            print(f"\n📌 No priority changes needed")

    def _save_priority_changes_to_config(self, priority_changes: Dict[str, int]):
        """Save priority changes back to config.py file"""
        try:
            # Read the current config file
            with open('config.py', 'r', encoding='utf-8') as f:
                config_content = f.read()

            # Apply each priority change
            updated_content = config_content

            for provider_name, new_priority in priority_changes.items():
                # Create a pattern to find and replace the priority line for this provider
                # Look for the provider section and the priority field within it
                provider_pattern = rf'"{provider_name}":\s*\{{([^}}]*)"priority":\s*\d+([^}}]*)}}'

                def replace_priority(match):
                    before_priority = match.group(1)
                    after_priority = match.group(2)
                    return f'"{provider_name}": {{{before_priority}"priority": {new_priority}{after_priority}}}'

                updated_content = re.sub(provider_pattern, replace_priority, updated_content, flags=re.DOTALL)

            # Write the updated config back to file
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"📁 Config file updated with new priorities")

        except Exception as e:
            raise Exception(f"Failed to update config.py: {str(e)}")
