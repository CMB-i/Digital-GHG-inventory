from flask import jsonify


def success_response(data=None, message="OK"):
    payload = {"message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload)


def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code
