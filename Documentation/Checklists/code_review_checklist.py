#!/usr/bin/env python3
"""
Comprehensive Code Review Tool
Systematically checks all modules for common issues
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import re

class CodeReviewer:
    """Automated code review tool"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.issues = []
        self.stats = {
            'files_checked': 0,
            'lines_checked': 0,
            'issues_found': 0,
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }

    def check_file(self, filepath: Path) -> List[Dict]:
        """Check a single Python file for issues"""
        issues = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            self.stats['files_checked'] += 1
            self.stats['lines_checked'] += len(lines)

            # Check for common issues
            issues.extend(self.check_security(filepath, content, lines))
            issues.extend(self.check_error_handling(filepath, content, lines))
            issues.extend(self.check_performance(filepath, content, lines))
            issues.extend(self.check_best_practices(filepath, content, lines))
            issues.extend(self.check_threading(filepath, content, lines))

        except Exception as e:
            issues.append({
                'file': str(filepath),
                'line': 0,
                'severity': 'critical',
                'category': 'parse_error',
                'message': f"Failed to parse file: {e}"
            })

        return issues

    def check_security(self, filepath: Path, content: str, lines: List[str]) -> List[Dict]:
        """Check for security vulnerabilities"""
        issues = []

        # Check for hardcoded credentials
        patterns = [
            (r'password\s*=\s*["\'].*["\']', 'Hardcoded password detected'),
            (r'api_key\s*=\s*["\'].*["\']', 'Hardcoded API key detected'),
            (r'secret\s*=\s*["\'].*["\']', 'Hardcoded secret detected'),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, message in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    if 'os.getenv' not in line and 'os.environ' not in line and 'input(' not in line:
                        issues.append({
                            'file': str(filepath),
                            'line': i,
                            'severity': 'critical',
                            'category': 'security',
                            'message': message,
                            'code': line.strip()
                        })

        # Check for SQL injection (if any SQL)
        if 'execute(' in content and 'format(' in content:
            issues.append({
                'file': str(filepath),
                'line': 0,
                'severity': 'high',
                'category': 'security',
                'message': 'Potential SQL injection - check query construction'
            })

        # Check for unsafe pickle usage
        if 'pickle.loads' in content and 'untrusted' not in content:
            issues.append({
                'file': str(filepath),
                'line': 0,
                'severity': 'high',
                'category': 'security',
                'message': 'Unsafe pickle.loads() - potential code execution risk'
            })

        # Check for eval/exec usage
        if re.search(r'\beval\(', content) or re.search(r'\bexec\(', content):
            for i, line in enumerate(lines, 1):
                if 'eval(' in line or 'exec(' in line:
                    issues.append({
                        'file': str(filepath),
                        'line': i,
                        'severity': 'critical',
                        'category': 'security',
                        'message': 'Dangerous eval()/exec() usage detected',
                        'code': line.strip()
                    })

        return issues

    def check_error_handling(self, filepath: Path, content: str, lines: List[str]) -> List[Dict]:
        """Check error handling patterns"""
        issues = []

        # Check for bare except clauses
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*except\s*:', line):
                issues.append({
                    'file': str(filepath),
                    'line': i,
                    'severity': 'medium',
                    'category': 'error_handling',
                    'message': 'Bare except clause - should specify exception type',
                    'code': line.strip()
                })

            # Check for pass in except blocks
            if i < len(lines) and 'except' in lines[i-1]:
                if line.strip() == 'pass':
                    issues.append({
                        'file': str(filepath),
                        'line': i,
                        'severity': 'high',
                        'category': 'error_handling',
                        'message': 'Silent error handling - exceptions should be logged',
                        'code': line.strip()
                    })

        # Check for missing finally blocks with file operations
        if 'open(' in content and 'with' not in content:
            issues.append({
                'file': str(filepath),
                'line': 0,
                'severity': 'medium',
                'category': 'resource_management',
                'message': 'File opened without context manager (with statement)'
            })

        return issues

    def check_performance(self, filepath: Path, content: str, lines: List[str]) -> List[Dict]:
        """Check for performance issues"""
        issues = []

        # Check for string concatenation in loops
        in_loop = False
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*for\s+.*:', line) or re.match(r'\s*while\s+.*:', line):
                in_loop = True
            elif in_loop and ('+=' in line and '"' in line or "'" in line):
                if 'str' in lines[i-2:i]:  # Check nearby lines for string context
                    issues.append({
                        'file': str(filepath),
                        'line': i,
                        'severity': 'low',
                        'category': 'performance',
                        'message': 'String concatenation in loop - consider using list + join()',
                        'code': line.strip()
                    })
            elif not line.strip() or line.strip().startswith('#'):
                continue
            elif re.match(r'\s*def\s+', line) or re.match(r'\s*class\s+', line):
                in_loop = False

        # Check for inefficient list operations
        if '.append(' in content and 'for' in content:
            # This is a heuristic - list comprehensions might be better
            pass  # Too many false positives, skip for now

        return issues

    def check_best_practices(self, filepath: Path, content: str, lines: List[str]) -> List[Dict]:
        """Check coding best practices"""
        issues = []

        # Check for missing docstrings in classes/functions
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*class\s+\w+', line) or re.match(r'\s*def\s+\w+', line):
                # Check if next non-empty line is a docstring
                j = i
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    next_line = lines[j].strip()
                    if not (next_line.startswith('"""') or next_line.startswith("'''")):
                        if 'def __' not in line:  # Skip dunder methods
                            issues.append({
                                'file': str(filepath),
                                'line': i,
                                'severity': 'low',
                                'category': 'documentation',
                                'message': 'Missing docstring',
                                'code': line.strip()
                            })

        # Check for magic numbers
        for i, line in enumerate(lines, 1):
            # Look for standalone numbers (not in common contexts)
            if re.search(r'\b\d{3,}\b', line):
                if 'range(' not in line and 'sleep(' not in line and '#' not in line:
                    issues.append({
                        'file': str(filepath),
                        'line': i,
                        'severity': 'low',
                        'category': 'maintainability',
                        'message': 'Magic number - consider using named constant',
                        'code': line.strip()
                    })

        return issues

    def check_threading(self, filepath: Path, content: str, lines: List[str]) -> List[Dict]:
        """Check threading safety"""
        issues = []

        # Check for mutable default arguments
        for i, line in enumerate(lines, 1):
            if 'def ' in line and '=[' in line or '={' in line:
                issues.append({
                    'file': str(filepath),
                    'line': i,
                    'severity': 'high',
                    'category': 'threading',
                    'message': 'Mutable default argument - can cause threading issues',
                    'code': line.strip()
                })

        # Check for shared state without locks
        if 'threading' in content or 'Thread' in content:
            if 'Lock' not in content and 'RLock' not in content:
                issues.append({
                    'file': str(filepath),
                    'line': 0,
                    'severity': 'high',
                    'category': 'threading',
                    'message': 'Threading used without locks - potential race conditions'
                })

        return issues

    def review_module(self, module_path: str) -> List[Dict]:
        """Review all files in a module"""
        module_issues = []
        module_dir = self.base_path / module_path

        if not module_dir.exists():
            return module_issues

        for py_file in module_dir.rglob('*.py'):
            if '__pycache__' not in str(py_file):
                file_issues = self.check_file(py_file)
                module_issues.extend(file_issues)
                self.stats['issues_found'] += len(file_issues)

                for issue in file_issues:
                    severity = issue['severity']
                    if severity in self.stats:
                        self.stats[severity] += 1

        return module_issues

    def generate_report(self) -> str:
        """Generate comprehensive review report"""
        report = []
        report.append("=" * 80)
        report.append("COMPREHENSIVE CODE REVIEW REPORT")
        report.append("=" * 80)
        report.append("")
        report.append("STATISTICS:")
        report.append(f"  Files Checked:    {self.stats['files_checked']}")
        report.append(f"  Lines Checked:    {self.stats['lines_checked']:,}")
        report.append(f"  Issues Found:     {self.stats['issues_found']}")
        report.append(f"    Critical:       {self.stats['critical']}")
        report.append(f"    High:           {self.stats['high']}")
        report.append(f"    Medium:         {self.stats['medium']}")
        report.append(f"    Low:            {self.stats['low']}")
        report.append("")

        # Group issues by severity and category
        by_severity = {}
        for issue in self.issues:
            severity = issue['severity']
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(issue)

        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in by_severity:
                report.append("=" * 80)
                report.append(f"{severity.upper()} SEVERITY ISSUES ({len(by_severity[severity])})")
                report.append("=" * 80)
                report.append("")

                for issue in by_severity[severity]:
                    report.append(f"File: {issue['file']}")
                    report.append(f"Line: {issue['line']}")
                    report.append(f"Category: {issue['category']}")
                    report.append(f"Message: {issue['message']}")
                    if 'code' in issue:
                        report.append(f"Code: {issue['code']}")
                    report.append("")

        return "\n".join(report)


def main():
    """Run comprehensive code review"""
    base_path = '/Users/gogineni/Python/trading-system'
    reviewer = CodeReviewer(base_path)

    # Review all modules
    modules = ['strategies', 'infrastructure', 'data', 'core', 'fno', 'utilities']

    print("Starting comprehensive code review...")
    print()

    for module in modules:
        print(f"Reviewing {module}/ ...")
        issues = reviewer.review_module(module)
        reviewer.issues.extend(issues)

    # Review main.py
    print("Reviewing main.py ...")
    main_issues = reviewer.check_file(Path(base_path) / 'main.py')
    reviewer.issues.extend(main_issues)
    reviewer.stats['issues_found'] += len(main_issues)

    # Generate report
    report = reviewer.generate_report()
    print()
    print(report)

    # Save report
    with open(Path(base_path) / 'CODE_REVIEW_REPORT.txt', 'w') as f:
        f.write(report)

    print()
    print("Report saved to CODE_REVIEW_REPORT.txt")

    return 0 if reviewer.stats['critical'] == 0 and reviewer.stats['high'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
