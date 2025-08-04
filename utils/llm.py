import os
import time
import openai
from openai import OpenAI

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