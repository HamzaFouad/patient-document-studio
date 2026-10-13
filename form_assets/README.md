# Fillable PDF request forms

Put AcroForm PDFs in this directory and add a record to `manifest.json` for each form. The form ID must match a `template_id` in `catalog/labs.json`. A mapped PDF takes precedence over the generated JSON request form. The app keeps the PDF fillable and returns it ready to print.

```json
{
  "forms": [
    {
      "id": "lab-request",
      "filename": "my-lab-request.pdf",
      "fields": {
        "patient.name": "PatientName",
        "patient.code": "PatientCode",
        "patient.age": "PatientAge",
        "patient.medical_history": "History",
        "doctor.name": "DoctorName",
        "today": "RequestDate",
        "fields.lab_name": "Laboratory",
        "fields.tests_requested": "TestsRequested",
        "fields.clinical_question": "ClinicalQuestion"
      }
    }
  ]
}
```

The values on the right must exactly match AcroForm text field names in the PDF. A form may map only the fields it contains. The app rejects missing fields and signed PDFs rather than silently producing incomplete forms. Use multiline PDF fields for medical history, tests, and clinical question. Keep patient PDFs and the local SQLite database out of Git.

Word files can be prepared as source material, then exported to fillable PDF once the layout is approved. That keeps the generated documents printable without requiring Word or a document converter on the clinic computer.
