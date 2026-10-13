# Patient Document Studio

Local MVP for filling clinical forms, lab requests, and consultation letters from one patient entry. Select one template to download a PDF or several to download a ZIP of PDFs.

## Workflow preview

![Animated walkthrough of patient entry, template selection, and PDF generation](docs/screenshots/workflow.gif)

The preview uses fictitious patient data.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use sample data only; the MVP has no authentication or clinical data controls.

## Test

```bash
pytest -q
```

## Configuration

Set `TEMPLATE_DIR` to another local folder of JSON templates. The default is this repository's `templates/` directory. See [architecture](docs/architecture.md) and [template authoring](docs/template-authoring.md). No patient input or generated files are persisted by the app.

