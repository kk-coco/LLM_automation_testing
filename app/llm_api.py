from flask import Blueprint, request
from services.api_service import (generate_test_script, execute_test_script,get_api_data, update_script_review_status,
                                  generate_test_scenario, load_generation_list, query_detail, get_execution_result,
                                  query_api_detail, query_scenario_list, edit_test_scenario, add_test_scenario,
                                  update_test_scenario_status, update_generation_script, query_script_group_detail,
                                  update_case_detail, add_script_case, update_test_case_status, undo_test_case_status,
                                  update_case_execution_fail_reason, set_data_type_metrics, set_syntax_metrics,
                                  set_method_coverage_metrics, set_status_coverage_metrics, set_data_type_metrics_value,
                                  set_method_coverage_metrics_value, set_status_coverage_metrics_value)
from utils.response import json_response
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
        result = query_api_detail(id)
        return json_response({'data': result['result'], 'total': result['total'], 'used': result['used'],
                              'unused': result['unused'], 'api_title': result['api_title'],
                              'api_swagger': result['api_swagger']})
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
@llm_automation.route('/update_scenario_status', methods=['POST'])
def update_scenario():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = update_test_scenario_status(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/get_scenario_list', methods=['GET'])
def get_scenario_list():
    try:
        id = int(request.args.get('id'))
        # page = int(request.args.get('page', 1))
        # page_size = int(request.args.get('page_size', 10))
        # offset = (page - 1) * page_size
        result = query_scenario_list(id)
        return json_response({'scenario_list': result['scenario_list'], 'api_info': result['api_info'],
                              'group_info': result['group_result'],
                              'total': result['total'], 'api_title': result['api_title'], 'used': result['used'],'unused': result['unused'],
                              'api_swagger': result['api_swagger'], 'valid_num': result['valid_num'], 'edit_num': result['edit_num'],
                              'invalid_num': result['invalid_num'], 'added_num': result['added_num']})

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
        result = generate_test_script(data)
        return json_response({'id': result})
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
        return json_response({'result': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/get_script_group_detail', methods=['GET'])
def get_script_group_detail():
    try:
        id = int(request.args.get('id'))
        result = query_script_group_detail(id)
        return json_response({'data': result})
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
        return json_response({'script_result': result['script_result'], 'case_result': result['case_result'],
                              'metrics_result': result['metrics_result']})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/update_detail', methods=['POST'])
def update_generation_result():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = update_generation_script(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/save_script_case', methods=['POST'])
def save_script_case():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = add_script_case(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/update_script_case', methods=['POST'])
def update_script_case():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = update_case_detail(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/update_case_status', methods=['POST'])
def update_case_status():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = update_test_case_status(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/undo_case_status', methods=['POST'])
def undo_case_status():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = undo_test_case_status(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/set_fail_reason', methods=['POST'])
def set_fail_reason():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = update_case_execution_fail_reason(data)
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

@llm_automation.route('/update_data_type_metrics', methods=['POST'])
def update_data_type_metrics():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_data_type_metrics(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/update_syntax_metrics', methods=['POST'])
def update_syntax_metrics():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_syntax_metrics(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/update_method_coverage_metrics', methods=['POST'])
def update_method_coverage_metrics():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_method_coverage_metrics(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/update_status_coverage_metrics', methods=['POST'])
def update_status_coverage_metrics():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_status_coverage_metrics(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/update_data_type_metrics_value', methods=['POST'])
def update_data_type_metrics_value():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_data_type_metrics_value(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/update_method_coverage_metrics_value', methods=['POST'])
def update_method_coverage_metrics_value():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_method_coverage_metrics_value(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500
@llm_automation.route('/update_status_code_metrics_value', methods=['POST'])
def update_status_code_metrics_value():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = set_status_coverage_metrics_value(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500

@llm_automation.route('/mark_script_reviewed', methods=['POST'])
def mark_script_reviewed():
    data = request.json
    if not isinstance(data, dict):
        return json_response({'error': 'Missing input data'}), 400
    try:
        result = update_script_review_status(data)
        return json_response({'data': result})
    except Exception as e:
        return json_response({'error': str(e)}), 500