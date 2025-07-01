from flask import Blueprint, request
from services.api_service import (generate_test_script, edit_test_script, execute_test_script,get_api_data,
                                  generate_test_scenario, load_generation_list, query_detail, get_execution_result,
                                  query_api_detail, query_scenario_list, edit_test_scenario, add_test_scenario)
from utils.response import json_response

llm_automation = Blueprint('api', __name__)

@llm_automation.route('/handle_api', methods=['POST'])
def handle_api():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = get_api_data(data)
        return json_response({'id': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/get_api_list', methods=['GET'])
def get_api_list():
    try:
        id = int(request.args.get('id'))
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        offset = (page - 1) * page_size
        result = query_api_detail(id, offset, page_size)
        return json_response({'data': result['result'], 'total': result['total']})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/generate_scenario', methods=['POST'])
def generate_scenario():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        group_id = generate_test_scenario(data)
        return json_response({'id': group_id})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/add_scenario', methods=['POST'])
def add_scenario():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = add_test_scenario(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/get_scenario_list', methods=['GET'])
def get_scenario_list():
    try:
        id = int(request.args.get('id'))
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        offset = (page - 1) * page_size
        result = query_scenario_list(id, offset, page_size)
        return json_response({'scenario_list': result['scenario_list'],'api_info':result['api_info'], 'total': result['total']})

    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/edit_scenario', methods=['POST'])
def edit_scenario():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = edit_test_scenario(data)
        return json_response({'result': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/generate_script', methods=['POST'])
def generate_script():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        test_script = generate_test_script(data)
        return json_response({'id': test_script['id'],'script': test_script['generated_script']})
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

@llm_automation.route('/get_generation_list', methods=['GET'])
def get_generation_list():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        offset = (page - 1) * page_size
        result = load_generation_list(offset, page_size)
        return json_response({'data': result['result'], 'total': result['total']})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/get_detail', methods=['GET'])
def get_generation_detail():
    try:
        id = int(request.args.get('id'))
        result = query_detail(id)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/query_execution_result', methods=['GET'])
def get_execution_detail():
    try:
        id = int(request.args.get('id'))
        result = get_execution_result(id)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500