# 02 Excel tracker store
Labels: backend, excel

## Description
`data/tracker.xlsx` is the system of record for applications (schema in plan.md section 7).

## Acceptance criteria
- [ ] File is created with the 14 headers if missing; header frozen, autofilter on, column widths set
- [ ] `append_record` adds a row with date applied, company, ATS score, requirements not matched, status
- [ ] Status column has a dropdown validation of the six statuses
- [ ] Job URL is a clickable hyperlink
- [ ] `update_status` changes Status, Notes and Last Updated for the right ID only
- [ ] Writes are atomic; a locked file (open in Excel) gives a clear error (HTTP 423), not a corrupt file
- [ ] Unit tests cover round trip, status update, validation present, atomic write
