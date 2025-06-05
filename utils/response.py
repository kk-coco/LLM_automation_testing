import json
from flask import Response

def json_response(data=None, msg="success", code=200):
    payload = {
        "code": code,
        "msg": msg,
        "data": data or {}
    }
    return Response(json.dumps(payload, ensure_ascii=False), mimetype="application/json")
