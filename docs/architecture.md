# Architecture and decisions

## Workflow

The browser at `/` shows a patient registry. Patients and orders persist in SQLite. A patient has a generated stable code; an order stores a snapshot of the selected tests, doctor, clinical question, copies, and creation time. The patient record supplies current name, age, and history whenever an order is downloaded. The summary PDF uses current patient data and order names.

`catalog/labs.json` groups tests by laboratory. Each test references a request form ID. Selected tests are grouped by laboratory and form ID, so several tests can be written on one form. The app emits the requested copies of each form. A single output is a PDF; multiple outputs are a ZIP.

## Sources and renderers

- `TemplateSource` exposes `list_templates()` and `get_template(id)` for normalized JSON document templates. `LocalTemplateSource` is the default and reads `templates/`. The one-off `/quick` flow still uses this source.
- `FormAssetSource` exposes `list_asset_ids()` and `get_asset(id)` for approved fillable PDF forms. `LocalFormAssetSource` reads `form_assets/manifest.json` and its PDFs. A matching PDF overrides a JSON request form when an order is rendered.
- ReportLab renders JSON templates and the patient summary. pypdf fills text fields in AcroForm PDFs. Arabic text in generated ReportLab PDFs is reshaped and reordered for print rendering.
- The browser talks only to API routes. A future Google Docs or server adapter can implement either source interface. A Docs pipeline would still need to export or normalize the source into a supported renderable form.

`create_app(template_source=..., database_path=..., form_asset_source=...)` supports source injection and isolated test databases. The catalog currently reads a local JSON file through `LocalTestCatalog` and can be replaced at the API boundary if needed later.

## Persistence and deletion

SQLite lives at `data/patients.sqlite3` by default. The database and generated files are ignored by Git. Patient IDs use SQLite autoincrement, so deleting a patient never reuses the displayed code. Deleting a patient also deletes that patient's orders. Cleanup previews the count before deleting records whose **creation date** is older than the selected number of days; editing a record does not reset that age. There is no scheduled deletion in this MVP.

## Limits before clinical deployment

The app is intended for local evaluation with sample data. It has no authentication, audit trail, encryption at rest, access control, approved clinical/legal wording, backup system, or regulated retention policy. A clinic deployment requires those controls and review of each form, especially Arabic rendering in supplied AcroForms.
