#!/usr/bin/env python3
"""
Stress Test Scenarios for Trading System
Defines different load testing scenarios
"""

import subprocess
import time
from datetime import datetime
from typing import Dict, List


class StressTestScenarios:
    """Different stress test scenarios for the trading system"""
    
    def __init__(self, host: str = "http://localhost:8000"):
        self.host = host
        self.results = {}
    
    def scenario_baseline(self):
        """
        Baseline Performance Test
        - 10 users
        - 2 users/second spawn rate
        - 5 minute duration
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 1: BASELINE PERFORMANCE TEST")
        print("="*70)
        print("Users: 10")
        print("Spawn Rate: 2/second")
        print("Duration: 5 minutes")
        print("="*70 + "\n")
        
        return self._run_test(
            users=10,
            spawn_rate=2,
            run_time="5m",
            scenario_name="baseline"
        )
    
    def scenario_normal_load(self):
        """
        Normal Load Test
        - 50 users
        - 5 users/second spawn rate
        - 10 minute duration
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 2: NORMAL LOAD TEST")
        print("="*70)
        print("Users: 50")
        print("Spawn Rate: 5/second")
        print("Duration: 10 minutes")
        print("="*70 + "\n")
        
        return self._run_test(
            users=50,
            spawn_rate=5,
            run_time="10m",
            scenario_name="normal_load"
        )
    
    def scenario_peak_load(self):
        """
        Peak Load Test
        - 200 users
        - 10 users/second spawn rate
        - 15 minute duration
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 3: PEAK LOAD TEST")
        print("="*70)
        print("Users: 200")
        print("Spawn Rate: 10/second")
        print("Duration: 15 minutes")
        print("="*70 + "\n")
        
        return self._run_test(
            users=200,
            spawn_rate=10,
            run_time="15m",
            scenario_name="peak_load"
        )
    
    def scenario_stress_test(self):
        """
        Stress Test - Push system to limits
        - 500 users
        - 20 users/second spawn rate
        - 20 minute duration
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 4: STRESS TEST")
        print("="*70)
        print("Users: 500")
        print("Spawn Rate: 20/second")
        print("Duration: 20 minutes")
        print("="*70 + "\n")
        
        return self._run_test(
            users=500,
            spawn_rate=20,
            run_time="20m",
            scenario_name="stress_test"
        )
    
    def scenario_spike_test(self):
        """
        Spike Test - Sudden load increase
        - Start with 10 users
        - Spike to 300 users
        - 50 users/second spawn rate (sudden spike)
        - 10 minute duration
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 5: SPIKE TEST")
        print("="*70)
        print("Users: 10 → 300 (sudden spike)")
        print("Spawn Rate: 50/second")
        print("Duration: 10 minutes")
        print("="*70 + "\n")
        
        return self._run_test(
            users=300,
            spawn_rate=50,
            run_time="10m",
            scenario_name="spike_test"
        )
    
    def scenario_endurance_test(self):
        """
        Endurance Test - Sustained load
        - 100 users
        - 5 users/second spawn rate
        - 60 minute duration (1 hour)
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 6: ENDURANCE TEST")
        print("="*70)
        print("Users: 100")
        print("Spawn Rate: 5/second")
        print("Duration: 60 minutes (1 hour)")
        print("="*70 + "\n")
        
        return self._run_test(
            users=100,
            spawn_rate=5,
            run_time="60m",
            scenario_name="endurance_test"
        )
    
    def scenario_high_frequency_trading(self):
        """
        High Frequency Trading Test
        - 50 HFT users (rapid requests)
        - 10 users/second spawn rate
        - 10 minute duration
        """
        print("\n" + "="*70)
        print("📊 SCENARIO 7: HIGH FREQUENCY TRADING TEST")
        print("="*70)
        print("Users: 50 (HFT pattern)")
        print("Spawn Rate: 10/second")
        print("Duration: 10 minutes")
        print("="*70 + "\n")
        
        return self._run_test(
            users=50,
            spawn_rate=10,
            run_time="10m",
            scenario_name="hft_test",
            user_class="HighFrequencyTrader"
        )
    
    def _run_test(
        self,
        users: int,
        spawn_rate: int,
        run_time: str,
        scenario_name: str,
        user_class: str = "TradingSystemUser"
    ) -> Dict:
        """Run a load test with specified parameters"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_prefix = f"results/{scenario_name}_{timestamp}"
        html_report = f"results/{scenario_name}_{timestamp}.html"
        
        cmd = [
            "locust",
            "-f", "locustfile.py",
            "--headless",
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", run_time,
            "--host", self.host,
            "--csv", csv_prefix,
            "--html", html_report,
            "--only-summary"
        ]
        
        if user_class != "TradingSystemUser":
            cmd.extend(["--class-name", user_class])
        
        print(f"🚀 Starting test: {scenario_name}")
        print(f"Command: {' '.join(cmd)}\n")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour max
            )
            
            duration = time.time() - start_time
            
            self.results[scenario_name] = {
                "success": result.returncode == 0,
                "duration_seconds": duration,
                "csv_prefix": csv_prefix,
                "html_report": html_report,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                print(f"✅ Test completed successfully in {duration:.2f}s")
                print(f"📊 Results: {html_report}")
            else:
                print(f"❌ Test failed with code {result.returncode}")
                print(f"Error: {result.stderr}")
            
            return self.results[scenario_name]
            
        except subprocess.TimeoutExpired:
            print(f"⏱️  Test timed out after 2 hours")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            return {"success": False, "error": str(e)}
    
    def run_all_scenarios(self, scenarios: List[str] = None):
        """Run all or selected scenarios"""
        
        all_scenarios = {
            "baseline": self.scenario_baseline,
            "normal_load": self.scenario_normal_load,
            "peak_load": self.scenario_peak_load,
            "stress_test": self.scenario_stress_test,
            "spike_test": self.scenario_spike_test,
            "endurance_test": self.scenario_endurance_test,
            "hft_test": self.scenario_high_frequency_trading
        }
        
        scenarios_to_run = scenarios if scenarios else all_scenarios.keys()
        
        print("\n" + "="*70)
        print("🎯 STRESS TEST SUITE")
        print("="*70)
        print(f"Host: {self.host}")
        print(f"Scenarios: {', '.join(scenarios_to_run)}")
        print(f"Start Time: {datetime.now().isoformat()}")
        print("="*70 + "\n")
        
        for scenario in scenarios_to_run:
            if scenario in all_scenarios:
                all_scenarios[scenario]()
                time.sleep(30)  # 30 second cooldown between tests
            else:
                print(f"⚠️  Unknown scenario: {scenario}")
        
        self._print_summary()
    
    def _print_summary(self):
        """Print summary of all test results"""
        print("\n" + "="*70)
        print("📊 STRESS TEST SUITE - SUMMARY")
        print("="*70)
        
        for scenario, result in self.results.items():
            status = "✅ PASS" if result.get("success") else "❌ FAIL"
            duration = result.get("duration_seconds", 0)
            print(f"\n{scenario}:")
            print(f"  Status: {status}")
            print(f"  Duration: {duration:.2f}s")
            if "html_report" in result:
                print(f"  Report: {result['html_report']}")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r.get("success"))
        
        print(f"\n{'='*70}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Pass Rate: {(passed_tests / total_tests * 100) if total_tests > 0 else 0:.1f}%")
        print("="*70 + "\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run stress test scenarios")
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Target host URL"
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        help="Specific scenarios to run (default: all)"
    )
    
    args = parser.parse_args()
    
    # Create results directory
    subprocess.run(["mkdir", "-p", "results"], check=True)
    
    # Run tests
    suite = StressTestScenarios(host=args.host)
    suite.run_all_scenarios(scenarios=args.scenarios)


if __name__ == "__main__":
    main()
