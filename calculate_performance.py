import os
import sys
import subprocess
import xml.etree.ElementTree as ET

def run_tests():
    print("Running test suite and generating XML report...")
    # Run pytest using the current python executable
    cmd = [sys.executable, "-m", "pytest", "--junitxml=test_results.xml", "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Pytest returns exit code 1 if tests fail, but we still want to parse the XML
    return result.returncode

def parse_results():
    if not os.path.exists("test_results.xml"):
        raise FileNotFoundError("test_results.xml was not created. Did pytest run successfully?")
    
    tree = ET.parse("test_results.xml")
    root = tree.getroot()
    
    if root.tag == "testsuite":
        testsuite = root
    else:
        testsuite = root.find("testsuite")
        if testsuite is None:
            testsuite = root

    total = int(testsuite.attrib.get("tests", 0))
    failures = int(testsuite.attrib.get("failures", 0))
    errors = int(testsuite.attrib.get("errors", 0))
    skipped = int(testsuite.attrib.get("skipped", 0))
    time_taken = float(testsuite.attrib.get("time", 0.0))
    
    passed = total - failures - errors - skipped
    
    return {
        "total": total,
        "passed": passed,
        "failed": failures + errors,
        "skipped": skipped,
        "time": time_taken
    }

def update_readme(metrics):
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        raise FileNotFoundError("README.md not found in the current directory.")
        
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    start_marker = "<!-- METRICS_START -->"
    end_marker = "<!-- METRICS_END -->"
    
    if start_marker not in content or end_marker not in content:
        raise ValueError("Could not find METRICS_START and METRICS_END markers in README.md")
        
    n_passed = metrics["passed"]
    n_total = metrics["total"]
    t_total = metrics["time"]
    t_avg = t_total / n_total if n_total > 0 else 0.0
    pass_rate = (n_passed / n_total * 100) if n_total > 0 else 0.0
    fail_rate = (metrics["failed"] / n_total * 100) if n_total > 0 else 0.0
    
    metrics_markdown = f"""{start_marker}
### Mathematical Performance Metrics

* **Passed Test Cases ($N_\\text{{passed}}$):**
  $$N_\\text{{passed}} = {n_passed}$$

* **Total Test Cases ($N_\\text{{total}}$):**
  $$N_\\text{{total}} = {n_total}$$

* **Pass Rate ($P_\\text{{rate}}$):**
  $$P_\\text{{rate}} = \\frac{{N_\\text{{passed}}}}{{N_\\text{{total}}}} \\times 100\\% = \\frac{{{n_passed}}}{{{n_total}}} \\times 100\\% = {pass_rate:.1f}\\%$$

* **Total Execution Time ($T_\\text{{total}}$):**
  $$T_\\text{{total}} = {t_total:.2f}\\text{{ seconds}}$$

* **Average Time per Test Case ($T_\\text{{avg}}$):**
  $$T_\\text{{avg}} = \\frac{{T_\\text{{total}}}}{{N_\\text{{total}}}} = \\frac{{{t_total:.2f}\\text{{ s}}}}{{{n_total}}} \\approx {t_avg:.2f}\\text{{ seconds / test}}$$

* **Failure Rate ($F_\\text{{rate}}$):**
  $$F_\\text{{rate}} = \\frac{{N_\\text{{total}} - N_\\text{{passed}}}}{{N_\\text{{total}}}} \\times 100\\% = \\frac{{{n_total} - {n_passed}}}{{{n_total}}} \\times 100\\% = {fail_rate:.1f}\\%$$
{end_marker}"""

    parts = content.split(start_marker)
    before = parts[0]
    after = parts[1].split(end_marker)[1]
    
    new_content = before + metrics_markdown + after
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print("README.md updated successfully with calculated mathematical metrics.")

if __name__ == "__main__":
    run_tests()
    try:
        metrics = parse_results()
        print(f"Parsed metrics: {metrics}")
        update_readme(metrics)
    except Exception as e:
        print(f"Error updating README: {e}", file=sys.stderr)
        sys.exit(1)
