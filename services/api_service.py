import json
import re
import os
import subprocess
import tempfile

import requests
from dotenv import load_dotenv
from openai import OpenAI
from utils.db import execute, fetch_one, fetch_all
import openai
import time

from utils.logging import Logger
from utils.prompt_loader import get_prompt
from utils.load_sql import load_all_sql
from utils.metrics import check_syntax, check_status_code_coverage, convert_sets_to_lists, expand_schema, \
    extract_json_from_markdown, calculate_method_coverage

sqls = load_all_sql()
log = Logger()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
def call_openai(prompt, model_version):
    openai.api_key = OPENAI_API_KEY
    start_time = time.time()
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": prompt['system']},
            {"role": "user", "content": prompt['user']}
        ],
        temperature=0.6,
    )
    end_time = time.time()
    response_time = round(end_time - start_time, 3)
    content = response.choices[0].message.content
    print("check path openai", content)

    return content

def call_deepseek(prompt, model_version):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    start_time = time.time()
    response = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": prompt['system']},
            {"role": "user", "content": prompt['user']}
        ],
        temperature=0.0,
        stream=False
    )
    # print(response.choices[0].message.content)
    content = response.choices[0].message.content
    print("check path deepseek", content)

    return content

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
        print("check error new result", new_result) #group info {'id': 1, 'scenarios': '[294]'}
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

def generate_test_script(data):
    selected_scenarios = data.get('selected_scenarios')
    group_id = add_scenario_group(selected_scenarios)
    print("check add_scenario_group result--", group_id) #result is 1
    selected_apis_list = data.get("selected_apis")
    selected_apis = json.dumps(data.get("selected_apis", []))
    print('api original', data.get("selected_apis"))
    print('api original type', type(data.get("selected_apis")))
    print('api', selected_apis)
    print('api type', type(selected_apis))
    model = data.get('model_name')
    model_version = data.get('model_version')
    prompt_name = "generate_test_case_prompt"
    script = None
    # print("-------", data.get('selected_scenarios'))
    for scenario in selected_scenarios:
        scenario_id = scenario['id']
        test_scenario = scenario['last_version']
        print('scenario', test_scenario)
        print('scenario id', scenario_id)
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
                script_syntax_result = 1.0
            print('script_syntax_result', script_syntax_result)
            # check test script status code coverage
            overall_coverage, coverage_detail = check_status_code_coverage(selected_apis_list, script)
            status_code_coverage = round(overall_coverage, 2)
            converted_detail = convert_sets_to_lists(coverage_detail)
            status_code_coverage_detail = json.dumps(converted_detail, ensure_ascii=False)
            # check test script method coverage
            method_coverage, method_coverage_detail = calculate_method_coverage(selected_apis_list, script)
            print('method_coverage', method_coverage)
            print('method_coverage_detail', method_coverage_detail)
            # check test script data type correctness
            parameter_context = {
                'selected_apis': selected_apis,
                'generated_script': script
            }
            check_result = None
            check_parameter_prompt = get_prompt("check_parameter_type_correctness", parameter_context)
            if model == "ChatGPT":
                check_result = call_openai(check_parameter_prompt, model_version)
            if model == "DeepSeek":
                check_result = call_deepseek(check_parameter_prompt, model_version)
            print('check result', check_result)
            print('check result type', type(check_result))
            result = extract_json_from_markdown(check_result)
            check_result_json = json.loads(result)
            data_type_coverage = check_result_json['coverage']
            print('check data_type_coverage type', type(data_type_coverage))
            print('check detail type', type(check_result_json['detail']))
            data_type_detail = json.dumps(check_result_json['detail'], ensure_ascii=False)
            print("conversion coverage:", data_type_coverage)
            print(" detail JSON after conversion:", data_type_detail)
            add_script_sql = sqls['add_generate_script']
            prompt_json = json.dumps(prompt)
            params = (group_id, selected_apis, scenario_id, test_scenario, model, model_version, prompt_json,
                      script, script, script_syntax_result, status_code_coverage, status_code_coverage_detail,
                      data_type_coverage, data_type_detail, method_coverage, method_coverage_detail)
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
                    pattern = re.compile(
                        r'^def\s+(test_\w+)\s*\(.*?\):\n'  
                        r'(?:^[ \t]+.*(?:\n|$))*'
                        , re.MULTILINE
                    )
                    func_names = []
                    case_blocks = []
                    for match in pattern.finditer(script_text):
                        func_names.append(match.group(1))
                        start_pos = match.start()
                        next_match = next(pattern.finditer(script_text, match.end()), None)
                        end_pos = next_match.start() if next_match else len(script_text)
                        case_blocks.append(script_text[start_pos:end_pos])
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
    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as tmp_file:
        tmp_file.write(script_code)
        tmp_path = tmp_file.name
    try:
        command = ["pytest", tmp_path, "-v", "--tb=short"]
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

    except subprocess.TimeoutExpired:
        response_result["success"] = False
        response_result["error"] = "Execution timed out"
        return {
            "success": False,
            "error": "Execution timed out"
        }
    sql = sqls['add_execution_result']
    params = (task_id, json.dumps(response_result, ensure_ascii=False))
    # print('sql', sql)
    # print('params', params)
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

    test_line_regex = re.compile(r'::(test_[\w_]+)\s+(PASSED|FAILED)')
    test_results = []
    for line in lines:
        match = test_line_regex.search(line)
        if match:
            test_results.append({
                'name': match.group(1),
                'status': match.group(2)
            })
    failure_start = next((i for i, line in enumerate(lines) if 'FAILURES' in line), -1)
    summary_start = next((i for i, line in enumerate(lines) if 'short test summary' in line), -1)

    failure_reasons = {}
    if failure_start != -1 and summary_start != -1:
        failure_block = '\n'.join(lines[failure_start + 1:summary_start])
        failure_cases = re.split(r'_{5,} (test_[\w_]+) _{5,}', failure_block)
        for i in range(1, len(failure_cases) - 1, 2):
            test_name = failure_cases[i]
            reason = failure_cases[i + 1]
            failure_reasons[test_name] = reason.strip()

    result = {}
    for test in test_results:
        name = test['name']
        status = test['status']
        error_message = failure_reasons.get(name, '') if status == 'FAILED' else ''
        result[name] = {'status': status, 'error_message': error_message}
    # print('result', result)
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
    title = data.get('title')
    query_swagger_sql = sqls['query_api_info']
    query_swagger_result = fetch_one(query_swagger_sql, url)
    if query_swagger_result:
        result = query_swagger_result['id']
        return result
    response = requests.get(url)
    swagger_json = response.json()
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
    print("result", result)
    query_num_sql = sqls['query_scenario_num']
    query_num_result = fetch_one(query_num_sql, id)
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
            'invalid_num': int(invalid_num), 'added_num': int(added_num)}

def add_api_group(data):
    api_ids = [api['id'] for api in data['selected_apis']]
    api_ids_sorted = sorted(api_ids)
    api_ids_json = json.dumps(api_ids_sorted)
    # result = fetch_one(sql, api_ids_json)
    # print("check error result", result)
    # if result:
    #     return result['id']
    add_sql = sqls["add_group"]
    add_res = execute(add_sql, api_ids_json)
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
    print("check error--", result)
    if result:
        # query_sql = sqls["check_test_scenario"]
        # query_result = fetch_one(query_sql, verify_result)
        # if query_result:
        #     return verify_result
        prompt = get_prompt("generate_test_scenario_prompt", data)
        print("---prompt: ", prompt)
        print("-------")
        model = data.get('model_name')
        model_version = data.get('model_version')
        scenario = None
        if model == "ChatGPT":
            print("check path chatgpt", model)
            scenario = call_openai(prompt, model_version)
        if model == "DeepSeek":
            print("check path deepseek", model)
            scenario = call_deepseek(prompt, model_version)
        print("check error--------")
        group_id = result
        sql = sqls["add_test_scenario"]
        print("check path1")
        matches = re.findall(r"(\d+)\.\s+(.*)", scenario)
        if not matches:
            log.error("No matches found in scenario text. Raw content:")
            log.error(repr(scenario))
        for num, title in matches:
            title = title.strip()
            print(f"Saving scenario: {title}")
            res = execute(sql, (group_id, title, title, model, model_version))
            if res:
                log.info(f"save scenario success: {title}")
            else:
                log.info(f"save scenario fail: {title}")
        return group_id
    return None

def edit_test_scenario(data):
    id = data.get("id")
    title = data.get("edit_title")
    sql = sqls["update_test_scenario"]
    result = execute(sql, (title, id))
    if result:
        log.info("update scenario success")
        return True
    log.info("update scenario fail")
    return False
def update_test_scenario_status(data):
    id = data.get("id")
    status = data.get("status")
    print('status', status)
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
    model_name = ""
    if data.get("model_name"):
        model_name = data.get("model_name")
    model_version = ""
    if data.get("model_version"):
        model_version = data.get("model_version")
    check_sql = sqls["query_scenario_by_scenario"]
    check_result = fetch_one(check_sql, (group_id, title))
    if check_result:
        return {'success': False, 'message': 'Scenario already exists'}
    sql = sqls["add_test_scenario"]
    result = execute(sql, (group_id, title, title, model_name, model_version))
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
    for line in lines:
        if line.strip().startswith("def test_"):
            break
        head_lines.append(line)
    return "\n".join(head_lines)

def query_detail(id):
    query_detail_sql = sqls['query_generation_detail']
    script_result = fetch_one(query_detail_sql, id)
    case_result = None
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
            log.error(f"query script case detail success{case_result}")
    else:
        log.error(f"query script  detail success{script_result}")

    return {'script_result': script_result, 'case_result': case_result}

def query_script_group_detail(id):
    query_detail_sql = sqls['query_script_group_detail']
    result = fetch_all(query_detail_sql, id)
    return result

def update_generation_script(data):
    id = data.get("id")
    script = data.get("script")
    sql = sqls["update_generation_detail"]
    result = execute(sql, (script, id))
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
    sql = sqls["update_script_case_detail"]
    result = execute(sql, (case, new_mark_name, id))
    if result:
        log.info("update script case success")
        query_full_script_sql = sqls['query_full_script']
        full_script = fetch_one(query_full_script_sql, script_id)['last_version']
        new_full_script = replace_case_function_body(full_script, old_mark_name, case)
        update_data = {'id': script_id,
                       'script': new_full_script}
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
    pattern = re.compile(
        rf'(def\s+{re.escape(target_mark_name)}\s*\(.*?\):\n(?:.*\n)*?)(?=^def\s|\Z)',
        re.MULTILINE
    )
    if not new_func_code.endswith("\n"):
        new_func_code += "\n"

    updated_script = pattern.sub(new_func_code, script_text)
    return updated_script

def add_case_to_script(script_text, new_func_code):
    """
    script_text: original script
    new_mark: "function name"
    new_func_code: new function body
    """
    return script_text.rstrip() + "\n\n" + new_func_code.rstrip() + "\n"

def delete_case_from_script(script_text, target_func_name):
    """
    remove test case by function name
    target_mark_name: "@pytest.mark.xxx"
    """
    pattern = re.compile(
        rf'def\s+{re.escape(target_func_name)}\s*\(.*?\):\n(?:[ \t]+.*\n?)+',
        re.MULTILINE
    )
    updated_script = pattern.sub('', script_text)
    return updated_script.strip() + '\n'

def add_script_case(data):
    script_id = data.get('script_id')
    scenario_id = data.get('scenario_id')
    case_code = data.get('case_detail')
    mark_name = data.get('mark_name')
    add_script_case_sql = sqls['add_script_case_detail']
    source_type = "MANUAL"
    add_script_case_res = execute(add_script_case_sql, (script_id, scenario_id, mark_name,
                                                        case_code, case_code, source_type))
    if add_script_case_res:
        log.info(f"add script case success: {add_script_case_res}")
        # add new case script to full script
        query_full_script_sql = sqls['query_full_script']
        full_script = fetch_one(query_full_script_sql, script_id)['last_version']
        new_full_script = add_case_to_script(full_script, case_code)
        update_data = {'id': script_id,
                       'script': new_full_script}
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








