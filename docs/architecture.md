# Architecture and decisions

## Goal

A doctor enters patient details once, selects one or more clinical document templates, adds the fields those templates require, and downloads completed PDFs. This MVP is intended for local evaluation with sample data.

## Decisions

- **Private GitHub repository.** The project concerns clinical workflows, so source is private by default. No patient records or generated files belong in Git.
- **Local-first FastAPI app.** A small browser interface talks to a Python API on localhost. Patient input is used in memory for each request; there is no database, account system, or generation history.
- **No external assets.** The interface uses system fonts and local static files so opening it makes no third-party asset requests.
- **One normalized template model.** JSON files in `templates/` define metadata, additional input fields, and document blocks. The `TemplateSource` protocol returns normalized `DocumentTemplate` objects. A later Google Docs or server API adapter can implement this protocol without changing the form or PDF generator.
- **PDF output for MVP.** ReportLab renders the normalized blocks to paginated A4 PDFs. Source ingestion and output rendering are separate decisions. Word or existing PDF templates will need an adapter or renderer rather than a change to the doctor form.
- **Explicit placeholders.** Only `patient.name`, `patient.age`, `patient.medical_history`, `doctor.name`, `today`, and declared `fields.<key>` may appear. Unknown tokens fail generation clearly; values are escaped before PDF rendering.
- **One or many downloads.** A single selection returns a PDF. Multiple selections return a ZIP containing one PDF per template.

## Boundaries

`TemplateSource` exposes `list_templates()` and `get_template(id)`. `LocalTemplateSource` reads JSON from a configured directory and validates it. The API receives patient and template-specific data, validates selected IDs and required fields, and passes normalized templates plus values to the PDF renderer. The browser does not depend on where templates are stored.

## Template contract

Each JSON file has `id`, `title`, `category`, `description`, `fields`, and `blocks`. Field entries have `key`, `label`, `required`, and `multiline`. Blocks are `heading`, `paragraph`, `field`, or `spacer`; text values can contain placeholders such as `{{ patient.name }}`. See the examples in `templates/` and [template authoring](template-authoring.md).

## Limits before clinical deployment

There is no authentication, audit trail, encryption at rest, access control, retention policy, EHR integration, or approved clinical/legal wording. Run on localhost with sample data only. A production release needs a privacy/security review and jurisdiction-specific template approval.
