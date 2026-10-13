# JSON template authoring

Add a `.json` file in `templates/` with a unique lowercase `id`. These are the generated fallback forms and the templates offered by the one-off `/quick` page. The request-form workflow chooses a template through the `template_id` in `catalog/labs.json`. For an approved fillable PDF layout, see [form assets](../form_assets/README.md).

```json
{
  "id": "sample-note",
  "title": "Sample note",
  "category": "Forms",
  "description": "A short example",
  "fields": [{"key": "reason", "label": "Reason", "required": true, "multiline": true}],
  "blocks": [
    {"type": "heading", "text": "Patient details"},
    {"type": "field", "label": "Patient", "text": "{{ patient.name }}"},
    {"type": "paragraph", "text": "Reason: {{ fields.reason }}"}
  ]
}
```

Available placeholders are `patient.name`, `patient.code`, `patient.age`, `patient.medical_history`, `doctor.name`, `today`, and declared `fields.<key>`. The request-form workflow supplies `fields.lab_name`, `fields.tests_requested`, and `fields.clinical_question`. The renderer preserves newlines and escapes entered text. Empty optional fields show an em dash.

To replace local JSON files later, implement `TemplateSource` and pass it to `create_app(template_source=...)`. Map external metadata and body into `DocumentTemplate` objects. The browser and PDF renderer use the normalized model.
