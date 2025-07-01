import os
import yaml
from jinja2 import Template


def load_all_prompts():
    path = os.path.join(os.path.dirname(__file__), '../prompts/prompts.yaml')
    with open(path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)
def render_template(template_str, context):
    template = Template(template_str)
    return template.render(**context)
def get_prompt(template_name, context):
    prompts = load_all_prompts()
    template = prompts.get(template_name)
    if not template:
        raise ValueError(f"Prompt template '{template_name}' not found.")

    system_prompt = render_template(template.get("system", ""), context)
    user_prompt = render_template(template.get("user", ""), context)

    return {
        "system": system_prompt,
        "user": user_prompt
    }
