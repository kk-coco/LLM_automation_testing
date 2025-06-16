from flask import Blueprint, request
from services.api_service import generate_test_script, edit_test_script, execute_test_script
from utils.response import json_response

llm_automation = Blueprint('api', __name__)

@llm_automation.route('/generate', methods=['POST'])
def generate():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400

    try:
        test_script = generate_test_script(data)
        return json_response({'id':test_script['id'],'script': test_script['generated_script']})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/edit', methods=['POST'])
def edit():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400

    try:
        test_script = edit_test_script(data)
        return json_response({'script': test_script})
    except Exception as e:
        return json_response({'error': str(e)}), 500

# execute script
@llm_automation.route('/execute', methods=['POST'])
def execute():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400

    try:
        result = execute_test_script(data)
        return json_response({'result':result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
