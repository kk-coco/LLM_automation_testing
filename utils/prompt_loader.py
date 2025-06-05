import os
import yaml

def load_all_prompts():
    path = os.path.join(os.path.dirname(__file__), '../prompts/prompts.yaml')
    with open(path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def get_prompt(template_name, context):
    prompts = load_all_prompts()
    template = prompts.get(template_name)
    if not template:
        raise ValueError(f"Prompt template '{template_name}' not found.")

    for key, value in context.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template
