"""
Security Scanner
Dedicated security analysis using multiple specialized tools.

Detects:
- Hardcoded secrets (API keys, passwords, tokens)
- SQL injection vulnerabilities
- XSS vulnerabilities
- Insecure dependencies
- Authentication/authorization issues
- Sensitive data exposure
- Cryptographic issues

Uses:
- Bandit (Python security)
- Safety (Python dependency vulnerabilities)
- npm audit (JavaScript dependencies)
- Semgrep (pattern-based security rules - multi-language)
- Custom regex patterns for secrets
"""

import asyncio
import json
import re
import subprocess
from typing import Dict, Any, List, Optional, Set
from pathlib import Path


class SecurityScanner:
    """
    Comprehensive security scanner using multiple tools.
    
    This provides OBJECTIVE SECURITY EVIDENCE, not AI guesses.
    """
    
    # Common patterns for hardcoded secrets
    SECRET_PATTERNS = {
        "aws_key": r"AKIA[0-9A-Z]{16}",
        "api_key": r"api[_-]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",
        "password": r"password['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "private_key": r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
        "github_token": r"gh[pousr]_[A-Za-z0-9_]{36,255}",
        "slack_token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}",
        "stripe_key": r"sk_live_[a-zA-Z0-9]{24,}",
        "jwt": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
    }
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze_files(
        self,
        files: List[str],
        full_scan: bool = False
    ) -> Dict[str, Any]:
        """
        Perform comprehensive security analysis.
        
        Args:
            files: List of files to analyze
            full_scan: If True, run all scanners. If False, run fast checks only.
        
        Returns:
            Security findings as objective evidence
        """
        result = {
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "security_findings": [],
            "hardcoded_secrets": [],
            "vulnerable_dependencies": [],
            "injection_risks": [],
            "tools_used": [],
        }
        
        # Always run: Secret detection (fast)
        secret_findings = await self._detect_secrets(files)
        if secret_findings:
            self._merge_findings(result, secret_findings)
            result["tools_used"].append("regex-secret-scanner")
        
        # Group files by language
        python_files = [f for f in files if f.endswith('.py')]
        js_files = [f for f in files if f.endswith(('.js', '.jsx', '.ts', '.tsx'))]
        
        # Python: Run Bandit
        if python_files:
            bandit_result = await self._run_bandit(python_files)
            if bandit_result:
                self._merge_findings(result, bandit_result)
                result["tools_used"].append("Bandit")
        
        if full_scan:
            # Python: Check dependency vulnerabilities
            if python_files or any("requirements" in f or "Pipfile" in f for f in files):
                safety_result = await self._run_safety()
                if safety_result:
                    self._merge_findings(result, safety_result)
                    result["tools_used"].append("Safety")
            
            # JavaScript: npm audit
            if js_files or any("package.json" in f for f in files):
                npm_result = await self._run_npm_audit()
                if npm_result:
                    self._merge_findings(result, npm_result)
                    result["tools_used"].append("npm audit")
            
            # Multi-language: Semgrep (if available)
            semgrep_result = await self._run_semgrep(files)
            if semgrep_result:
                self._merge_findings(result, semgrep_result)
                result["tools_used"].append("Semgrep")
        
        return result
    
    async def _detect_secrets(self, files: List[str]) -> Dict[str, Any]:
        """
        Detect hardcoded secrets using regex patterns.
        
        This is fast and catches common mistakes.
        """
        findings = []
        
        for file_path in files:
            try:
                full_path = self.repo_path / file_path
                
                # Skip non-text files
                if full_path.suffix in ['.jpg', '.png', '.gif', '.pdf', '.zip']:
                    continue
                
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check each pattern
                for secret_type, pattern in self.SECRET_PATTERNS.items():
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    
                    for match in matches:
                        # Find line number
                        line_num = content[:match.start()].count('\n') + 1
                        
                        # Mask the secret
                        secret_value = match.group(0)
                        masked_value = secret_value[:4] + "****" + secret_value[-4:]
                        
                        findings.append({
                            "severity": "CRITICAL",
                            "type": "hardcoded_secret",
                            "file": str(file_path),
                            "line": line_num,
                            "issue": f"Potential {secret_type} detected",
                            "value": masked_value,
                        })
            
            except Exception:
                # Skip files that can't be read
                continue
        
        return {
            "critical_issues": len(findings),
            "hardcoded_secrets": findings,
        }
    
    async def _run_bandit(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run Bandit Python security scanner.
        
        Bandit checks:
        - SQL injection
        - Hardcoded passwords
        - Unsafe functions (exec, eval)
        - Weak cryptography
        - Insecure deserialization
        """
        try:
            cmd = ["bandit", "-f", "json", "-r"] + files
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            return self._parse_bandit_output(output)
        
        except Exception:
            return None
    
    async def _run_safety(self) -> Optional[Dict[str, Any]]:
        """
        Run Safety to check Python dependencies for known vulnerabilities.
        
        Checks against a database of known CVEs.
        """
        try:
            cmd = ["safety", "check", "--json"]
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            return self._parse_safety_output(output)
        
        except Exception:
            return None
    
    async def _run_npm_audit(self) -> Optional[Dict[str, Any]]:
        """
        Run npm audit for JavaScript dependency vulnerabilities.
        """
        try:
            cmd = ["npm", "audit", "--json"]
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            return self._parse_npm_audit_output(output)
        
        except Exception:
            return None
    
    async def _run_semgrep(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run Semgrep for pattern-based security scanning.
        
        Semgrep uses community rules to detect:
        - SQL injection
        - XSS vulnerabilities
        - Path traversal
        - Command injection
        - Insecure configurations
        """
        try:
            cmd = [
                "semgrep",
                "--config=auto",  # Use Semgrep registry rules
                "--json",
                "--quiet",
            ] + files
            
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            return self._parse_semgrep_output(output)
        
        except Exception:
            return None
    
    async def _run_command(self, cmd: List[str]) -> Optional[str]:
        """Run command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_path),
            )
            
            stdout, stderr = await process.communicate()
            return stdout.decode('utf-8', errors='ignore')
        
        except FileNotFoundError:
            return None
        except Exception:
            return None
    
    def _parse_bandit_output(self, output: str) -> Dict[str, Any]:
        """Parse Bandit JSON output."""
        try:
            data = json.loads(output)
            results = data.get("results", [])
            
            findings = []
            critical = 0
            high = 0
            medium = 0
            low = 0
            
            for r in results:
                severity = r.get("issue_severity", "LOW")
                
                if severity == "CRITICAL":
                    critical += 1
                elif severity == "HIGH":
                    high += 1
                elif severity == "MEDIUM":
                    medium += 1
                else:
                    low += 1
                
                findings.append({
                    "severity": severity,
                    "type": r.get("test_id"),
                    "file": r.get("filename"),
                    "line": r.get("line_number"),
                    "issue": r.get("issue_text"),
                    "confidence": r.get("issue_confidence"),
                })
            
            # Categorize injection risks
            injection_risks = [
                f for f in findings
                if any(keyword in f["issue"].lower() for keyword in ["sql", "injection", "query"])
            ]
            
            return {
                "critical_issues": critical,
                "high_issues": high,
                "medium_issues": medium,
                "low_issues": low,
                "security_findings": findings,
                "injection_risks": injection_risks,
            }
        
        except json.JSONDecodeError:
            return {}
    
    def _parse_safety_output(self, output: str) -> Dict[str, Any]:
        """Parse Safety JSON output."""
        try:
            data = json.loads(output)
            
            vulnerable_deps = []
            
            for vuln in data:
                vulnerable_deps.append({
                    "package": vuln.get("package"),
                    "version": vuln.get("installed_version"),
                    "vulnerability": vuln.get("vulnerability"),
                    "cve": vuln.get("cve"),
                    "severity": "HIGH",  # Safety reports are typically high severity
                })
            
            return {
                "high_issues": len(vulnerable_deps),
                "vulnerable_dependencies": vulnerable_deps,
            }
        
        except json.JSONDecodeError:
            return {}
    
    def _parse_npm_audit_output(self, output: str) -> Dict[str, Any]:
        """Parse npm audit JSON output."""
        try:
            data = json.loads(output)
            metadata = data.get("metadata", {}).get("vulnerabilities", {})
            
            critical = metadata.get("critical", 0)
            high = metadata.get("high", 0)
            moderate = metadata.get("moderate", 0)
            low = metadata.get("low", 0)
            
            # Extract specific vulnerabilities
            vulnerabilities = data.get("vulnerabilities", {})
            vulnerable_deps = []
            
            for pkg_name, vuln_info in vulnerabilities.items():
                vulnerable_deps.append({
                    "package": pkg_name,
                    "severity": vuln_info.get("severity", "UNKNOWN").upper(),
                    "via": vuln_info.get("via", []),
                })
            
            return {
                "critical_issues": critical,
                "high_issues": high,
                "medium_issues": moderate,
                "low_issues": low,
                "vulnerable_dependencies": vulnerable_deps,
            }
        
        except json.JSONDecodeError:
            return {}
    
    def _parse_semgrep_output(self, output: str) -> Dict[str, Any]:
        """Parse Semgrep JSON output."""
        try:
            data = json.loads(output)
            results = data.get("results", [])
            
            findings = []
            critical = 0
            high = 0
            medium = 0
            
            for r in results:
                severity = r.get("extra", {}).get("severity", "WARNING").upper()
                
                if "CRITICAL" in severity:
                    critical += 1
                elif "ERROR" in severity or "HIGH" in severity:
                    high += 1
                else:
                    medium += 1
                
                findings.append({
                    "severity": severity,
                    "type": r.get("check_id"),
                    "file": r.get("path"),
                    "line": r.get("start", {}).get("line"),
                    "issue": r.get("extra", {}).get("message"),
                })
            
            return {
                "critical_issues": critical,
                "high_issues": high,
                "medium_issues": medium,
                "security_findings": findings,
            }
        
        except json.JSONDecodeError:
            return {}
    
    def _merge_findings(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge security findings."""
        target["critical_issues"] += source.get("critical_issues", 0)
        target["high_issues"] += source.get("high_issues", 0)
        target["medium_issues"] += source.get("medium_issues", 0)
        target["low_issues"] += source.get("low_issues", 0)
        
        for key in ["security_findings", "hardcoded_secrets", "vulnerable_dependencies", "injection_risks"]:
            target[key].extend(source.get(key, []))
    
    def get_security_summary(self, result: Dict[str, Any]) -> str:
        """
        Generate human-readable security summary for LLM context.
        """
        parts = []
        
        # Overall severity counts
        total = (
            result["critical_issues"] +
            result["high_issues"] +
            result["medium_issues"] +
            result["low_issues"]
        )
        
        if total == 0:
            return "✅ No security issues detected"
        
        parts.append(f"Security issues found: {total}")
        
        if result["critical_issues"] > 0:
            parts.append(f"🔴 Critical: {result['critical_issues']}")
        
        if result["high_issues"] > 0:
            parts.append(f"🟠 High: {result['high_issues']}")
        
        if result["medium_issues"] > 0:
            parts.append(f"🟡 Medium: {result['medium_issues']}")
        
        # Specific categories
        if result["hardcoded_secrets"]:
            parts.append(f"\n⚠️ Hardcoded secrets detected: {len(result['hardcoded_secrets'])}")
        
        if result["vulnerable_dependencies"]:
            parts.append(f"⚠️ Vulnerable dependencies: {len(result['vulnerable_dependencies'])}")
        
        if result["injection_risks"]:
            parts.append(f"⚠️ Potential injection vulnerabilities: {len(result['injection_risks'])}")
        
        # Tools used
        if result.get("tools_used"):
            parts.append(f"\nScanners: {', '.join(result['tools_used'])}")
        
        return "\n".join(parts)
    
    def assess_security_risk(self, result: Dict[str, Any]) -> str:
        """
        Assess overall security risk level.
        
        Returns: low, medium, high, critical
        """
        if result["critical_issues"] > 0 or len(result["hardcoded_secrets"]) > 0:
            return "critical"
        
        if result["high_issues"] > 2 or result["injection_risks"]:
            return "high"
        
        if result["high_issues"] > 0 or result["medium_issues"] > 3:
            return "medium"
        
        return "low"
