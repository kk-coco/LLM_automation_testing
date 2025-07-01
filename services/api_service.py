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

def save_script(data, script, prompt_name):
    sql = sqls['add_generate_script']
    query_sql = sqls['query_generate_script']
    spec_url = json.dumps(data.get("selected_apis", []))
    test_scenario = json.dumps(data.get("selected_scenarios", []))
    model_name = data.get("model_name")
    model_version = data.get('model_version')
    params = (spec_url, test_scenario, model_name, model_version, prompt_name, script)
    save_result = execute(sql, params)
    query_params = (spec_url, test_scenario, model_name, model_version)
    result = None
    if save_result:
        result = fetch_one(query_sql, query_params)
        log.info(f"check result after query: {result}")
    return result


def generate_test_script(data):
    prompt = get_prompt("generate_test_case_prompt", data)
    print("---prompt: ", prompt)
    print("-------")
    model = data.get('model_name')
    model_version = data.get('model_version')
    prompt_name = "generate_test_case_prompt"
    script = None
    result = None
    if model == "ChatGPT":
        script = call_openai(prompt, model_version)
    if model == "DeepSeek":
        script = call_deepseek(prompt, model_version)
    if script:
        if script.startswith("```"):
            script = re.sub(r"```(?:python)?\n?", "", script)
            script = re.sub(r"```$", "", script.strip())
        result = save_script(data, script, prompt_name)
        log.info(f"check result after save: {result}")
    return result

def edit_test_script(data):
    id = data.get('taskId')
    script = data.get('editScript')

def execute_test_script(data):
    # id = data.get('taskId')
    response_result = {}
    script_code = data.get('script')
    task_id = data.get('task_id')
    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as tmp_file:
        tmp_file.write(script_code)
        tmp_path = tmp_file.name

    try:
        result = subprocess.run(
            ["pytest", tmp_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=30
        )
        response_result["success"] = result.returncode == 0
        response_result["stdout"] = result.stdout
        response_result["stderr"] = result.stderr
        response_result["returncode"] = result.returncode
        # return {
        #     "success": result.returncode == 0,
        #     "stdout": result.stdout,
        #     "stderr": result.stderr,
        #     "returncode": result.returncode
        # }
    except subprocess.TimeoutExpired:
        response_result["success"] = False
        response_result["error"] = "Execution timed out"
        return {
            "success": False,
            "error": "Execution timed out"
        }
    sql = sqls['add_execution_result']
    params = (task_id, json.dumps(response_result, ensure_ascii=False))
    save_result = execute(sql, params)
    if save_result:
        log.info("save execution result success")
    else:
        log.info("save execution result fail")
    return response_result

def get_execution_result(data):
    query_sql = sqls['query_execution_result']
    result = fetch_one(query_sql, data)
    return result

def get_api_data(data):
    # api_data = []
    result = None
    url = data.get('api_swagger')
    title = data.get('title')
    query_swagger_sql = sqls['query_api_info']
    query_swagger_result = fetch_one(query_swagger_sql, (title, url))
    if query_swagger_result:
        result = query_swagger_result['id']
        return result
    response = requests.get(url)
    swagger_json = response.json()
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
                    # api_info = {
                    #     "path": path,
                    #     "method": method.upper(),
                    #     "summary": details.get('summary', ''),
                    #     "parameters": details.get('parameters', []),
                    #     "responses": details.get('responses', {})
                    # }
                    summary = details.get('summary', '')
                    parameters = json.dumps(details.get('parameters', []), ensure_ascii=False)
                    responses = json.dumps(details.get('responses', {}), ensure_ascii=False)
                    # api_data.append(api_info)
                    add_swagger_detail_sql=sqls['add_api_details']
                    detail_params = (query_swagger_result['id'], path, summary, method.upper(), parameters, responses)
                    add_swagger_detail_result = execute(add_swagger_detail_sql, detail_params)
                    if add_swagger_detail_result:
                        log.info("save api details success")
                    else:
                        log.info("save api details fail")
    return result

def query_api_detail(id, offset, page_size):
    params = (id, page_size, offset)
    query_sql = sqls['query_api_details']
    rows = fetch_all(query_sql, params)
    result = []
    query_total_sql = sqls['query_api_num']

    total = fetch_one(query_total_sql)['total']

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

    return {'result': result, 'total': total}

def query_scenario_list(id, offset, page_size):
    params = (id, page_size, offset)
    query_sql = sqls['query_test_scenario']
    result = fetch_all(query_sql, params)
    print("result", result)
    query_total_sql = sqls['query_scenario_num']
    total = fetch_one(query_total_sql)['total']
    group_sql = sqls["query_group_apis_by_id"]
    group_result = fetch_one(group_sql, id)
    api_ids = json.loads(group_result["apis"])
    print("api_ids", api_ids)
    placeholder = ", ".join(["%s"] * len(api_ids))
    api_sql = sqls["query_api"].format(placeholder)
    api_info = fetch_all(api_sql, tuple(api_ids))
    print("api_info", api_info)
    return {"scenario_list": result, "api_info": api_info, 'total': total}

def verify_api_group(data):
    api_ids = [api['id'] for api in data['selected_apis']]
    api_ids_sorted = sorted(api_ids)
    api_ids_json = json.dumps(api_ids_sorted)
    sql = sqls["query_group_apis"]
    result = fetch_one(sql, api_ids_json)
    print("check error result", result)
    if result:
        return result['id']
    add_sql = sqls["add_group_apis"]
    add_res = execute(add_sql, api_ids_json)
    new_result = None
    if add_res:
        log.info("save group apis success")
        new_result = fetch_one(sql, api_ids_json)
        print("check error new result", new_result)
        return new_result["id"]
    log.info("save group apis fail")
    return new_result

def generate_test_scenario(data):
    verify_result = verify_api_group(data)
    print("check error--", verify_result)
    if verify_result:
        query_sql = sqls["query_test_scenario"]
        query_result = fetch_one(query_sql, verify_result)
        if query_result:
            return verify_result
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
        group_id = verify_result
        sql = sqls["add_test_scenario"]
        print("check path1")
        matches = re.findall(r"#### \*\*(\d+)\.\s*(.+?)\*\*", scenario)
        if not matches:
            log.error("No matches found in scenario text. Raw content:")
            log.error(repr(scenario))
        for num, title in matches:
            title = title.strip()
            print(f"Saving scenario: {title}")
            res = execute(sql, (group_id, title, model, model_version))
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

def add_test_scenario(data):
    group_id = data.get("group_id")
    title = data.get("title")
    check_sql = sqls["query_scenario_by_scenario"]
    check_result = fetch_one(check_sql, (group_id, title))
    if check_result:
        return {'success': False, 'message': 'Scenario already exists'}
    sql = sqls["add_test_scenario"]
    result = execute(sql, (group_id, title))
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

def query_detail(id):
    query_detail_sql = sqls['query_generation_detail']
    result = fetch_one(query_detail_sql, id)
    return result













