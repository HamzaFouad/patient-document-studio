# Add laboratories and tests

Edit `catalog/labs.json`. Each laboratory has a unique `id`, a display `name`, and a list of tests. Each test has a globally unique `id`, a display `name`, and the `template_id` of the request form used by that test.

```json
[
  {
    "id": "example-lab",
    "name": "Example laboratory",
    "tests": [
      {"id": "blood-count", "name": "Complete blood count", "template_id": "lab-request"},
      {"id": "inflammation", "name": "CRP", "template_id": "lab-request"}
    ]
  }
]
```

Both tests above use one `lab-request` form when selected together. If another laboratory uses the same form ID, it gets a separate completed form for that laboratory. IDs use lowercase letters, numbers, and hyphens. Keep the catalog names and form wording reviewed by the clinic; the included tests and laboratories are examples.

A `template_id` must be available as a JSON template in `templates/` or a mapped PDF in `form_assets/manifest.json`. The API rejects orders whose form IDs are unavailable. Existing orders keep the selected test names and form mappings as a snapshot, so changing the catalog does not rename those selections retroactively.
