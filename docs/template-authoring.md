# Template authoring

Add a `.json` file in `templates/` with a unique lowercase `id`. Restart the server to reload after edits (or run with `--reload`). The browser lists templates from the configured source and creates input controls from each template's `fields` array.

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

Available placeholders are `patient.name`, `patient.age`, `patient.medical_history`, `doctor.name`, `today`, and `fields.<key>` for fields declared in that file. The renderer preserves newlines and escapes entered text. Empty optional fields show an em dash. Keep clinical wording reviewed by qualified staff before use.

To use Google Docs later, implement `TemplateSource` in `app/repository.py` or another module. Map each external document's metadata and body into `DocumentTemplate`, then pass an instance to `create_app(template_source=...)`. The API, browser, and PDF renderer consume the normalized model and need no source-specific code.

