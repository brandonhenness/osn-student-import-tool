# SMC + OSN Student Import Tool

This Excel workbook automates two student account workflows:

1. **OSN Export Workflow** — generates CSV for OSN disabled accounts provisioning.
2. **SMC/Canvas Import Workflow** — imports students directly into SMC and optionally provisions Canvas accounts.

Both workflows share user attributes pulled from Active Directory.

---

## Features

- Pulls AD user data from OSN workstation
- DOCID → username mapping
- Export for OSN disabled accounts workflow
- Import to SMC via JSON API (no SMC UI spreadsheet upload)
- Automatic Canvas provisioning (optional)
- Re-import safe / idempotent
- Optional password generation rules for SMC/Canvas (random or passphrase)
- Read-only endpoints for viewing `student_info` and safe `auth_user` fields (Power Query friendly)

---

## Setup

### Excel / OSN Setup

- Update defaults in: Institution, LogonScript, Password, Groups, HDriveRootPath
- Refresh AD Users on an OSN workstation (pulls AD attributes)

### SMC (web2py) Setup (Required for SMC Import)

This project includes an API implementation in the file:

```
api.py
```

That file contains **all API endpoints** (import + read-only endpoints).

Because this SMC deployment does not expose custom controllers via routing, the API code must be **copied from `api.py` and appended into the existing controller**:

```
smc/controllers/default.py
```

---

## Install (SMC web2py)

### 1) Open SMC design interface

Browser:

```
https://smc.<domain>/admin/design/smc
```

Example:

```
https://smc.ghc.osn.wa.gov/admin/design/smc
```

### 2) Open `default.py`

Navigate:

```
controllers → default.py → Edit
```

Scroll to the **bottom of the file**.

### 3) Copy API code from this project

From this project repository:

```
api.py
```

Copy **the entire contents** of `api.py`.

### 4) Append API code into `default.py`

Paste the copied contents **at the very end** of `default.py`.

Click:

```
Save → Apply
```

Notes:
- Do not remove or modify existing code in `default.py`.
- Do not nest the API code inside another function.
- The API code must remain top-level functions.
- Endpoints become active immediately after Apply.

---

## Token Configuration (Required)

### 1) Create private token file

In the web2py design interface, navigate:

```
private → (Create) api_token.txt
```

Paste **only the token value** into the file:

```
<your token here>
```

Click:

```
Save → Apply
```

Notes:
- Treat this file like a password.
- This keeps secrets out of source control.
- The API reads the token from this file at runtime.

---

## API Endpoints

Because the API functions are appended to `controllers/default.py`, the URLs are rooted at the application level and **do NOT include `/default/`**.

### Import endpoint

```
https://smc.<domain>/api_student_import.json
```

### Read endpoints

Students:

```
https://smc.<domain>/api_students.json?token=YOUR_TOKEN
```

Users (safe whitelist fields only):

```
https://smc.<domain>/api_users.json?token=YOUR_TOKEN
```

Both read endpoints support paging:

```
?limit=500&offset=0
```

---

### Browser Testing (API Discovery)

The API exposes a discovery endpoint that can be tested directly in a web browser.

This confirms that:
- the controller is loaded
- routing is correct
- the API token is valid
- JSON responses are working

Open the following URL in a browser:

    https://smc.<domain>/api.json?token=YOUR_TOKEN

Expected response:

    {
      "status": "ok",
      "endpoints": {
        "student_import": "POST /api/student_import.json",
        "students": "GET /api/students.json",
        "users": "GET /api/users.json"
      }
    }

If the token is missing or incorrect, SMC will return:

    Forbidden

This endpoint is intended for verification and discovery only.
It does not perform any data modification.

The student import endpoint requires POST and cannot be tested from the browser address bar.

---

## Excel Configuration (SMC)

All SMC settings live in workbook → `smc_config` table.

Minimum required:

```
SMC_IMPORT_URL        https://smc.<domain>/api_student_import.json
SMC_IMPORT_TOKEN      <secret>
```

Recommended for Power Query:

```
SMC_STUDENTS_URL      https://smc.<domain>/api_students.json
SMC_USERS_URL         https://smc.<domain>/api_users.json
```

Tokens must match between:
- `smc/private/api_token.txt`
- `SMC_IMPORT_TOKEN` in Excel

If mismatched, SMC returns `Forbidden`.

---

## Excel Settings (SMC Import + Password Rules)

Add these rows to the `smc_config` table (exact keys):

SMC_IMPORT_URL  
Value: https://smc.<domain>/api_student_import.json  
Help: SMC import endpoint URL  

SMC_IMPORT_TOKEN  
Value: <secret>  
Help: Must match token in `smc/private/api_token.txt`  

SMC_STUDENTS_URL  
Value: https://smc.<domain>/api_students.json  
Help: SMC students read endpoint URL (Power Query)  

SMC_USERS_URL  
Value: https://smc.<domain>/api_users.json  
Help: SMC users read endpoint URL (Power Query; safe fields only)  

SMC_PROCESS_CANVAS  
Value: TRUE  
Help: TRUE/FALSE  

SMC_ERASE_CURRENT_PASSWORD  
Value: TRUE  
Help: TRUE/FALSE (replace existing passwords)  

SMC_ERASE_CURRENT_QUOTA  
Value: FALSE  
Help: TRUE/FALSE (reset quota values)  

SMC_GENERATE_PASSWORDS  
Value: TRUE  
Help: TRUE/FALSE (generate separate SMC password)  

SMC_PASSWORD_STYLE  
Value: passphrase  
Help: passphrase or random  

SMC_PASSWORD_WORDS_SHEET  
Value: passphrase_words  
Help: Sheet name containing words in column A  

SMC_PASSWORD_MIN_LENGTH  
Value: 15  
Help: Minimum length for random passwords (SMC requires at least 8)  

SMC_PASSWORD_ALLOWED_SPECIALS  
Value: !@#$%^&*?-  
Help: Allowed special characters  

SMC_PASSWORD_DISALLOWED_CHARS  
Value: O0oIl1  
Help: Characters to never use  

SMC_PASSWORD_REQUIRE_LOWER  
Value: TRUE  
Help: Require at least one lowercase  

SMC_PASSWORD_REQUIRE_UPPER  
Value: TRUE  
Help: Require at least one uppercase  

SMC_PASSWORD_REQUIRE_DIGIT  
Value: TRUE  
Help: Require at least one digit  

SMC_PASSWORD_REQUIRE_SPECIAL  
Value: TRUE  
Help: Require at least one special character  

SMC_PASSPHRASE_MIN_LENGTH  
Value: 15  
Help: Minimum length for passphrases  

SMC_PASSPHRASE_SEPARATOR  
Value: -  
Help: Separator character  

SMC_PASSPHRASE_APPEND_DIGIT  
Value: TRUE  
Help: Append a single digit  

SMC_PASSPHRASE_CAPITALIZATION  
Value: all  
Help: all, first, or none  

SMC_PASSPHRASE_DIGIT_PLACEMENT  
Value: random_word  
Help: random_word or end  

SMC_PASSPHRASE_DIGITS_ALLOWED  
Value: 123456789  
Help: Allowed digits for passphrase suffix  

---

## Usage

### OSN Export Workflow (Disabled Accounts)

```
1. Refresh AD Users (every time)
2. Paste DOCID list
3. Adjust special rows if needed
4. Export Disabled Accounts
5. Submit disabled_accounts CSV to OSN ticket
```

Outputs CSV formatted for OSN provisioning.

---

### SMC/Canvas Import Workflow

```
1. Fill students table
2. Verify smc_config (URL + Token + settings)
3. Click Import to SMC
4. Accounts + optional Canvas provisioning run automatically
```

This replaces the manual spreadsheet upload into SMC.

Re-import is safe and will not duplicate accounts.

---

## Data Mapping

Username → user_id  
Name → student_name  
DOCID → doc_number (stored as DOC_NUMBER in additional_fields)  
Password → student_password (optional; Excel may generate separate SMC password)  
Program → program (optional)  
Classes → import_classes (optional)  

---

## API Payload Format

POST to:

```
https://smc.<domain>/api_student_import.json
```

JSON body:

```json
{
  "token": "TOKEN",
  "erase_current_password": true,
  "erase_current_quota": false,
  "process_canvas": true,
  "queue_canvas": true,
  "students": [
    {
      "user_id": "jdoe",
      "student_name": "Doe, John",
      "student_password": "Example1!",
      "doc_number": "1234567",
      "import_classes": "MATH101,ENG102"
    }
  ]
}
```

---

## Error Handling

SMC returns structured JSON:

```json
{
  "status": "error",
  "message": "...",
  "traceback": "..."
}
```

---

## Security Notes

- Token is a shared secret (treat as password)
- Token stored in `smc/private/api_token.txt`
- Tokens may be rotated anytime
- No firewall exposure required
- auth_user responses must whitelist fields

---

## Limitations

- AD → SMC sync not automated
- Canvas provisioning must already be functional
- Course enrollment optional
- SMC integration requires web2py admin access

---

## Future Enhancements

- Course enrollment sync
- Canvas roster reconciliation
- DOCID ↔ SIS mapping logic
- Completion sync
- Token rotation tooling
- Optional endpoint to report queue status / last import

---

## Contributing

Pull requests welcome, particularly around Canvas workflows, mappings, and provisioning logic.

---

## License

This project is licensed under the GPL 3.0 license. See [`LICENSE`](LICENSE) for details.
