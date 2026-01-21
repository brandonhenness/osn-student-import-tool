from gluon import current
import json
import uuid
from datetime import datetime
import traceback


@request.restful()
def student_import_api():
    """
    JSON API for importing students without uploading an Excel file.

    POST /import/student_import_api
    Content-Type: application/json

    {
      "token": "YOUR_SECRET_TOKEN",
      "erase_current_password": false,
      "erase_current_quota": false,
      "process_canvas": true,
      "students": [
        {
          "user_id": "S123456",          # usually sAMAccountName
          "student_name": "Doe, Jane",
          "student_password": "SidS123456!",   # optional
          "import_classes": "MATH101,ENG102",  # optional
          "program": "SCCC",                   # optional
          "doc_number": "1234567"              # optional; saved in additional_fields
        }
      ]
    }
    """
    response.view = 'generic.json'

    def POST(*args, **vars):
        db = current.db

        try:
            # 1. Parse JSON body
            data = request.json
            if data is None:
                raw = request.body.read()
                data = json.loads(raw)

            # 2. Shared-secret auth
            token = data.get('token')
            expected = "CHANGE_ME_IMPORT_TOKEN"  # <-- keep in sync with Excel
            if token != expected:
                raise Exception("Forbidden: invalid token")

            # 3. Options
            erase_pw = bool(data.get('erase_current_password', False))
            erase_quota = bool(data.get('erase_current_quota', False))
            process_canvas = bool(data.get('process_canvas', True))

            # 4. Normalize students list
            students = data.get('students')
            if students is None:
                single = data.get('student')
                if single is not None:
                    students = [single]
                else:
                    students = []
            elif isinstance(students, dict):
                students = [students]

            if not students:
                return dict(status='error', message='No students provided')

            # 5. New synthetic sheet_name for this batch
            sheet_name = 'API_%s' % datetime.utcnow().strftime('%Y%m%d_%H%M%S')

            inserted = 0
            insert_errors = []

            for s in students:
                try:
                    _insert_student_into_queue_from_json(sheet_name, s)
                    inserted += 1
                except Exception as ex_row:
                    insert_errors.append(dict(student=s, error=str(ex_row)))

            # 6. Same first step as student_do_import()
            created_accounts = Student.CreateW2PyAccounts(
                sheet_name,
                erase_pw,
                erase_quota
            )

            # AD queue (safe even if AD is effectively disabled)
            queued_ad = Student.QueueActiveDirectoryImports(sheet_name)

            # Canvas queue
            queued_canvas = Student.QueueCanvasImports(sheet_name)

            # 7. Optionally process Canvas queue now (like student_do_import_canvas)
            canvas_processed = 0
            last_canvas_result = None

            if process_canvas and queued_canvas:
                max_iterations = 1000  # safety cap

                for i in range(max_iterations):
                    result = Student.ProcessCanvasStudent()
                    last_canvas_result = result
                    canvas_processed += 1

                    text = str(result).lower()
                    if "done" in text or "no more" in text or "empty" in text:
                        break

            return dict(
                status='ok',
                sheet_name=sheet_name,
                queued_students=inserted,
                created_accounts=created_accounts,
                queued_ad=queued_ad,
                queued_canvas=queued_canvas,
                canvas_processed=canvas_processed,
                insert_errors=insert_errors,
                last_canvas_result=str(last_canvas_result)
            )

        except Exception as ex:
            tb = traceback.format_exc()
            response.status = 500
            return dict(
                status='error',
                message=str(ex),
                traceback=tb
            )

    return locals()


def _insert_student_into_queue_from_json(sheet_name, s):
    """
    Insert one row into student_import_queue from JSON dict `s`.

    This is all new code; no existing modules are modified.
    """
    db = current.db

    user_id = (s.get('user_id') or s.get('sam_account_name') or '').strip()
    if not user_id:
        raise ValueError("user_id (or sam_account_name) is required")

    student_name = (s.get('student_name') or s.get('name') or '').strip()
    if not student_name:
        student_name = user_id

    student_password = s.get('student_password', None)

    # IMPORTANT: import_classes must always be a string, not None,
    # so that ProcessCanvasStudent can safely call .split(';')
    import_classes = s.get('import_classes')
    if import_classes is None:
        import_classes = ''
    else:
        import_classes = str(import_classes)

    # You said you don't really want to set program; leaving it as empty string by default
    program = s.get('program', '') or ''

    additional_fields = s.get('additional_fields', '') or ''

    # Optionally store doc_number in additional_fields
    doc_number = s.get('doc_number', None)
    if doc_number:
        if additional_fields:
            additional_fields = str(additional_fields) + "\nDOC_NUMBER=%s" % doc_number
        else:
            additional_fields = "DOC_NUMBER=%s" % doc_number

    now = request.now
    student_guid = s.get('student_guid') or str(uuid.uuid4()).replace('-', '')

    db.student_import_queue.insert(
        user_id=user_id,
        student_name=student_name,
        student_password=student_password,
        import_classes=import_classes,   # now always a string, never None
        program=program,
        additional_fields=additional_fields,
        sheet_name=sheet_name,
        student_guid=student_guid,
        account_enabled=True,
        account_added_on=now,
        account_updated_on=now
    )
