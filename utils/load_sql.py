import os
import yaml

def load_all_sql():
    path = os.path.join(os.path.dirname(__file__), '../sql/api_sql.yaml')
    with open(path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

