# -*- coding: utf-8 -*-
"""
Append this block to the END of applications/smc/controllers/default.py

This deployment routes many root paths to default/<function>, so these API
endpoints are implemented in default.py to avoid needing routes.py changes.

Endpoints (root, because they live in default.py):
  GET  /api.json                 (discovery)
  POST /api_student_import.json  (JSON import -> queue -> optional canvas processing)
  GET  /api_students.json        (student_info rows)
  GET  /api_users.json           (auth_user rows, SAFE FIELD WHITELIST)

Auth:
  Shared-secret token loaded from a private file:
    applications/smc/private/api_token.txt

  Accepted via one of:
    - Header: X-Api-Token
    - Query:  ?token=...
    - JSON:   {"token": "..."}  (for POST)
"""

from ednet.util import Util
from ednet.ad import AD
from ednet.student import Student

# Help shut up pylance warnings (matches your existing controller style)
if 1 == 2:
    from ..common import *  # noqa: F401

import os
import cgi
from gluon import current, HTTP
import json
import uuid
from datetime import datetime
import traceback


# -----------------------------
# Token loading (private file)
# -----------------------------
def _load_api_token():
    """
    Load the shared-secret API token from:
      applications/smc/private/api_token.txt

    File contents:
      <token>   (single line)

    Notes:
      - Do NOT include quotes
      - Trailing newline is fine
      - Keep file permissions tight (owned by the app user)
    """
    try:
        token_path = os.path.join(request.folder, "private", "api_token.txt")
        with open(token_path, "r") as f:
            return (f.read() or "").strip()
    except Exception:
        return ""


def _get_request_json():
    """
    Parse JSON body safely.
    web2py sometimes provides request.json; fall back to raw body.
    """
    data = request.json
    if data is None:
        raw = request.body.read()
        if raw:
            data = json.loads(raw)
    return data or {}


def _require_api_token(data=None):
    """
    Shared-secret auth.
    Accepts token from:
      - Header: X-Api-Token
      - Query:  ?token=...
      - JSON body: {"token": "..."}   (useful for POST)
    """
    if data is None:
        data = {}

    token = None

    # Header (web2py lowercases and prefixes http_)
    try:
        token = request.env.get("http_x_api_token")
    except Exception:
        token = None

    # Query string
    if not token:
        token = request.vars.get("token")

    # JSON body
    if not token:
        token = data.get("token")

    expected = _load_api_token()
    if not expected:
        raise HTTP(500, "Server misconfigured: API token file missing or empty")

    if token != expected:
        raise HTTP(403, "Forbidden: invalid token")


def _int_or_default(value, default):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _clamp_limit_offset(limit, offset, default_limit=500, max_limit=5000):
    limit = _int_or_default(limit, default_limit)
    offset = _int_or_default(offset, 0)

    if limit < 1:
        limit = 1
    if limit > max_limit:
        limit = max_limit
    if offset < 0:
        offset = 0

    return limit, offset


# -----------------------------
# Discovery
# -----------------------------
def api():
    """
    GET /api.json
    """
    response.view = "generic.json"
    _require_api_token()
    return dict(
        status="ok",
        endpoints=dict(
            student_import="POST /api_student_import.json",
            students="GET /api_students.json?limit=500&offset=0",
            users="GET /api_users.json?limit=500&offset=0",
        ),
        auth="X-Api-Token header OR token query param OR token in JSON body",
    )


# -----------------------------
# Student Import API
# -----------------------------
@request.restful()
def api_student_import():
    """
    POST /api_student_import.json
    Content-Type: application/json

    {
      "token": "YOUR_SECRET_TOKEN",
      "erase_current_password": false,
      "erase_current_quota": false,

      // if true, queues Canvas imports (default true)
      "queue_canvas": true,

      // if true, processes Canvas queue immediately (default true)
      "process_canvas": true,

      "students": [
        {
          "user_id": "S123456",
          "student_name": "Doe, Jane",
          "student_password": "SidS123456!",   # optional
          "import_classes": "MATH101,ENG102",  # optional
          "program": "SCCC",                   # optional
          "doc_number": "1234567",             # optional
          "additional_fields": "KEY=VALUE"     # optional
        }
      ]
    }
    """
    response.view = "generic.json"

    def POST(*args, **vars):
        db = current.db

        try:
            data = _get_request_json()
            _require_api_token(data)

            erase_pw = bool(data.get("erase_current_password", False))
            erase_quota = bool(data.get("erase_current_quota", False))
            queue_canvas = bool(data.get("queue_canvas", True))
            process_canvas = bool(data.get("process_canvas", True))

            # Normalize students list
            students = data.get("students")
            if students is None:
                single = data.get("student")
                if single is not None:
                    students = [single]
                else:
                    students = []
            elif isinstance(students, dict):
                students = [students]

            if not students:
                return dict(status="error", message="No students provided")

            # Synthetic sheet_name for this batch
            sheet_name = "API_%s" % datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            inserted = 0
            insert_errors = []

            for s in students:
                try:
                    _api_insert_student_into_queue_from_json(sheet_name, s)
                    inserted += 1
                except Exception as ex_row:
                    insert_errors.append(dict(student=s, error=str(ex_row)))

            # Mirror student_do_import()
            AD.Close()

            created_accounts = Student.CreateW2PyAccounts(sheet_name, erase_pw, erase_quota)

            queued_ad = Student.QueueActiveDirectoryImports(sheet_name)

            queued_canvas = 0
            if queue_canvas:
                queued_canvas = Student.QueueCanvasImports(sheet_name)

            # Optionally process Canvas queue now
            canvas_processed = 0
            last_canvas_result = None

            if process_canvas and queued_canvas:
                max_iterations = 1000  # safety cap
                for i in range(max_iterations):
                    result = Student.ProcessCanvasStudent()
                    last_canvas_result = result
                    canvas_processed += 1

                    text = str(result).lower()
                    if ("done" in text) or ("no more" in text) or ("empty" in text):
                        break

            return dict(
                status="ok",
                sheet_name=sheet_name,
                queued_students=inserted,
                created_accounts=created_accounts,
                queued_ad=queued_ad,
                queued_canvas=queued_canvas,
                canvas_processed=canvas_processed,
                insert_errors=insert_errors,
                last_canvas_result=str(last_canvas_result),
            )

        except HTTP as h:
            response.status = h.status
            return dict(status="error", message=str(h))

        except Exception as ex:
            response.status = 500
            return dict(status="error", message=str(ex), traceback=traceback.format_exc())

    return locals()


def _api_insert_student_into_queue_from_json(sheet_name, s):
    """
    Insert one row into student_import_queue from JSON dict `s`.
    """
    db = current.db

    user_id = (s.get("user_id") or s.get("sam_account_name") or "").strip()
    if not user_id:
        raise ValueError("user_id (or sam_account_name) is required")

    student_name = (s.get("student_name") or s.get("name") or "").strip()
    if not student_name:
        student_name = user_id

    student_password = s.get("student_password", None)

    # IMPORTANT: import_classes must always be a string, never None
    import_classes = s.get("import_classes")
    if import_classes is None:
        import_classes = ""
    else:
        import_classes = str(import_classes)

    program = s.get("program", "") or ""
    additional_fields = s.get("additional_fields", "") or ""

    doc_number = s.get("doc_number", None)
    if doc_number:
        if additional_fields:
            additional_fields = str(additional_fields) + "\nDOC_NUMBER=%s" % doc_number
        else:
            additional_fields = "DOC_NUMBER=%s" % doc_number

    now = request.now
    student_guid = s.get("student_guid") or str(uuid.uuid4()).replace("-", "")

    db.student_import_queue.insert(
        user_id=user_id,
        student_name=student_name,
        student_password=student_password,
        import_classes=import_classes,
        program=program,
        additional_fields=additional_fields,
        sheet_name=sheet_name,
        student_guid=student_guid,
        account_enabled=True,
        account_added_on=now,
        account_updated_on=now,
    )


# -----------------------------
# Read endpoints
# -----------------------------
def api_students():
    """
    GET /api_students.json

    Query params:
      token   (or X-Api-Token header)
      limit   default 500, max 5000
      offset  default 0

    Returns: student_info rows (ALL fields).
    """
    response.view = "generic.json"
    try:
        _require_api_token()

        db = current.db
        limit, offset = _clamp_limit_offset(request.vars.get("limit"), request.vars.get("offset"))

        q = (db.student_info.id > 0)
        rows = db(q).select(orderby=db.student_info.id, limitby=(offset, offset + limit))

        return dict(
            status="ok",
            table="student_info",
            limit=limit,
            offset=offset,
            count=len(rows),
            rows=rows.as_list(),
        )

    except HTTP as h:
        response.status = h.status
        return dict(status="error", message=str(h))

    except Exception as ex:
        response.status = 500
        return dict(status="error", message=str(ex), traceback=traceback.format_exc())


def api_users():
    """
    GET /api_users.json

    Query params:
      token   (or X-Api-Token header)
      limit   default 500, max 5000
      offset  default 0

    IMPORTANT:
      auth_user can contain sensitive fields. This endpoint intentionally
      returns a SAFE FIELD WHITELIST only.
    """
    response.view = "generic.json"
    try:
        _require_api_token()

        db = current.db
        limit, offset = _clamp_limit_offset(request.vars.get("limit"), request.vars.get("offset"))

        # Safe whitelist: always present fields
        fields = [
            db.auth_user.id,
            db.auth_user.email,
            db.auth_user.first_name,
            db.auth_user.last_name,
        ]

        # Optional commonly-present fields (include only if they exist)
        for optional in ("is_active", "created_on", "modified_on", "last_login"):
            if optional in db.auth_user.fields:
                fields.append(db.auth_user[optional])

        q = (db.auth_user.id > 0)
        rows = db(q).select(*fields, orderby=db.auth_user.id, limitby=(offset, offset + limit))

        return dict(
            status="ok",
            table="auth_user",
            limit=limit,
            offset=offset,
            count=len(rows),
            rows=rows.as_list(),
        )

    except HTTP as h:
        response.status = h.status
        return dict(status="error", message=str(h))

    except Exception as ex:
        response.status = 500
        return dict(status="error", message=str(ex), traceback=traceback.format_exc())
