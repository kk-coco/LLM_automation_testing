import re
import os
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
def call_openai(prompt):
    openai.api_key = OPENAI_API_KEY
    start_time = time.time()
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    end_time = time.time()
    response_time = round(end_time - start_time, 3)
    content = response.choices[0].message.content

    return content

def call_deepseek(prompt):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    start_time = time.time()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{
            "role": "user",
            "content": prompt},
        ],
        temperature= 0.0,
        stream=False
    )
    # print(response.choices[0].message.content)
    content = response.choices[0].message.content
    # response = requests.post(url, headers=headers, json=data)
    end_time = time.time()
    response_time = round(end_time - start_time, 3)
    # response_json = response.json()
    # output_content = response_json["choices"][0]["message"]["content"]
    # input_tokens = response_json["usage"]["prompt_tokens"]
    # output_tokens = response_json["usage"]["completion_tokens"]

    return content

def save_script(data, script):
    sql = sqls['add_generate_script']
    query_sql = sqls['query_generate_script']
    spec_url = data.get("api_spec")
    test_scenario = data.get("test_scenario")
    model_name = data.get("model_name")
    params = (spec_url, test_scenario, model_name, script)
    save_result = execute(sql, params)
    query_params = (spec_url, test_scenario, model_name)
    result = None
    if save_result:
        result = fetch_one(query_sql, query_params)
        log.info(f"check result after query: {result}")
    return result


def generate_test_script(data):
    prompt = get_prompt("generate_test_case_prompt1", data)
    model = data.get('model_name')
    script = None
    result = None
    if model == "ChatGPT":
        script = call_openai(prompt)
    if model == "DeepSeek":
        script = call_deepseek(prompt)
    if script:
        if script.startswith("```"):
            script = re.sub(r"```(?:python)?\n?", "", script)
            script = re.sub(r"```$", "", script.strip())
        result = save_script(data, script)
        log.info(f"check result after save: {result}")
    return result

def edit_test_script(data):
    prompt = get_prompt("generate_test_case_prompt1", data)
    model = data.get('model')
    if model == "ChatGPT":
        res = call_openai(prompt)
    elif model == "DeepSeek":
        res = call_deepseek(prompt)
    else:
        res = None
    return res



