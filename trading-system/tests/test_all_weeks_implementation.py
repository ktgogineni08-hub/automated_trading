#!/usr/bin/env python3
"""
Comprehensive Test Suite for All 4 Weeks Implementation
Tests all deliverables from Week 1-4
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class WeeklyImplementationTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results = {
            'week1': {'passed': 0, 'failed': 0, 'tests': []},
            'week2': {'passed': 0, 'failed': 0, 'tests': []},
            'week3': {'passed': 0, 'failed': 0, 'tests': []},
            'week4': {'passed': 0, 'failed': 0, 'tests': []}
        }

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Color.BLUE}{'='*80}{Color.RESET}")
        print(f"{Color.BLUE}{text.center(80)}{Color.RESET}")
        print(f"{Color.BLUE}{'='*80}{Color.RESET}\n")

    def print_test(self, test_name: str, passed: bool, details: str = ""):
        """Print test result"""
        status = f"{Color.GREEN}✓ PASS{Color.RESET}" if passed else f"{Color.RED}✗ FAIL{Color.RESET}"
        print(f"{status} - {test_name}")
        if details:
            print(f"        {details}")

    def record_result(self, week: str, test_name: str, passed: bool, details: str = ""):
        """Record test result"""
        if passed:
            self.results[week]['passed'] += 1
        else:
            self.results[week]['failed'] += 1

        self.results[week]['tests'].append({
            'name': test_name,
            'passed': passed,
            'details': details
        })

        self.print_test(test_name, passed, details)

    # ========================================================================
    # WEEK 1 TESTS: Advanced Features & Optimizations
    # ========================================================================

    def test_week1_advanced_features(self):
        """Test Week 1 deliverables"""
        self.print_header("WEEK 1: ADVANCED FEATURES & OPTIMIZATIONS")

        # Test 1: Check documentation exists
        week1_doc = self.project_root / "docs" / "WEEK1_DEPLOYMENT_COMPLETION.md"
        self.record_result(
            'week1',
            'Week 1 completion documentation exists',
            week1_doc.exists(),
            f"File: {week1_doc}" if week1_doc.exists() else "File not found"
        )

        # Test 2: Check query optimizer exists
        query_opt = self.project_root / "infrastructure" / "query_optimizer.py"
        self.record_result(
            'week1',
            'Query optimizer module exists',
            query_opt.exists(),
            f"File: {query_opt}"
        )

        # Test 3: Validate query optimizer syntax
        if query_opt.exists():
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'py_compile', str(query_opt)],
                    capture_output=True,
                    cwd=self.project_root
                )
                self.record_result(
                    'week1',
                    'Query optimizer syntax is valid',
                    result.returncode == 0,
                    "Python syntax check passed"
                )
            except Exception as e:
                self.record_result('week1', 'Query optimizer syntax check', False, str(e))

        # Test 4: Check advanced risk analytics
        risk_analytics = self.project_root / "infrastructure" / "advanced_risk_analytics.py"
        self.record_result(
            'week1',
            'Advanced risk analytics module exists',
            risk_analytics.exists(),
            f"File: {risk_analytics}"
        )

        # Test 5: Check performance monitor
        perf_monitor = self.project_root / "infrastructure" / "performance_monitor.py"
        self.record_result(
            'week1',
            'Performance monitor module exists',
            perf_monitor.exists(),
            f"File: {perf_monitor}"
        )

    # ========================================================================
    # WEEK 2 TESTS: Deployment Automation
    # ========================================================================

    def test_week2_deployment_automation(self):
        """Test Week 2 deliverables"""
        self.print_header("WEEK 2: DEPLOYMENT AUTOMATION")

        # Test 1: Check documentation
        week2_doc = self.project_root / "docs" / "WEEK2_DEPLOYMENT_COMPLETION.md"
        self.record_result(
            'week2',
            'Week 2 completion documentation exists',
            week2_doc.exists()
        )

        # Test 2: Check Dockerfile
        dockerfile = self.project_root / "Dockerfile"
        self.record_result(
            'week2',
            'Dockerfile exists',
            dockerfile.exists()
        )

        # Validate Dockerfile content
        if dockerfile.exists():
            with open(dockerfile) as f:
                content = f.read()
                has_multistage = 'FROM' in content and 'as builder' in content
                self.record_result(
                    'week2',
                    'Dockerfile uses multi-stage build',
                    has_multistage,
                    "Multi-stage build pattern detected" if has_multistage else "Single stage build"
                )

        # Test 3: Check docker-compose.yml
        compose = self.project_root / "docker-compose.yml"
        self.record_result(
            'week2',
            'docker-compose.yml exists',
            compose.exists()
        )

        # Validate docker-compose content
        if compose.exists():
            try:
                with open(compose) as f:
                    content = f.read()
                    services = ['postgres', 'redis', 'trading-system']
                    has_services = all(svc in content for svc in services)
                    self.record_result(
                        'week2',
                        'docker-compose has required services',
                        has_services,
                        f"Services: {', '.join(services)}"
                    )
            except Exception as e:
                self.record_result('week2', 'docker-compose validation', False, str(e))

        # Test 4: Check deployment scripts
        deploy_script = self.project_root / "scripts" / "deploy.sh"
        self.record_result(
            'week2',
            'Deployment script exists',
            deploy_script.exists() and os.access(deploy_script, os.X_OK),
            f"Executable: {os.access(deploy_script, os.X_OK)}" if deploy_script.exists() else "Not found"
        )

        # Test 5: Check health check module
        health_check = self.project_root / "infrastructure" / "health_check.py"
        self.record_result(
            'week2',
            'Health check module exists',
            health_check.exists()
        )

        # Validate health check syntax
        if health_check.exists():
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'py_compile', str(health_check)],
                    capture_output=True,
                    cwd=self.project_root
                )
                self.record_result(
                    'week2',
                    'Health check module syntax is valid',
                    result.returncode == 0
                )
            except Exception as e:
                self.record_result('week2', 'Health check syntax', False, str(e))

    # ========================================================================
    # WEEK 3 TESTS: Performance Tuning & High Availability
    # ========================================================================

    def test_week3_performance_ha(self):
        """Test Week 3 deliverables"""
        self.print_header("WEEK 3: PERFORMANCE TUNING & HIGH AVAILABILITY")

        # Test 1: Check documentation
        week3_doc = self.project_root / "docs" / "WEEK3_PERFORMANCE_HA_COMPLETION.md"
        self.record_result(
            'week3',
            'Week 3 completion documentation exists',
            week3_doc.exists()
        )

        # Test 2: Verify query optimizer enhancements
        query_opt = self.project_root / "infrastructure" / "query_optimizer.py"
        if query_opt.exists():
            with open(query_opt) as f:
                content = f.read()
                has_caching = 'cache' in content.lower()
                has_slow_query = 'slow_query' in content.lower()

                self.record_result(
                    'week3',
                    'Query optimizer has caching functionality',
                    has_caching
                )

                self.record_result(
                    'week3',
                    'Query optimizer tracks slow queries',
                    has_slow_query
                )

        # Test 3: Check load testing infrastructure
        load_test_exists = (
            (self.project_root / "tests" / "performance" / "locustfile.py").exists() or
            (self.project_root / "scripts" / "run_load_tests.sh").exists()
        )
        self.record_result(
            'week3',
            'Load testing infrastructure exists',
            load_test_exists
        )

        # Test 4: Check for HA components documentation
        if week3_doc.exists():
            with open(week3_doc) as f:
                content = f.read()
                has_replication = 'replication' in content.lower()
                has_sentinel = 'sentinel' in content.lower()

                self.record_result(
                    'week3',
                    'HA documentation covers replication',
                    has_replication
                )

                self.record_result(
                    'week3',
                    'HA documentation covers Redis Sentinel',
                    has_sentinel
                )

    # ========================================================================
    # WEEK 4 TESTS: Production Go-Live & Operational Excellence
    # ========================================================================

    def test_week4_operational_excellence(self):
        """Test Week 4 deliverables"""
        self.print_header("WEEK 4: PRODUCTION GO-LIVE & OPERATIONAL EXCELLENCE")

        # Test 1: Check all documentation files
        docs_to_check = [
            ('Production deployment checklist', 'PRODUCTION_DEPLOYMENT_CHECKLIST.md'),
            ('Incident response runbooks', 'INCIDENT_RESPONSE_RUNBOOKS.md'),
            ('Backup & recovery guide', 'BACKUP_RECOVERY.md'),
            ('Disaster recovery plan', 'DISASTER_RECOVERY_PLAN.md'),
            ('Monitoring & alerting playbook', 'MONITORING_ALERTING_PLAYBOOK.md'),
            ('Team training guide', 'TEAM_TRAINING_GUIDE.md'),
            ('Continuous improvement framework', 'CONTINUOUS_IMPROVEMENT_FRAMEWORK.md'),
            ('Week 4 completion report', 'WEEK4_PRODUCTION_GOLIVE_COMPLETION.md')
        ]

        for name, filename in docs_to_check:
            doc_path = self.project_root / "docs" / filename
            self.record_result(
                'week4',
                f'{name} exists',
                doc_path.exists(),
                f"File size: {doc_path.stat().st_size / 1024:.1f} KB" if doc_path.exists() else "Not found"
            )

        # Test 2: Check backup scripts
        backup_scripts = [
            ('Backup script', 'backup.sh'),
            ('Restore script', 'restore.sh'),
            ('Schedule backups script', 'schedule_backups.sh')
        ]

        for name, filename in backup_scripts:
            script_path = self.project_root / "scripts" / filename
            is_executable = script_path.exists() and os.access(script_path, os.X_OK)
            self.record_result(
                'week4',
                f'{name} exists and is executable',
                is_executable,
                f"Permissions: {oct(script_path.stat().st_mode)[-3:]}" if script_path.exists() else "Not found"
            )

        # Test 3: Validate backup script syntax
        backup_script = self.project_root / "scripts" / "backup.sh"
        if backup_script.exists():
            try:
                result = subprocess.run(
                    ['bash', '-n', str(backup_script)],
                    capture_output=True
                )
                self.record_result(
                    'week4',
                    'Backup script syntax is valid',
                    result.returncode == 0,
                    "Bash syntax check passed" if result.returncode == 0 else result.stderr.decode()
                )
            except Exception as e:
                self.record_result('week4', 'Backup script syntax', False, str(e))

        # Test 4: Check dashboard files
        dashboards = [
            'trading_activity_dashboard.json',
            'system_health_dashboard.json',
            'performance_metrics_dashboard.json',
            'alert_management_dashboard.json',
            'infrastructure_dashboard.json'
        ]

        dashboards_dir = self.project_root / "dashboards"
        if dashboards_dir.exists():
            for dashboard in dashboards:
                dashboard_path = dashboards_dir / dashboard
                if dashboard_path.exists():
                    try:
                        with open(dashboard_path) as f:
                            data = json.load(f)
                            has_dashboard = 'dashboard' in data
                            self.record_result(
                                'week4',
                                f'{dashboard} is valid JSON',
                                has_dashboard,
                                f"Valid Grafana dashboard: {has_dashboard}"
                            )
                    except json.JSONDecodeError as e:
                        self.record_result('week4', f'{dashboard} JSON validation', False, str(e))
                else:
                    self.record_result('week4', f'{dashboard} exists', False, 'File not found')

        # Test 5: Check dashboard import script
        import_script = self.project_root / "scripts" / "import_dashboards.sh"
        is_executable = import_script.exists() and os.access(import_script, os.X_OK)
        self.record_result(
            'week4',
            'Dashboard import script exists and is executable',
            is_executable
        )

        # Test 6: Check dashboards README
        dashboard_readme = self.project_root / "dashboards" / "README.md"
        self.record_result(
            'week4',
            'Dashboards README exists',
            dashboard_readme.exists(),
            f"File size: {dashboard_readme.stat().st_size / 1024:.1f} KB" if dashboard_readme.exists() else "Not found"
        )

    # ========================================================================
    # INTEGRATION TESTS
    # ========================================================================

    def test_integration(self):
        """Test integration between weeks"""
        self.print_header("INTEGRATION TESTS")

        # Test 1: All weeks documentation exists
        all_weeks_docs = all([
            (self.project_root / "docs" / f"WEEK{i}_{'DEPLOYMENT' if i <= 2 else 'PERFORMANCE_HA' if i == 3 else 'PRODUCTION_GOLIVE'}_COMPLETION.md").exists()
            for i in range(1, 5)
        ])
        self.record_result(
            'week4',
            'All 4 weeks completion reports exist',
            all_weeks_docs,
            "Complete documentation chain"
        )

        # Test 2: Check project structure completeness
        required_dirs = ['docs', 'scripts', 'infrastructure', 'dashboards']
        dirs_exist = all((self.project_root / d).exists() for d in required_dirs)
        self.record_result(
            'week4',
            'Project directory structure is complete',
            dirs_exist,
            f"Directories: {', '.join(required_dirs)}"
        )

        # Test 3: Count total deliverables
        total_docs = len(list((self.project_root / "docs").glob("*.md")))
        total_scripts = len(list((self.project_root / "scripts").glob("*.sh")))
        total_dashboards = len(list((self.project_root / "dashboards").glob("*.json")))

        self.record_result(
            'week4',
            f'Documentation files: {total_docs}',
            total_docs >= 8,
            f"Expected >= 8, found {total_docs}"
        )

        self.record_result(
            'week4',
            f'Scripts: {total_scripts}',
            total_scripts >= 3,
            f"Expected >= 3, found {total_scripts}"
        )

        self.record_result(
            'week4',
            f'Grafana dashboards: {total_dashboards}',
            total_dashboards >= 5,
            f"Expected >= 5, found {total_dashboards}"
        )

    # ========================================================================
    # MAIN TEST RUNNER
    # ========================================================================

    def run_all_tests(self):
        """Run all tests for all 4 weeks"""
        print(f"\n{Color.BLUE}{'='*80}{Color.RESET}")
        print(f"{Color.BLUE}COMPREHENSIVE 4-WEEK IMPLEMENTATION TEST SUITE{Color.RESET}".center(80))
        print(f"{Color.BLUE}{'='*80}{Color.RESET}\n")

        # Run all week tests
        self.test_week1_advanced_features()
        self.test_week2_deployment_automation()
        self.test_week3_performance_ha()
        self.test_week4_operational_excellence()
        self.test_integration()

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")

        total_passed = 0
        total_failed = 0

        for week, results in self.results.items():
            passed = results['passed']
            failed = results['failed']
            total = passed + failed

            total_passed += passed
            total_failed += failed

            percentage = (passed / total * 100) if total > 0 else 0

            status = f"{Color.GREEN}✓{Color.RESET}" if failed == 0 else f"{Color.YELLOW}!{Color.RESET}"
            print(f"{status} {week.upper()}: {passed}/{total} tests passed ({percentage:.1f}%)")

        print(f"\n{Color.BLUE}{'='*80}{Color.RESET}")

        total = total_passed + total_failed
        overall_percentage = (total_passed / total * 100) if total > 0 else 0

        if total_failed == 0:
            print(f"{Color.GREEN}ALL TESTS PASSED: {total_passed}/{total} ({overall_percentage:.1f}%){Color.RESET}")
        else:
            print(f"{Color.YELLOW}TESTS COMPLETED: {total_passed}/{total} passed ({overall_percentage:.1f}%){Color.RESET}")
            print(f"{Color.RED}Failed tests: {total_failed}{Color.RESET}")

        print(f"{Color.BLUE}{'='*80}{Color.RESET}\n")

        # Return exit code
        return 0 if total_failed == 0 else 1

def main():
    """Main entry point"""
    tester = WeeklyImplementationTester()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
