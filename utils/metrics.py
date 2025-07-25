import ast
import re
import json


def check_syntax(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def check_status_code_coverage(api_info, script):
    script_status_codes = set(re.findall(r'assert\s+response\.status_code\s*==\s*(\d+)', script))

    api_status_code_map = {}
    for api in api_info:
        path = api["api_path"]
        try:
            responses = json.loads(api["responses"])
        except Exception as e:
            print(f"Invalid responses JSON for {path}: {e}")
            continue
        codes = set(responses.keys())
        if codes:
            api_status_code_map[path] = codes

    coverage_report = {}
    total_expected_codes = 0
    total_matched_codes = 0

    for api_path, expected_codes in api_status_code_map.items():
        matched_codes = set(code for code in script_status_codes if code in expected_codes)
        coverage = len(matched_codes) / len(expected_codes) * 100 if expected_codes else 0
        coverage_report[api_path] = {
            "expected": expected_codes,
            "matched": matched_codes,
            "coverage_percent": round(coverage, 2)
        }
        total_expected_codes += len(expected_codes)
        total_matched_codes += len(matched_codes)

    overall_coverage = (total_matched_codes / total_expected_codes * 100) if total_expected_codes else 0.0
    overall_coverage = round(overall_coverage, 2)

    return overall_coverage, coverage_report


def convert_sets_to_lists(obj):
    if isinstance(obj, dict):
        return {k: convert_sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, list):
        return [convert_sets_to_lists(i) for i in obj]
    else:
        return obj


def resolve_ref(ref_path, definitions):
    ref_name = ref_path.split('/')[-1]
    return definitions.get(ref_name, {})


def extract_definition_properties(definition):
    """extract definitions content"""
    props = []
    for prop_name, prop_detail in definition.get("properties", {}).items():
        props.append({
            "name": prop_name,
            "in": "body",
            "type": prop_detail.get("type", "object"),
            "description": prop_detail.get("description", "")
        })
    return props


def expand_schema(schema, definitions):
    if '$ref' in schema:
        definition = resolve_ref(schema['$ref'], definitions)
        return extract_definition_properties(definition)
    elif schema.get('type') == 'array' and 'items' in schema:
        items = schema['items']
        if '$ref' in items:
            definition = resolve_ref(items['$ref'], definitions)
            return extract_definition_properties(definition)
    return []


def extract_json_from_markdown(text):
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def extract_api_paths_from_script(script_text):
    pattern = r'requests\.(get|post|put|delete)\(f?"?\{?BASE_URL\}?(/[^"\')]+)'
    matches = re.findall(pattern, script_text)
    return set(path for _, path in matches)


def calculate_method_coverage(selected_apis, script_text):
    expected_paths = set(api["api_path"] for api in selected_apis)
    for api in selected_apis:
        print('api', api)
        print('api_path', api["api_path"])
    print('expected_paths', expected_paths)
    used_paths = extract_api_paths_from_script(script_text)
    print('used_paths', used_paths)
    matched_paths = expected_paths.intersection(used_paths)
    print('matched_paths', matched_paths)

    coverage = round(len(matched_paths) / len(expected_paths) * 100, 2) if expected_paths else 0
    detail = {
        "expected": list(expected_paths),
        "used_in_script": list(used_paths),
        "matched": list(matched_paths)
    }
    detail_json = json.dumps(detail, ensure_ascii=False)
    return coverage, detail_json