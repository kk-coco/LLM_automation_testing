import re
import os
import subprocess
import tempfile

from dotenv import load_dotenv
from openai import OpenAI
from utils.db import execute, fetch_one
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
            {"role": "system", "content": "You are a senior Python testing engineer. Only return clean pytest scripts without any explanations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
    )
    end_time = time.time()
    response_time = round(end_time - start_time, 3)
    content = response.choices[0].message.content

    return content

def call_deepseek(prompt, model_version):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    start_time = time.time()
    response = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "You are a senior Python testing engineer. Only return clean pytest scripts without any explanations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        stream=False
    )
    # print(response.choices[0].message.content)
    content = response.choices[0].message.content

    return content

def save_script(data, script, prompt_name):
    sql = sqls['add_generate_script']
    query_sql = sqls['query_generate_script']
    spec_url = data.get("api_spec")
    test_scenario = data.get("test_scenario")
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
    prompt = get_prompt("generate_test_case_prompt1", data)
    model = data.get('model_name')
    model_version = data.get('model_version')
    prompt_name = "generate_test_case_prompt1"
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
        result = save_script(data, script,prompt_name)
        log.info(f"check result after save: {result}")
    return result

def edit_test_script(data):
    id = data.get('taskId')
    script = data.get('editScript')

def execute_test_script(data):
    # id = data.get('taskId')
    response_result = {}
    script_code = data.get('editScript')
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
    return response_result





