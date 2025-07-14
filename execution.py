import re
from typing import List, Dict

output = """
{"success": false, "stdout": "============================= test session starts ==============================\nplatform darwin -- Python 3.13.1, pytest-8.4.0, pluggy-1.6.0 -- /Users/hanxiaoke/Documents/LLM_automation_testing/myenv/bin/python3\ncachedir: .pytest_cache\nrootdir: /var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T\nplugins: anyio-4.9.0\ncollecting ... collected 4 items\n\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_valid_pet PASSED [ 25%]\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_invalid_pet_missing_required_fields FAILED [ 50%]\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_pet_with_invalid_data_type FAILED [ 75%]\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_empty_pet_object FAILED [100%]\n\n=================================== FAILURES ===================================\n_________________ test_add_invalid_pet_missing_required_fields _________________\n/var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:31: in test_add_invalid_pet_missing_required_fields\n    assert response.status_code == 405\nE   assert 200 == 405\nE    +  where 200 = <Response [200]>.status_code\n_____________________ test_add_pet_with_invalid_data_type ______________________\n/var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:45: in test_add_pet_with_invalid_data_type\n    assert response.status_code == 405\nE   assert 500 == 405\nE    +  where 500 = <Response [500]>.status_code\n__________________________ test_add_empty_pet_object ___________________________\n/var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:52: in test_add_empty_pet_object\n    assert response.status_code == 405\nE   assert 200 == 405\nE    +  where 200 = <Response [200]>.status_code\n=============================== warnings summary ===============================\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:5\n  /var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:5: PytestUnknownMarkWarning: Unknown pytest.mark.successful_addition - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.successful_addition\n\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:19\n  /var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:19: PytestUnknownMarkWarning: Unknown pytest.mark.invalid_input - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.invalid_input\n\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:33\n  /var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:33: PytestUnknownMarkWarning: Unknown pytest.mark.invalid_input - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.invalid_input\n\n../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:47\n  /var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py:47: PytestUnknownMarkWarning: Unknown pytest.mark.invalid_input - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.invalid_input\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n=========================== short test summary info ============================\nFAILED ../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_invalid_pet_missing_required_fields\nFAILED ../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_pet_with_invalid_data_type\nFAILED ../../../../var/folders/q5/38hry1752xj5jpxqq3x71xvc0000gn/T/tmp__2hncmz.py::test_add_empty_pet_object\n=================== 3 failed, 1 passed, 4 warnings in 1.45s ====================\n", "stderr": "", "returncode": 1}
"""

def parse_pytest_output(output: str) -> Dict[str, Dict[str, str]]:
    """
    从 pytest stdout 中提取测试函数名和其状态（PASSED/FAILED）以及失败时的错误信息。
    返回：
    {
        'test_add_valid_pet': {'status': 'PASSED', 'error': ''},
        'test_add_invalid_pet_missing_required_fields': {'status': 'FAILED', 'error': 'assert 200 == 405\n...'},
        ...
    }
    """
    results = {}

    # 提取每个 case 的执行结果
    for line in output.splitlines():
        match = re.search(r"::(test_[\w_]+)\s+(PASSED|FAILED|SKIPPED)", line)
        if match:
            func_name, status = match.groups()
            results[func_name] = {'status': status, 'error': ''}

    # 提取错误信息（在 FAILURES 区段中）
    failure_block = output.split("=================================== FAILURES ===================================")
    if len(failure_block) > 1:
        failures_text = failure_block[1].split("============================== warnings summary ===============================")[0]
        failed_cases = re.findall(r"_{5,}\s*(test_[\w_]+)\s*_{5,}\n(.*?)\n(?=_{5,}|\Z)", failures_text, re.DOTALL)
        for func_name, error_msg in failed_cases:
            if func_name in results:
                results[func_name]['error'] = error_msg.strip()

    return results

result = parse_pytest_output(output)
print(result)
