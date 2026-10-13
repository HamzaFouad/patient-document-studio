const templateList = document.querySelector('#template-list');
const detailsPanel = document.querySelector('#details-panel');
const templateFields = document.querySelector('#template-fields');
const selectedCount = document.querySelector('#selected-count');
const selectedList = document.querySelector('#selected-list');
const summaryDescription = document.querySelector('#summary-description');
const generateButton = document.querySelector('#generate-button');
const buttonLabel = document.querySelector('#button-label');
const status = document.querySelector('#status');
let templates = [];

function selectedTemplates() {
  const ids = [...templateList.querySelectorAll('input:checked')].map(input => input.value);
  return templates.filter(template => ids.includes(template.id));
}

function makeField(field, templateId) {
  const label = document.createElement('label');
  label.className = 'field';
  const caption = document.createElement('span');
  caption.textContent = field.label;
  if (field.required) {
    const star = document.createElement('b');
    star.textContent = ' *';
    caption.append(star);
  }
  const control = document.createElement(field.multiline ? 'textarea' : 'input');
  if (field.multiline) control.rows = 3;
  control.dataset.templateId = templateId;
  control.dataset.fieldKey = field.key;
  control.required = field.required;
  control.maxLength = 5000;
  control.placeholder = `Enter ${field.label.toLowerCase()}`;
  label.append(caption, control);
  return label;
}

function updateSelection() {
  const selected = selectedTemplates();
  const previous = new Map([...templateFields.querySelectorAll('[data-field-key]')].map(input => [`${input.dataset.templateId}.${input.dataset.fieldKey}`, input.value]));
  templateFields.replaceChildren();
  selectedList.replaceChildren();
  selected.forEach(template => {
    const item = document.createElement('li');
    item.textContent = template.title;
    selectedList.append(item);
    if (!template.fields.length) return;
    const group = document.createElement('div');
    group.className = 'detail-group';
    const heading = document.createElement('h3');
    heading.textContent = template.title;
    const grid = document.createElement('div');
    grid.className = 'detail-fields';
    template.fields.forEach(field => {
      const label = makeField(field, template.id);
      const control = label.querySelector('input, textarea');
      control.value = previous.get(`${template.id}.${field.key}`) || '';
      grid.append(label);
    });
    group.append(heading, grid);
    templateFields.append(group);
  });
  templateList.querySelectorAll('.template-card').forEach(card => card.classList.toggle('selected', card.querySelector('input').checked));
  detailsPanel.hidden = selected.length === 0;
  selectedCount.textContent = String(selected.length).padStart(2, '0');
  summaryDescription.textContent = selected.length ? `${selected.length} document${selected.length === 1 ? '' : 's'} ready to complete and generate.` : 'Choose a template to start building your document set.';
  generateButton.disabled = selected.length === 0;
  buttonLabel.textContent = selected.length > 1 ? 'Generate PDF bundle' : 'Generate PDF';
  status.textContent = '';
}

function renderCatalog() {
  templateList.replaceChildren();
  if (!templates.length) {
    templateList.textContent = 'No templates found in the configured source.';
    return;
  }
  templates.forEach(template => {
    const card = document.createElement('label');
    card.className = 'template-card';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = template.id;
    input.addEventListener('change', updateSelection);
    const category = document.createElement('span');
    category.className = 'template-category';
    category.textContent = template.category;
    const title = document.createElement('span');
    title.className = 'template-title';
    title.textContent = template.title;
    const description = document.createElement('span');
    description.className = 'template-description';
    description.textContent = template.description;
    card.append(input, category, title, description);
    templateList.append(card);
  });
}

async function loadTemplates() {
  try {
    const response = await fetch('/api/templates', {cache: 'no-store'});
    if (!response.ok) throw new Error((await response.json()).detail || 'Could not load templates');
    templates = await response.json();
    renderCatalog();
  } catch (error) {
    templateList.textContent = 'Templates could not be loaded.';
    status.className = 'status error';
    status.textContent = error.message;
  }
}

document.querySelector('#document-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const selected = selectedTemplates();
  if (!selected.length) return;
  const fields = {};
  templateFields.querySelectorAll('[data-field-key]').forEach(input => {
    const id = input.dataset.templateId;
    fields[id] ||= {};
    fields[id][input.dataset.fieldKey] = input.value;
  });
  const payload = {
    patient: {name: document.querySelector('#patient-name').value, age: Number(document.querySelector('#patient-age').value), medical_history: document.querySelector('#medical-history').value},
    doctor: {name: document.querySelector('#doctor-name').value},
    template_ids: selected.map(template => template.id),
    fields
  };
  generateButton.disabled = true;
  buttonLabel.textContent = 'Preparing documents…';
  status.className = 'status';
  status.textContent = '';
  try {
    const response = await fetch('/api/generate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), cache: 'no-store'});
    if (!response.ok) {
      const error = await response.json();
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Please check the entered information.');
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = selected.length === 1 ? `${selected[0].id}.pdf` : 'patient-documents.zip';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    status.className = 'status success';
    status.textContent = `Created ${selected.length} document${selected.length === 1 ? '' : 's'}. Review before clinical use.`;
  } catch (error) {
    status.className = 'status error';
    status.textContent = error.message;
  } finally {
    generateButton.disabled = false;
    buttonLabel.textContent = selected.length > 1 ? 'Generate PDF bundle' : 'Generate PDF';
  }
});

loadTemplates();
