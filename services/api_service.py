import json
import re
import subprocess
import tempfile
import requests
from utils.db import execute, fetch_one, fetch_all
from utils.llm import call_openai, call_deepseek
from utils.logging import Logger
from utils.prompt_loader import get_prompt
from utils.load_sql import load_all_sql
from utils.metrics import (check_syntax, check_status_code_coverage, convert_sets_to_lists, expand_schema,
                           calculate_method_coverage, calculate_data_type_coverage)

sqls = load_all_sql()
log = Logger()

def save_script(group_id,api_info, scenario_id, test_scenario, model_name, model_version, script, prompt_name):
    sql = sqls['add_generate_script']
    query_sql = sqls['query_generate_script']
    print('api_info', api_info)
    params = (group_id, api_info, scenario_id, test_scenario, model_name, model_version, prompt_name, script, script)
    save_result = execute(sql, params)
    query_params = (api_info, scenario_id, model_name, model_version)
    result = None
    if save_result:
        result = fetch_one(query_sql, query_params)
        log.info(f"check result after query: {result}")
    return result

def add_scenario_group(data):
    scenario_ids = [scenario['id'] for scenario in data]
    scenario_ids_sorted = sorted(scenario_ids)
    scenario_ids_json = json.dumps(scenario_ids_sorted)
    add_sql = sqls["add_scenario_group"]
    add_res = execute(add_sql, scenario_ids_json)
    new_result = None
    if add_res:
        log.info("save group scenarios success")
        sql = sqls["query_scenario_group"]
        new_result = fetch_one(sql, scenario_ids_json)
        group_scenario_relations_sql = sqls['add_scenario_group_relations']
        for i in scenario_ids:
            add_group_scenario_relations = execute(group_scenario_relations_sql, (new_result["id"], i))
            if add_group_scenario_relations:
                log.info(f"save group scenario relations success: {add_group_scenario_relations}")
            else:
                log.error(f"save group scenario relations fail: {add_group_scenario_relations}")
        return new_result["id"]
    log.info("save group scenarios fail")
    return new_result

def extract_cases(script_text):
    lines = script_text.splitlines(keepends=True)
    case_blocks = []
    func_names = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("@"):
            # Collect all decorator lines (including multi-line decorators)
            decorator_start = i
            i += 1  # Move to next line after @
            
            # Continue collecting lines until we find a function definition or another @
            while i < len(lines):
                current_line = lines[i]
                stripped = current_line.strip()
                
                if stripped.startswith("@"):
                    break
                
                if re.match(r'^\s*def\s+\w+', stripped):
                    if re.match(r'^\s*def\s+test_\w+', stripped):
                        match = re.match(r'^\s*def\s+(test_\w+)\s*\(.*?\):', stripped)
                        if match:
                            func_name = match.group(1)
                            start = decorator_start  # Start from the first @ line
                            i += 1  # Skip the def line
                            while i < len(lines):
                                next_line = lines[i]
                                if next_line.strip() == "":
                                    i += 1
                                    continue
                                if not lines[i].startswith(" ") or lines[i].startswith("\t"):
                                    break
                                i += 1
                            end = i
                            func_body = "".join(lines[start:end])
                            func_names.append(func_name)
                            case_blocks.append(func_body)
                    else:
                        pass
                    break
                
                i += 1
            continue
        match = re.match(r'^\s*def\s+(test_\w+)\s*\(.*?\):', line)
        if match:
            func_name = match.group(1)
            start = i
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip() == "":
                    i += 1
                    continue
                if not lines[i].startswith(" ") or lines[i].startswith("\t"):
                    break
                i += 1
            end = i
            func_body = "".join(lines[start:end])
            func_names.append(func_name)
            case_blocks.append(func_body)
        else:
            i += 1
    return func_names, case_blocks

def generate_test_script(data):
    selected_scenarios = data.get('selected_scenarios')
    group_id = add_scenario_group(selected_scenarios)
    selected_apis_list = data.get("selected_apis")
    selected_apis = json.dumps(data.get("selected_apis", []))
    # print('api original', data.get("selected_apis"))
    # print('api original type', type(data.get("selected_apis")))
    # print('api', selected_apis)
    # print('api type', type(selected_apis))
    model = data.get('model_name')
    model_version = data.get('model_version')
    prompt_name = "generate_test_case_prompt"
    script = None
    # print("-------", data.get('selected_scenarios'))
    for scenario in selected_scenarios:
        scenario_id = scenario['id']
        test_scenario = scenario['last_version']
        context = {
            'selected_apis': selected_apis,
            'selected_scenarios': test_scenario
        }
        prompt = get_prompt("generate_test_case_prompt", context)
        print("---prompt: ", prompt)
        print("---prompt type: ", type(prompt))
        if model == "ChatGPT":
            script = call_openai(prompt, model_version)
        if model == "DeepSeek":
            script = call_deepseek(prompt, model_version)
        if script:
            if script.startswith("```"):
                script = re.sub(r"```(?:python)?\n?", "", script)
                script = re.sub(r"```$", "", script.strip())
            # save generated script
            script_syntax_result = 0.0
            # check script syntax
            check_script_syntax = check_syntax(script)
            print('check_script_syntax', check_script_syntax)
            if check_script_syntax:
                script_syntax_result = 100.0
            print('script_syntax_result', script_syntax_result)
            parameter_context = {
                'selected_apis': selected_apis,
                'generated_script': script,
                'scenario': test_scenario
            }
            # check test script status code coverage
            # status_code_coverage, status_code_coverage_detail = check_status_code_coverage_by_script(parameter_context,
            #                                                                                          model,
            #                                                                                          model_version)
            # check test script method coverage
            method_coverage, method_coverage_detail = calculate_method_coverage(parameter_context, model, model_version)
            print('method_coverage', method_coverage)
            print('method_coverage_detail', method_coverage_detail)
            # check test script data type correctness
            data_type_coverage, data_type_detail = calculate_data_type_coverage(parameter_context, model, model_version)
            add_script_sql = sqls['add_generate_script']
            prompt_json = json.dumps(prompt)
            params = (group_id, selected_apis, scenario_id, test_scenario, model, model_version, prompt_json,
                      script, script, script_syntax_result, script_syntax_result, data_type_coverage,
                      data_type_coverage, data_type_detail, data_type_detail, method_coverage, method_coverage,
                      method_coverage_detail, method_coverage_detail)
            add_script_sql_result = execute(add_script_sql, params)
            if add_script_sql_result:
                log.info(f"save generated script successful: {add_script_sql_result}")
                # query script info
                query_sql = sqls['query_generate_script']
                query_params = (selected_apis, scenario_id, group_id)
                query_result = fetch_one(query_sql, query_params)
                if query_result:
                    log.info(f"query script result success: {query_result}")
                    script_id = query_result['id']
                    script_text = query_result['last_version']
                    # extract function name and case body
                    # pattern = re.compile(
                    #     r'^def\s+(test_\w+)\s*\(.*?\):\n'
                    #     r'(?:^[ \t]+.*(?:\n|$))*'
                    #     , re.MULTILINE
                    # )
                    # func_names = []
                    # case_blocks = []
                    # for match in pattern.finditer(script_text):
                    #     func_names.append(match.group(1))
                    #     start_pos = match.start()
                    #     next_match = next(pattern.finditer(script_text, match.end()), None)
                    #     end_pos = next_match.start() if next_match else len(script_text)
                    #     case_blocks.append(script_text[start_pos:end_pos])
                    func_names, case_blocks = extract_cases(script_text)
                    if len(func_names) != len(case_blocks):
                        log.warning(f"Mismatch between marks ({len(func_names)}) and functions ({len(case_blocks)})")
                    valid_case_count = 0
                    total_cases = len(func_names)
                    for i, (mark, func_body) in enumerate(zip(func_names, case_blocks), 1):
                        print(f"--- CASE {i} title ---\n{mark}\n")
                        print(f"--- CASE {i} title ---\n{func_body}\n")
                        add_script_case_sql = sqls['add_script_case_detail']
                        source_type = "LLM"
                        if script_syntax_result == 1:
                            case_syntax_result = 0
                            valid_case_count += 1
                        else:
                            check_case_syntax_result = check_syntax(func_body)
                            if check_case_syntax_result:
                                case_syntax_result = 0
                                valid_case_count += 1
                            else:
                                case_syntax_result = 1
                        add_script_case_res = execute(add_script_case_sql, (script_id, scenario_id, mark,
                                                                            func_body, func_body, source_type, case_syntax_result))
                        if add_script_case_res:
                            log.info(f"add script case success: {add_script_case_res}")
                        else:
                            log.error(f"add script case fail: {add_script_case_res}")
                    if script_syntax_result == 0:
                        update_script_syntax_sql = sqls['update_script_syntax']
                        syntax_rate = round(valid_case_count / total_cases, 2) if total_cases > 0 else 0.0
                        update_script_syntax_result = execute(update_script_syntax_sql, (syntax_rate, script_id))
                        if update_script_syntax_result:
                            log.info(f"update script case syntax check result success: {update_script_syntax_result}")
                        else:
                            log.error(f"update script case syntax check result fail: {update_script_syntax_result}")
                else:
                    log.error(f"query script result fail: {query_result}")
            else:
                log.error(f"save generated script fail: {add_script_sql_result}")

    return group_id



def execute_test_script(data):
    # id = data.get('taskId')
    response_result = {}
    script_code = data.get('script')
    task_id = data.get('task_id')
    case_name = data.get('case_name')
    print('case_name', case_name)
    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as tmp_file:
        tmp_file.write(script_code)
        tmp_path = tmp_file.name
    try:
        # command = ["pytest", tmp_path, "-v", "--tb=short"]
        command = ["pytest", tmp_path, "-v", "--tb=long", "-s"]
        if case_name:
            command += ["-k", case_name]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )
        response_result["success"] = result.returncode == 0
        response_result["stdout"] = result.stdout
        response_result["stderr"] = result.stderr
        response_result["returncode"] = result.returncode
        print('execution result', result.stdout)

    except subprocess.TimeoutExpired:
        response_result["success"] = False
        response_result["error"] = "Execution timed out"
        return {
            "success": False,
            "error": "Execution timed out"
        }
    # query script detail
    query_detail_sql = sqls['query_script_detail_by_id']
    script_result = fetch_one(query_detail_sql, (task_id))
    selected_apis = script_result['spec_url']
    model = script_result['model_name']
    model_version = script_result['model_version']
    scenario = script_result['test_scenario']
    old_status_code_coverage = script_result['status_code_coverage']
    if result.returncode:
        parameter_context = {
            'selected_apis': selected_apis,
            'scenario': scenario,
            'execution_result': result.stdout
        }
        prompt_text = get_prompt("check_status_code_coverage_by_execution_results", parameter_context)
    else:
        parameter_context = {
            'selected_apis': selected_apis,
            'scenario': scenario,
            'generated_script': script_result
        }
        prompt_text = get_prompt("check_status_code_coverage_by_script", parameter_context)
    status_code_coverage, status_code_coverage_detail = check_status_code_coverage(model, model_version, prompt_text)
    print('status_code_coverage', status_code_coverage)
    print('status_code_coverage_detail', status_code_coverage_detail)
    if old_status_code_coverage:
        params = (status_code_coverage, status_code_coverage_detail, task_id)
        sql = sqls["update_status_coverage"]
    else:
        sql = sqls["set_status_coverage"]
        params = (status_code_coverage, status_code_coverage, status_code_coverage_detail, status_code_coverage_detail,
                  task_id)

    update_status_result = execute(sql, params)
    if update_status_result:
        log.info("update script status code coverage success")
    else:
        log.info("update script status code coverage fail")
    sql = sqls['add_execution_result']
    params = (task_id, json.dumps(response_result, ensure_ascii=False))
    save_result = execute(sql, params)
    if save_result:
        log.info("save execution result success")
    else:
        log.info("save execution result fail")
    execution_results = parse_pytest_output(result.stdout)
    query_case_sql = sqls['query_script_case_by_script_id']
    query_case_result = fetch_all(query_case_sql, task_id)
    if query_case_result:
        # print('query_case_result', query_case_result)
        update_execution_result(query_case_result, execution_results)
    return response_result

def parse_pytest_output(output):
    try:
        data = json.loads(output)
        stdout = data.get('stdout', '')
    except Exception as e:
        stdout = output
    lines = stdout.split('\n')

    status_keywords = 'PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS'
    test_line_regex = re.compile(r'::(test_[\w_]+(?:\[[^\]]+\])?)\s+(' + status_keywords + r')')

    summary_line_regex = re.compile(r'^(?:' + status_keywords + r')\s+[^\s]+::(test_[^\s]+)')

    setup_error_header_regex = re.compile(r'ERROR at setup of\s+(test_[\w_]+(?:\[[^\]]+\])?)')

    collected_status = {}

    for line in lines:
        m = test_line_regex.search(line)
        if m:
            full_name = m.group(1)
            status = m.group(2)
            func_name = re.sub(r'\[[^\]]+\]$', '', full_name)
            collected_status[func_name] = status
            continue

        # Fallback to short summary lines when main lines aren't present
        sm = summary_line_regex.search(line.strip())
        if sm:
            full_name = sm.group(1)
            func_name = re.sub(r'\[[^\]]+\]$', '', full_name)
            # The status is at the start of the line
            status_match = re.match(r'^(' + status_keywords + r')\b', line.strip())
            if status_match:
                collected_status[func_name] = status_match.group(1)

    # Extract error/failure reasons from detailed sections
    summary_start = next((i for i, line in enumerate(lines) if 'short test summary' in line), len(lines))

    failure_reasons = {}

    failure_headers = [i for i, line in enumerate(lines) if re.search(r'=+\s*FAILURES\s*=+', line)]
    for start_idx in failure_headers:
        block = '\n'.join(lines[start_idx + 1:summary_start])
        parts = re.split(r'_{5,}\s+(test_[\w_]+(?:\[[^\]]+\])?)\s+_{5,}', block)
        for i in range(1, len(parts) - 1, 2):
            full_test_name = parts[i]
            reason = parts[i + 1]
            func_name = re.sub(r'\[[^\]]+\]$', '', full_test_name)
            failure_reasons[func_name] = reason.strip()

    # Parse ERRORS block(s), including setup errors
    error_headers = [i for i, line in enumerate(lines) if re.search(r'=+\s*ERRORS\s*=+', line)]
    for start_idx in error_headers:
        block = '\n'.join(lines[start_idx + 1:summary_start])
        # Split by setup error headers
        # Keep the headers by using a capturing group in split
        parts = re.split(r'(?:\n|^)_{5,}.*?ERROR at setup of\s+(test_[\w_]+(?:\[[^\]]+\])?).*?_{5,}\s*\n', block)
        if len(parts) > 1:
            # parts looks like: [pre, test_name1, reason1, test_name2, reason2, ...]
            for i in range(1, len(parts) - 1, 2):
                full_test_name = parts[i]
                reason = parts[i + 1]
                func_name = re.sub(r'\[[^\]]+\]$', '', full_test_name)
                # Mark status as ERROR if not already set
                if func_name not in collected_status:
                    collected_status[func_name] = 'ERROR'
                # Save reason
                failure_reasons[func_name] = reason.strip()
        else:
            current_test = None
            reason_lines = []
            for line in block.split('\n'):
                m = setup_error_header_regex.search(line)
                if m:
                    if current_test and reason_lines:
                        func_name = re.sub(r'\[[^\]]+\]$', '', current_test)
                        if func_name not in collected_status:
                            collected_status[func_name] = 'ERROR'
                        failure_reasons[func_name] = '\n'.join(reason_lines).strip()
                        reason_lines = []
                    current_test = m.group(1)
                else:
                    reason_lines.append(line)
            if current_test and reason_lines:
                func_name = re.sub(r'\[[^\]]+\]$', '', current_test)
                if func_name not in collected_status:
                    collected_status[func_name] = 'ERROR'
                failure_reasons[func_name] = '\n'.join(reason_lines).strip()

    result = {}
    for name, status in collected_status.items():
        error_message = ''
        if status in ('FAILED', 'ERROR'):
            error_message = failure_reasons.get(name, '')
        result[name] = {'status': status, 'error_message': error_message}
    return result

def update_execution_result(case_data, execution_result):
    for case in case_data:
        case_id = case['id']
        mark_name = case['mark_name']
        if mark_name in execution_result:
            status = execution_result[mark_name]['status']
            error_message = execution_result[mark_name]['error_message']
            update_case_execution_sql = sqls['update_script_case_execution']
            update_case_execution_result = execute(update_case_execution_sql, (status, error_message, case_id))
            if update_case_execution_result:
                log.info('update script case execution info success')
            else:
                log.error(f'update script case execution info fail: {update_case_execution_result}')
            add_case_execution_results_sql = sqls['add_case_execution_results']
            add_case_execution_results = execute(add_case_execution_results_sql, (case_id, status, error_message))
            if add_case_execution_results:
                log.info('add case execution info success')
            else:
                log.error(f'add case execution info fail: {add_case_execution_results}')
        else:
            log.info(f'case {mark_name} no execution results')
    return True
def get_execution_result(data):
    query_sql = sqls['query_execution_result']
    result = fetch_one(query_sql, data)
    total = result['total']
    valid_num = result['valid_count']
    invalid_num = result['invalid_count']
    added_num = result['added_num']
    edit_num = result['edit_num']
    pass_num = result['pass_num']
    fail_num = result['fail_num']
    return {
            'total': total, 'valid_num': int(valid_num), 'pass_num': int(pass_num),
            'invalid_num': int(invalid_num), 'edit_num': int(edit_num),
            'fail_num': int(fail_num), 'added_num': int(added_num)}

def get_api_data(data):
    # api_data = []
    result = None
    url = data.get('api_swagger')
    title = data.get('api_title')
    query_swagger_sql = sqls['query_api_info']
    query_swagger_result = fetch_one(query_swagger_sql, url)
    if query_swagger_result:
        result = query_swagger_result['id']
        return result
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Swagger URL responded with {response.status_code}")
    try:
        swagger_json = response.json()
    except Exception as e:
        print("Raw response:", response.text)
        raise Exception(f"Invalid JSON from swagger URL: {str(e)}")
    # swagger_json = response.json()
    definitions = swagger_json.get("definitions", {})
    add_swagger_sql = sqls['add_api_info']
    params = (title, url)
    add_swagger_result = execute(add_swagger_sql, params)
    if add_swagger_result:
        query_swagger_sql = sqls['query_api_info']
        query_swagger_result = fetch_one(query_swagger_sql, url)
        if query_swagger_result:
            result = query_swagger_result['id']
            for path, methods in swagger_json.get('paths', {}).items():
                for method, details in methods.items():
                    if isinstance(details, dict) and details.get('deprecated', False):
                        log.info(f"skip deprecated API operation: {method.upper()} {path}")
                        continue
                    summary = details.get('summary', '')
                    raw_parameters = details.get('parameters', [])
                    expanded_parameters = []
                    for param in raw_parameters:
                        if param.get('in') == 'body' and 'schema' in param:
                            schema = param['schema']
                            expanded = expand_schema(schema, definitions)
                            expanded_parameters.extend(expanded)
                        else:
                            expanded_parameters.append(param)
                    responses = details.get('responses', {})
                    expanded_responses = {}
                    for code, resp in responses.items():
                        description = resp.get("description", "")
                        if "schema" in resp:
                            fields = expand_schema(resp["schema"], definitions)
                            expanded_responses[code] = {
                                "description": description,
                                "fields": fields
                            }
                        else:
                            expanded_responses[code] = {
                                "description": description
                            }

                    parameters_json = json.dumps(expanded_parameters, ensure_ascii=False)
                    responses_json = json.dumps(expanded_responses, ensure_ascii=False)
                    add_swagger_detail_sql = sqls['add_api_details']
                    detail_params = (query_swagger_result['id'], path, summary, method.upper(), parameters_json, responses_json)
                    add_swagger_detail_result = execute(add_swagger_detail_sql, detail_params)
                    if add_swagger_detail_result:
                        log.info("save api details success")
                    else:
                        log.info("save api details fail")
    return result

def query_api_info(id):
    sql=sqls['query_api_info_by_id']
    result = fetch_one(sql, id)
    return result
def query_api_detail(id):
    params = (id)
    query_sql = sqls['query_api_details']
    rows = fetch_all(query_sql, params)
    result = []
    query_total_sql = sqls['query_api_num']
    total = fetch_one(query_total_sql, id)['total']
    api_swagger = query_api_info(id)['swagger_url']
    api_title = query_api_info(id)['title']
    query_used_sql = sqls['query_used_api_num']
    used = fetch_one(query_used_sql, id)['generated_count']
    unused = total - used
    for row in rows:
        try:
            row['parameters'] = json.loads(row['parameters']) if row['parameters'] else []
        except json.JSONDecodeError:
            row['parameters'] = []

        try:
            row['responses'] = json.loads(row['responses']) if row['responses'] else {}
        except json.JSONDecodeError:
            row['responses'] = {}

        result.append(row)

    return {'result': result, 'total': total, 'used': used, 'unused': unused,
            'api_swagger': api_swagger, 'api_title':api_title}

def query_scenario_list(id):
    params = (id)
    query_sql = sqls['query_test_scenario']
    result = fetch_all(query_sql, params)
    query_num_sql = sqls['query_scenario_num']
    query_num_result = fetch_one(query_num_sql, (id))
    print("query_num_result", query_num_result)
    total = query_num_result['total']
    valid_num = query_num_result['valid_count']
    invalid_num = query_num_result['invalid_count']
    added_num = query_num_result['added_num']
    edit_num = query_num_result['edit_num']
    query_used_sql = sqls['query_used_scenario_num']
    used = fetch_one(query_used_sql, id)['generated_count']
    unused = total - used
    group_sql = sqls["query_group_by_id"]
    group_result = fetch_one(group_sql, id)
    api_ids = json.loads(group_result["apis"])
    print("api_ids", api_ids)
    placeholder = ", ".join(["%s"] * len(api_ids))
    api_sql = sqls["query_api"].format(placeholder)
    api_info = fetch_all(api_sql, tuple(api_ids))
    print("api_info", api_info)
    api_swagger = query_api_info(api_info[0]['swagger_id'])['swagger_url']
    api_title = query_api_info(api_info[0]['swagger_id'])['title']
    return {"scenario_list": result, "api_info": api_info,
            'total': total, 'api_swagger': api_swagger,'used': used, 'unused': unused,
            'api_title': api_title, 'valid_num': int(valid_num), 'edit_num': int(edit_num),
            'invalid_num': int(invalid_num), 'added_num': int(added_num), "group_result": group_result}

def add_api_group(data):
    api_ids = [api['id'] for api in data['selected_apis']]
    api_ids_sorted = sorted(api_ids)
    api_ids_json = json.dumps(api_ids_sorted)
    group_name = data.get('group_name')
    scenario_type = data.get('type')
    # result = fetch_one(sql, api_ids_json)
    # print("check error result", result)
    # if result:
    #     return result['id']
    add_sql = sqls["add_group"]
    add_res = execute(add_sql, (api_ids_json, group_name, scenario_type))
    new_result = None
    if add_res:
        log.info("save group apis success")
        sql = sqls["query_group"]
        new_result = fetch_one(sql, api_ids_json)
        print("check error new result", new_result)
        group_api_relations_sql = sqls['add_group_relations']
        for i in api_ids:
            add_group_api_relations = execute(group_api_relations_sql, (new_result["id"], i))
            if add_group_api_relations:
                log.info(f"save group api relations success: {add_group_api_relations}")
            else:
                log.error(f"save group api relations fail: {add_group_api_relations}")
        return new_result["id"]
    log.info("save group apis fail")
    return new_result

def generate_test_scenario(data):
    result = add_api_group(data)
    scenario_type = data.get('type')
    if scenario_type:
        # generate system level test scenario to evaluate metrics
        prompt = get_prompt("generate_system_scenario_prompt", data)
        print("---generate_system_scenario_prompt: ", prompt)
        print("-------")
    else:
        print('scenario_type is', scenario_type)
        # generate none system level test scenario to evaluate metrics
        prompt = get_prompt("generate_test_scenario_prompt", data)
        print("---generate_test_scenario_prompt: ", prompt)
        print("-------")
    if result:
        # query_sql = sqls["check_test_scenario"]
        # query_result = fetch_one(query_sql, verify_result)
        # if query_result:
        #     return verify_result
        # prompt = get_prompt("generate_test_scenario_prompt", data)
        model = data.get('model_name')
        model_version = data.get('model_version')
        scenario = None
        if model == "ChatGPT":
            scenario = call_openai(prompt, model_version)
        if model == "DeepSeek":
            scenario = call_deepseek(prompt, model_version)
        group_id = result
        sql = sqls["add_test_scenario"]
        # Normalize model output: strip code fences/preamble and parse robustly
        if scenario:
            scenario = scenario.strip()
            if scenario.startswith("```"):
                scenario = re.sub(r"^```(?:\w+)?\n?", "", scenario)
                scenario = re.sub(r"```$", "", scenario.strip())
            # Drop any leading text before the first enumerated scenario item
            start_match = re.search(r"\d+\.\s*Scenario Name:\s*", scenario, flags=re.IGNORECASE)
            if start_match:
                scenario = scenario[start_match.start():]

        # Parse items like:
        # 1. Scenario Name: <title>\n   Scenario Description: <desc...>
        pattern = re.compile(
            r"^\s*\d+\.\s*Scenario Name:\s*(?P<title>.+?)\s*(?:\r?\n)+\s*Scenario Description:\s*(?P<desc>.*?)(?=(?:\r?\n)+\s*\d+\.\s*Scenario Name:|$)",
            re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        matches = [(None, m.group('title'), m.group('desc')) for m in pattern.finditer(scenario or "")]
        if not matches:
            log.error("No matches found in scenario text. Raw content:")
            log.error(repr(scenario))
        for num, title, description in matches:
            title = title.strip()
            description = re.sub(r"\s+", " ", description.strip())
            print(f"Saving scenario: {title}")
            res = execute(sql, (group_id, title, description, description, model, model_version, scenario_type))
            if res:
                log.info(f"save scenario title success: {title}")
                log.info(f"save scenario description success: {description}")
            else:
                log.info(f"save scenario fail: {title}")
                log.info(f"save scenario description fail: {description}")
        return group_id
    return None

def edit_test_scenario(data):
    id = data.get("id")
    title = data.get("edit_title")
    description = data.get("edit_description")
    sql = sqls["update_test_scenario"]
    result = execute(sql, (title,description, id))
    if result:
        log.info("update scenario success")
        return True
    log.info("update scenario fail")
    return False
def update_test_scenario_status(data):
    id = data.get("id")
    status = data.get("status")
    sql = sqls["update_test_scenario_status"]
    result = execute(sql, (status, id))
    if result:
        log.info("update scenario status success")
        return True
    log.info("update scenario status fail")
    return False
def add_test_scenario(data):
    group_id = data.get("group_id")
    title = data.get("title")
    description = data.get('description')
    scenario_type = data.get('scenario_type')
    model_name = ""
    if data.get("model_name"):
        model_name = data.get("model_name")
    model_version = ""
    if data.get("model_version"):
        model_version = data.get("model_version")
    check_sql = sqls["query_scenario_by_scenario"]
    check_result = fetch_one(check_sql, (group_id, title, description))
    if check_result:
        return {'success': False, 'message': 'Scenario already exists'}
    sql = sqls["add_test_scenario"]
    result = execute(sql, (group_id, title, description, description, model_name, model_version, scenario_type))
    if result:
        log.info("add new scenario success")
        return {'success': True}
    log.info("add scenario fail")
    return {'success': False}



def load_generation_list(offset, page_size):
    query_list_sql = sqls['query_generation_list']
    query_total_sql = sqls['query_list_num']
    params = (page_size, offset)
    result = fetch_all(query_list_sql, params)
    total = fetch_one(query_total_sql)['total']
    return {'result': result, 'total': total}

def extract_script_head(script: str):
    lines = script.splitlines()
    head_lines = []
    buffer = []
    collecting_decorator = False
    for i in range(len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if collecting_decorator:
                buffer.append(line)
            else:
                head_lines.append(line)
            continue
        # decorators
        if stripped.startswith("@"):
            buffer.append(line)
            collecting_decorator = True
            continue
        # function
        func_match = re.match(r"def\s+(\w+)\s*\(", stripped)
        if func_match:
            func_name = func_match.group(1)
            if collecting_decorator:
                # Check if the function starts with test_
                if func_name.startswith("test_"):
                    buffer = []
                    collecting_decorator = False
                    break
                else:
                    buffer.append(line)
                    head_lines.extend(buffer)
                    buffer = []
                    collecting_decorator = False
                    continue
            elif func_name.startswith("test_"):
                break
            else:
                head_lines.append(line)
                continue
        # If we're collecting decorator content and this line doesn't start with @ or def,
        # it's part of the decorator (like multi-line parameters)
        if collecting_decorator:
            buffer.append(line)
            continue
        head_lines.append(line)
    return "\n".join(head_lines)

def query_detail(id):
    query_detail_sql = sqls['query_generation_detail']
    script_result = fetch_one(query_detail_sql, id)
    case_result = None
    metrics_result = None
    if script_result:
        log.info("query script detail success")
        script_header = extract_script_head(script_result['last_version'])
        print('script_header', script_header)
        script_result['script_header'] = script_header
        # print('script_result', script_result)
        # query script case detail
        query_case_sql = sqls['query_script_case_detail']
        script_id = script_result['id']
        case_result = fetch_all(query_case_sql, (script_id, id))
        if case_result:
            log.info("query script case detail success")
        else:
            log.error(f"query script case detail fail{case_result}")
        query_metrics_sql = sqls['query_script_metrics']
        metrics_result = fetch_one(query_metrics_sql, script_id)
        if metrics_result:
            log.info("query script metrics success")
        else:
            log.error(f"query script metrics fail{metrics_result}")
    else:
        log.error(f"query script  detail success{script_result}")

    return {'script_result': script_result, 'case_result': case_result, 'metrics_result': metrics_result}

def query_script_group_detail(id):
    query_detail_sql = sqls['query_script_group_detail']
    result = fetch_all(query_detail_sql, id)
    return result

def update_generation_script(data):
    id = data.get("id")
    script = data.get("script")
    syntax_check_result = data.get('syntax_check_result')
    # update syntax check result
    script_syntax_result = 100.0
    if syntax_check_result:
        query_script_case_sql = sqls['query_script_case_num']
        query_script_case_result = fetch_one(query_script_case_sql, id)
        total = query_script_case_result['total']
        valid_num = int(query_script_case_result['valid_count'] or 0)
        script_syntax_result = round(valid_num / total * 100, 2)
    # query script detail
    query_detail_sql = sqls['query_script_detail_by_id']
    script_result = fetch_one(query_detail_sql, (id))
    selected_apis = script_result['spec_url']
    selected_apis_list = json.loads(selected_apis)
    model = script_result['model_name']
    model_version = script_result['model_version']
    scenario = script_result['test_scenario']
    parameter_context = {
        'selected_apis': selected_apis,
        'generated_script': script,
        'scenario': scenario
    }
    # check test script status code coverage
    # status_code_coverage, status_code_coverage_detail = check_status_code_coverage_by_script(parameter_context, model,
    #                                                                                          model_version)
    # status_code_coverage = round(overall_coverage, 2)
    # converted_detail = convert_sets_to_lists(coverage_detail)
    # status_code_coverage_detail = json.dumps(converted_detail, ensure_ascii=False)
    # check test script data type correctness
    data_type_coverage, data_type_detail = calculate_data_type_coverage(parameter_context, model, model_version)
    # check test script method coverage
    method_coverage, method_coverage_detail = calculate_method_coverage(parameter_context, model, model_version)
    sql = sqls["update_generation_detail"]
    result = execute(sql, (script, script_syntax_result, data_type_coverage, data_type_detail, method_coverage,
                           method_coverage_detail, id))
    if result:
        log.info("update script success")
        return True
    log.info("update script fail")
    return False

def update_case_detail(data):
    id = data.get("id")
    case = data.get("case_detail")
    script_id = data.get("script_id")
    new_mark_name = data.get("new_mark_name")
    old_mark_name = data.get("old_mark_name")
    # check script syntax
    check_script_syntax = check_syntax(case)
    if check_script_syntax:
        syntax_check_result = 0
    else:
        syntax_check_result = 1
    sql = sqls["update_script_case_detail"]
    result = execute(sql, (case, new_mark_name, syntax_check_result, id))
    if result:
        log.info("update script case success")
        query_full_script_sql = sqls['query_full_script']
        full_script = fetch_one(query_full_script_sql, script_id)['last_version']
        new_full_script = replace_case_function_body(full_script, old_mark_name, case)
        update_data = {'id': script_id,
                       'script': new_full_script,
                       'syntax_check_result': syntax_check_result}
        update_full_script = update_generation_script(update_data)
        if update_full_script:
            log.info("update full script success")
            return True
        else:
            log.error(f"update full script fail:{update_full_script}")
    log.info("update script case fail")
    return False


def replace_case_function_body(script_text, target_mark_name, new_func_code):
    if not script_text.endswith("\n"):
        script_text += "\n"

    lines = script_text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("@"):
            decorator_start = i
            # Advance through decorator block (including multi-line arguments and consecutive decorators)
            pos = i
            while pos < len(lines):
                s = lines[pos].lstrip()
                if s.startswith("def "):
                    break
                # Allow consecutive decorators
                if s.startswith("@") and pos != decorator_start:
                    # keep scanning to reach the function definition
                    pos += 1
                    continue
                # Continue through decorator argument lines
                pos += 1

            # pos now at def or end
            if pos < len(lines) and re.match(rf'^\s*def\s+{re.escape(target_mark_name)}\s*\(', lines[pos]):
                start = decorator_start
                i = pos + 1  # move past def line
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() == "":
                        i += 1
                        continue
                    if not lines[i].startswith(" ") and not lines[i].startswith("\t"):
                        break
                    i += 1
                end = i

                # Replace the entire function (including decorators)
                before = "".join(lines[:start])
                after = "".join(lines[end:])
                if not new_func_code.endswith("\n"):
                    new_func_code += "\n"
                updated_script = before + new_func_code + after
                return updated_script
            else:
                # Advance to continue scanning safely
                i = max(pos, i + 1)
                continue
        else:
            # Check if this is target function without decorators (match by function name only)
            if re.match(rf'^\s*def\s+{re.escape(target_mark_name)}\s*\(', stripped):
                # Found target function without decorators
                start = i
                i += 1  # Skip the def line
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() == "":
                        i += 1
                        continue
                    if not lines[i].startswith(" ") and not lines[i].startswith("\t"):
                        break
                    i += 1
                end = i
                
                # Replace the function
                before = "".join(lines[:start])
                after = "".join(lines[end:])
                if not new_func_code.endswith("\n"):
                    new_func_code += "\n"
                updated_script = before + new_func_code + after
                return updated_script
            i += 1

    # If function not found, return original script unchanged
    return script_text

def add_case_to_script(script_text, new_func_code):
    """
    script_text: original script
    new_mark: "function name"
    new_func_code: new function body
    """
    return script_text.rstrip() + "\n\n" + new_func_code.rstrip() + "\n"

def delete_case_from_script(script_text, target_func_name):
    """
    remove test case by function name (including decorators)
    target_func_name: function name to delete
    """
    lines = script_text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if this line starts with @ (decorator)
        if stripped.startswith("@"):
            decorator_start = i
            # Collect all decorator lines (including multi-line decorators)
            while i < len(lines):
                current_line = lines[i]
                current_stripped = current_line.strip()
                
                if current_stripped.startswith("@"):
                    break
                
                if re.match(r'^\s*def\s+\w+', current_stripped):
                    if re.match(rf'^\s*def\s+{re.escape(target_func_name)}\s*\(', current_stripped):
                        break
                    else:
                        i += 1
                        continue
                
                i += 1
            
            if i < len(lines) and re.match(rf'^\s*def\s+{re.escape(target_func_name)}\s*\(', lines[i]):
                start = decorator_start
                i += 1  # Skip the def line
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() == "":
                        i += 1
                        continue
                    if not lines[i].startswith(" ") and not lines[i].startswith("\t"):
                        break
                    i += 1
                end = i
                
                before = "".join(lines[:start])
                after = "".join(lines[end:])
                updated_script = before + after
                return updated_script.strip() + '\n'
            else:
                continue
        else:
            if re.match(rf'^\s*def\s+{re.escape(target_func_name)}\s*\(', stripped):
                start = i
                i += 1  # Skip the def line
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() == "":
                        i += 1
                        continue
                    if not lines[i].startswith(" ") and not lines[i].startswith("\t"):
                        break
                    i += 1
                end = i
                
                # Remove the function
                before = "".join(lines[:start])
                after = "".join(lines[end:])
                updated_script = before + after
                return updated_script.strip() + '\n'
            i += 1
    
    # If function not found, return original script
    return script_text.strip() + '\n'

def add_script_case(data):
    script_id = data.get('script_id')
    scenario_id = data.get('scenario_id')
    case_code = data.get('case_detail')
    mark_name = data.get('mark_name')
    # check script syntax
    check_script_syntax = check_syntax(case_code)
    if check_script_syntax:
        syntax_check_result = 0
    else:
        syntax_check_result = 1
    add_script_case_sql = sqls['add_script_case_detail']
    source_type = "MANUAL"
    add_script_case_res = execute(add_script_case_sql, (script_id, scenario_id, mark_name,
                                                        case_code, case_code, source_type, syntax_check_result))
    if add_script_case_res:
        log.info(f"add script case success: {add_script_case_res}")
        # add new case script to full script
        query_full_script_sql = sqls['query_full_script']
        full_script = fetch_one(query_full_script_sql, script_id)['last_version']
        new_full_script = add_case_to_script(full_script, case_code)
        print('new_full_script', new_full_script)
        update_data = {'id': script_id,
                       'script': new_full_script,
                       'syntax_check_result': syntax_check_result}
        update_full_script = update_generation_script(update_data)
        if update_full_script:
            log.info("update full script success")
            return True
        else:
            log.info("update full script fail")
        log.error(f"add script case fail: {add_script_case_res}")
        return False

def update_test_case_status(data):
    id = data.get("id")
    script_id = data.get("script_id")
    mark_name = data.get("func_name")
    status = 1
    sql = sqls["update_script_case_status"]
    result = execute(sql, (status, id))
    if result:
        log.info("update case status to invalid success")
        # update full script case
        query_full_script_sql = sqls['query_full_script']
        full_script = fetch_one(query_full_script_sql, script_id)['last_version']
        new_full_script = delete_case_from_script(full_script, mark_name)
        update_data = {'id': script_id,
                       'script': new_full_script}
        update_full_script = update_generation_script(update_data)
        if update_full_script:
            log.info("update full script success")
            return True
        else:
            log.error(f"update full script fail:{update_full_script}")
    log.info("update script case status to invalid fail")
    return False

def undo_test_case_status(data):
    id = data.get("id")
    script_id = data.get("script_id")
    case = data.get("case_detail")
    status = 0
    sql = sqls["update_script_case_status"]
    result = execute(sql, (status, id))
    if result:
        log.info("update case status to valid success")
        # update full script case
        query_full_script_sql = sqls['query_full_script']
        full_script = fetch_one(query_full_script_sql, script_id)['last_version']
        new_full_script = add_case_to_script(full_script, case)
        update_data = {'id': script_id,
                       'script': new_full_script}
        update_full_script = update_generation_script(update_data)
        if update_full_script:
            log.info("update full script success")
            return True
        else:
            log.error(f"update full script fail:{update_full_script}")
    log.info("undo script case status to valid fail")
    return False

def update_case_execution_fail_reason(data):
    id = data.get("id")
    type = data.get("type")
    sql = sqls["update_case_execution_fail_reason"]
    result = execute(sql, (type, id))
    if result:
        log.info("update case execution fail reason success")
        update_case_fail_reason_sql = sqls["update_script_case_execution_fail_reason"]
        update_case_fail_reason_result = execute(update_case_fail_reason_sql, (type, id))
        if update_case_fail_reason_result:
            log.info("update case execution last time fail reason success")
            return True
        else:
            log.info(f"update case execution last time fail reason fail:{update_case_fail_reason_result}")
            return False
    log.info("update case execution fail reason fail")
    return False

def set_data_type_metrics(data):
    script_id = data.get('id')
    status = data.get('status')
    metrics_sql = sqls['set_data_type_metrics']
    result = execute(metrics_sql, (status, script_id))
    if result:
        return True
    return False

def set_method_coverage_metrics(data):
    script_id = data.get('id')
    status = data.get('status')
    metrics_sql = sqls['set_method_coverage_metrics']
    result = execute(metrics_sql, (status, script_id))
    if result:
        return True
    return False

def set_status_coverage_metrics(data):
    script_id = data.get('id')
    status = data.get('status')
    metrics_sql = sqls['set_status_code_metrics']
    result = execute(metrics_sql, (status, script_id))
    if result:
        return True
    return False
def set_syntax_metrics(data):
    script_id = data.get('id')
    status = data.get('status')
    metrics_sql = sqls['set_syntax_metrics']
    result = execute(metrics_sql, (status, script_id))
    if result:
        return True
    return False

def set_data_type_metrics_value(data):
    script_id = data.get('script_id')
    value = data.get('value')
    metrics_sql = sqls['set_data_type_metrics_last']
    result = execute(metrics_sql, (value, script_id))
    if result:
        return True
    return False

def set_method_coverage_metrics_value(data):
    script_id = data.get('script_id')
    value = data.get('value')
    metrics_sql = sqls['set_method_coverage_metrics_last']
    result = execute(metrics_sql, (value, script_id))
    if result:
        return True
    return False

def set_status_coverage_metrics_value(data):
    script_id = data.get('script_id')
    value = data.get('value')
    metrics_sql = sqls['set_status_code_metrics_last']
    result = execute(metrics_sql, (value, script_id))
    if result:
        return True
    return False

def update_script_review_status(data):
    script_id = data.get('script_id')
    metrics_sql = sqls['update_script_review_status']
    result = execute(metrics_sql, (script_id))
    if result:
        return True
    return False






