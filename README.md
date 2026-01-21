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
- Import to SMC via JSON API
- Automatic Canvas provisioning (optional)
- Re-import safe / idempotent
- Eliminates SMC UI spreadsheet upload

---

## Setup

### Excel / OSN Setup

- Update defaults in: `Institution`, `LogonScript`, `Password`, `Groups`, `HDriveRootPath`
- Refresh `AD Users` on an OSN workstation (pulls AD attributes)

### SMC (web2py) Setup (Required for SMC Import)

The SMC import API must be added to the `smc` application.

#### **1. Open SMC design interface**

Browser:

```
https://smc.<domain>/admin/design/smc
```

Example:

```
https://smc.ghc.osn.wa.gov/admin/design/smc
```

#### **2. Edit controller**

Navigate:

```
controllers → import.py → Edit
```

Do not remove or overwrite existing code.

#### **3. Add imports at top of file**

Ensure the following exist:

```python
import json
import uuid
from datetime import datetime
import traceback
```

If duplicates exist, leave them.

#### **4. Append new SMC import API at bottom of file**

Scroll to the bottom and append the:

```
@request.restful()
def student_import_api():
    ...
```

This must be appended, not inserted into existing functions.

#### **5. Configure secure token**

Inside the API, change:

```python
expected = "CHANGE_ME_IMPORT_TOKEN"
```

to a randomly generated shared secret, for example:

```python
expected = "X9z!sG4p7QdK38sw"
```

Token is treated as a password.

#### **6. Save + Apply**

web2py auto reloads after:

```
Save → Apply
```

#### **7. Verify API endpoint**

The endpoint is located at:

```
https://smc.<domain>/import/student_import_api.json
```

Opening this in a browser without a POST will typically return:

- `{"method":"POST"}` or
- `"Method Not Allowed"` or
- `"Forbidden"`

This is expected.

#### **8. Test with POST (curl example)**

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"token":"X9z!sG4p7QdK38sw","students":[]}' \
  https://smc.<domain>/import/student_import_api.json
```

Expected result:

```json
{"status":"error","message":"No students provided"}
```

#### **9. Test with PowerShell**

```powershell
Invoke-RestMethod `
  -Uri "https://smc.<domain>/import/student_import_api.json" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"token":"X9z!sG4p7QdK38sw","students":[]}'
```

#### **10. Permissions**

API requires either:

- `Import` membership, or
- `Administrators` membership, or
- matching shared token (recommended)

Canvas provisioning must already work in SMC.

---

## Excel Configuration (SMC)

Inside workbook → `smc_config` table:

```
Key                  Value
-----------------------------------------------
SMC_IMPORT_URL       https://smc.<domain>/import/student_import_api.json
SMC_IMPORT_TOKEN     X9z!sG4p7QdK38sw
```

Tokens must match between web2py and Excel.

If mismatched, SMC returns `Forbidden`.

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
2. Verify smc_config (URL + Token)
3. Click “Import to SMC”
4. Accounts + Canvas provisioning automatically
```

This replaces the manual spreadsheet upload into SMC.

Re-import is safe and will not duplicate accounts.

---

## Data Mapping

| Excel Field     | SMC Field         | Notes |
|---|---|---|
| Username        | user_id           | typically sAMAccountName |
| Name            | student_name      | fallback = Username |
| DOCID           | DOC_NUMBER        | stored in additional_fields |
| Password        | student_password  | optional |
| Enabled         | ignored           | not used for SMC |
| Program         | optional          | not required |
| Classes         | optional          | may be added later |

---

## API Format (Excel → SMC)

```json
{
  "token": "TOKEN",
  "process_canvas": true,
  "students": [
    {
      "user_id": "jdoe",
      "student_name": "Doe, John",
      "student_password": "Example1!",
      "doc_number": "1234567"
    }
  ]
}
```

---

## Error Handling

SMC returns structured JSON:

```json
{
  "status":"error",
  "message":"...",
  "traceback":"..."
}
```

Useful for debugging Canvas provisioning or account collisions.

---

## Security Notes

- Token is a shared secret (treat as password)
- Tokens may be rotated anytime
- No firewall exposure required
- Membership-based auth alternative available

---

## Limitations

- AD → SMC sync not automated
- Canvas provisioning must be functional
- Course enrollment optional
- SMC integration requires web2py admin access

---

## Future Enhancements

- Course enrollment sync
- Canvas roster reconciliation
- DOCID ↔ SIS mapping logic
- Completion sync
- Token rotation tooling

---

## Contributing

Pull requests welcome, particularly around Canvas workflows, mappings, and provisioning logic.

---

## License

This project is licensed under the GPL 3.0 license. See [`LICENSE`](LICENSE) for details.
