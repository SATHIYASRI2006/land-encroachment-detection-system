from __future__ import annotations

from flask import jsonify


def success_response(data=None, status=200):
    return jsonify({"success": True, "data": data, "error": None}), status


def error_response(message, status=400, details=None):
    payload = {"success": False, "data": None, "error": {"message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return jsonify(payload), status
