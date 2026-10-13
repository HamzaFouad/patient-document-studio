const state = {patients: [], catalog: [], selectedPatientId: null, patient: null, orders: [], lastDoctorName: ''};
const $ = selector => document.querySelector(selector);

function node(tag, className = '', text = '') {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function toast(message, error = false) {
  const target = $('#toast');
  target.textContent = message;
  target.className = `toast visible ${error ? 'error' : ''}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { target.className = 'toast'; }, 5000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: options.body ? {'Content-Type': 'application/json', ...(options.headers || {})} : options.headers,
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Please check the entered information.';
    throw new Error(detail);
  }
  return data;
}

async function download(path, fallbackName) {
  const response = await fetch(path, {cache: 'no-store'});
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || 'Could not create the document.');
  }
  const blob = await response.blob();
  const header = response.headers.get('Content-Disposition') || '';
  const filename = /filename="([^"]+)"/.exec(header)?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function button(label, className, onClick) {
  const element = node('button', className, label);
  element.type = 'button';
  element.addEventListener('click', onClick);
  return element;
}

function renderCounts() {
  $('#patient-count').textContent = state.patients.length;
  $('#order-count').textContent = state.patients.reduce((sum, patient) => sum + patient.order_count, 0);
  $('#form-count').textContent = new Set(state.catalog.flatMap(lab => lab.tests.map(test => test.template_id))).size;
  $('#download-summary').disabled = state.patients.length === 0;
}

function renderPatientList() {
  const list = $('#patient-list');
  list.replaceChildren();
  const query = $('#search').value.trim().toLocaleLowerCase();
  const matches = state.patients.filter(patient => `${patient.name} ${patient.code}`.toLocaleLowerCase().includes(query));
  $('#list-count').textContent = matches.length;
  if (!matches.length) {
    const empty = node('div', 'empty-list');
    empty.append(node('span', 'empty-icon', '＋'), node('h3', '', query ? 'No matching patients' : 'No patients yet'), node('p', '', query ? 'Try another name or code.' : 'Add your first patient to start creating orders.'));
    list.append(empty);
    return;
  }
  matches.forEach(patient => {
    const card = node('article', `patient-card${patient.id === state.selectedPatientId ? ' active' : ''}`);
    const info = node('div', 'patient-card-info');
    info.append(node('span', 'patient-code', patient.code), node('h3', '', patient.name), node('p', '', `Age ${patient.age}  ·  ${patient.order_count} order${patient.order_count === 1 ? '' : 's'}`));
    const actions = node('div', 'patient-card-actions');
    actions.append(button('Open', 'button small subtle', () => selectPatient(patient.id)), button('＋ Add order', 'button small outline', () => openOrder(patient.id)));
    card.append(info, actions);
    list.append(card);
  });
}

function renderDetail() {
  const detail = $('#patient-detail');
  detail.replaceChildren();
  const patient = state.patient;
  if (!patient) {
    const empty = node('div', 'empty-detail');
    empty.append(node('span', '', '▤'), node('h3', '', 'Select a patient'), node('p', '', 'Open a patient to review their history and create an order.'));
    detail.append(empty);
    return;
  }
  const header = node('div', 'detail-identity');
  const identity = node('div');
  identity.append(node('span', 'patient-code', patient.code), node('h3', '', patient.name));
  header.append(identity, node('span', 'age-badge', `${patient.age} years`));
  const history = node('div', 'history-box');
  history.append(node('span', 'detail-label', 'MEDICAL CONDITIONS / HISTORY'), node('p', '', patient.medical_history || 'No history recorded.'));
  const actions = node('div', 'detail-actions');
  actions.append(
    button('＋ Add order', 'button primary', () => openOrder(patient.id)),
    button('Edit patient', 'button subtle', () => openPatient(patient)),
    button('Delete patient', 'button text-danger', () => deletePatient(patient)),
  );
  const heading = node('div', 'orders-heading');
  heading.append(node('h3', '', 'Orders'), node('span', 'count-pill', String(state.orders.length)));
  const list = node('div', 'order-list');
  if (!state.orders.length) {
    list.append(node('p', 'no-orders', 'No orders for this patient yet.'));
  } else {
    state.orders.forEach(order => {
      const card = node('article', 'order-card');
      const top = node('div', 'order-top');
      const title = node('div');
      title.append(node('strong', '', `Order #${order.id}`), node('span', '', new Date(order.created_at).toLocaleDateString()));
      top.append(title, node('span', 'copy-badge', `${order.copies} cop${order.copies === 1 ? 'y' : 'ies'}/form`));
      const tests = node('p', 'order-tests', order.tests.map(test => test.name).join(' · '));
      const bottom = node('div', 'order-bottom');
      bottom.append(button('↓ Download forms', 'button small outline', () => download(`/api/orders/${order.id}/documents`, `order-${order.id}.zip`).catch(error => toast(error.message, true))), button('Delete order', 'button small text-danger', () => deleteOrder(patient.id, order)));
      card.append(top, tests, bottom);
      list.append(card);
    });
  }
  detail.append(header, history, actions, heading, list);
}

async function refreshPatients(selectId = state.selectedPatientId) {
  state.patients = await api('/api/patients');
  if (selectId && !state.patients.some(patient => patient.id === selectId)) selectId = null;
  state.selectedPatientId = selectId;
  renderCounts();
  renderPatientList();
  if (selectId) await selectPatient(selectId);
  else { state.patient = null; state.orders = []; renderDetail(); }
}

async function selectPatient(patientId) {
  state.selectedPatientId = patientId;
  renderPatientList();
  const [patient, orders] = await Promise.all([api(`/api/patients/${patientId}`), api(`/api/patients/${patientId}/orders`)]);
  if (state.selectedPatientId !== patientId) return;
  state.patient = patient;
  state.orders = orders;
  renderDetail();
}

function openPatient(patient = null) {
  const form = $('#patient-form');
  form.reset();
  form.dataset.patientId = patient?.id || '';
  $('#patient-dialog-title').textContent = patient ? `Edit ${patient.code}` : 'New patient';
  if (patient) {
    form.elements.name.value = patient.name;
    form.elements.age.value = patient.age;
    form.elements.medical_history.value = patient.medical_history;
  }
  $('#patient-dialog').showModal();
}

async function savePatient(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const patientId = form.dataset.patientId;
  const data = {name: form.elements.name.value, age: Number(form.elements.age.value), medical_history: form.elements.medical_history.value};
  try {
    const saved = await api(patientId ? `/api/patients/${patientId}` : '/api/patients', {method: patientId ? 'PUT' : 'POST', body: JSON.stringify(data)});
    $('#patient-dialog').close();
    await refreshPatients(saved.id);
    toast(patientId ? 'Patient updated.' : `${saved.code} added to the registry.`);
  } catch (error) { toast(error.message, true); }
}

function renderLabs() {
  const list = $('#lab-list');
  list.replaceChildren();
  state.catalog.forEach(lab => {
    const group = node('section', 'lab-group');
    const header = node('div', 'lab-heading');
    header.append(node('h3', '', lab.name), node('span', '', `${lab.tests.length} tests`));
    group.append(header);
    const tests = node('div', 'test-options');
    lab.tests.forEach(test => {
      const label = node('label', 'test-option');
      const input = document.createElement('input');
      input.type = 'checkbox'; input.name = 'test_ids'; input.value = test.id;
      input.addEventListener('change', updateSelectedTests);
      label.append(input, node('span', '', test.name));
      tests.append(label);
    });
    group.append(tests);
    list.append(group);
  });
}

function updateSelectedTests() {
  const count = $('#order-form').querySelectorAll('input[name="test_ids"]:checked').length;
  $('#selected-tests').textContent = `${count} test${count === 1 ? '' : 's'} selected`;
}

function openOrder(patientId) {
  state.selectedPatientId = patientId;
  renderPatientList();
  const patient = state.patients.find(item => item.id === patientId);
  const form = $('#order-form');
  form.reset();
  form.dataset.patientId = patientId;
  form.elements.doctor_name.value = state.lastDoctorName;
  $('#order-dialog-title').textContent = `Order for ${patient.name}`;
  renderLabs();
  updateSelectedTests();
  $('#order-dialog').showModal();
}

async function saveOrder(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const ids = [...form.querySelectorAll('input[name="test_ids"]:checked')].map(input => input.value);
  if (!ids.length) { toast('Select at least one test.', true); return; }
  const patientId = Number(form.dataset.patientId);
  const data = {test_ids: ids, doctor_name: form.elements.doctor_name.value, clinical_question: form.elements.clinical_question.value, copies: Number(form.elements.copies.value)};
  try {
    const order = await api(`/api/patients/${patientId}/orders`, {method: 'POST', body: JSON.stringify(data)});
    state.lastDoctorName = data.doctor_name;
    $('#order-dialog').close();
    await refreshPatients(patientId);
    await download(`/api/orders/${order.id}/documents`, `order-${order.id}.zip`);
    toast(`Order #${order.id} saved and forms downloaded.`);
  } catch (error) { toast(error.message, true); }
}

async function deletePatient(patient) {
  if (!window.confirm(`Delete ${patient.name} (${patient.code}) and all their orders? This cannot be undone.`)) return;
  try {
    await api(`/api/patients/${patient.id}`, {method: 'DELETE'});
    await refreshPatients(null);
    toast(`${patient.code} deleted.`);
  } catch (error) { toast(error.message, true); }
}

async function deleteOrder(patientId, order) {
  if (!window.confirm(`Delete order #${order.id}? This cannot be undone.`)) return;
  try {
    await api(`/api/patients/${patientId}/orders/${order.id}`, {method: 'DELETE'});
    await refreshPatients(patientId);
    toast(`Order #${order.id} deleted.`);
  } catch (error) { toast(error.message, true); }
}

async function updatePurgePreview() {
  const days = Number($('#cleanup-form').elements.older_than_days.value);
  const label = $('#purge-preview');
  if (!Number.isInteger(days) || days < 1 || days > 3650) { label.textContent = 'Enter a number between 1 and 3650.'; return; }
  try {
    const result = await api(`/api/maintenance/purge-preview?older_than_days=${days}`);
    label.textContent = `${result.count} patient${result.count === 1 ? '' : 's'} would be deleted.`;
    $('#purge-button').disabled = result.count === 0;
  } catch (error) { label.textContent = error.message; }
}

async function purgePatients(event) {
  event.preventDefault();
  const days = Number(event.currentTarget.elements.older_than_days.value);
  try {
    const preview = await api(`/api/maintenance/purge-preview?older_than_days=${days}`);
    if (!preview.count) return;
    if (!window.confirm(`Permanently delete ${preview.count} patient${preview.count === 1 ? '' : 's'} older than ${days} days, including their orders?`)) return;
    const result = await api('/api/maintenance/purge', {method: 'POST', body: JSON.stringify({older_than_days: days})});
    $('#cleanup-dialog').close();
    await refreshPatients();
    toast(`${result.deleted} patient${result.deleted === 1 ? '' : 's'} deleted.`);
  } catch (error) { toast(error.message, true); }
}

document.addEventListener('click', event => {
  const id = event.target.closest('[data-close]')?.dataset.close;
  if (id) document.getElementById(id).close();
});
$('#add-patient').addEventListener('click', () => openPatient());
$('#patient-form').addEventListener('submit', savePatient);
$('#order-form').addEventListener('submit', saveOrder);
$('#search').addEventListener('input', renderPatientList);
$('#download-summary').addEventListener('click', () => download('/api/summary.pdf', 'patient-summary.pdf').catch(error => toast(error.message, true)));
$('#open-cleanup').addEventListener('click', () => { $('#cleanup-dialog').showModal(); updatePurgePreview(); });
$('#cleanup-form').elements.older_than_days.addEventListener('input', updatePurgePreview);
$('#cleanup-form').addEventListener('submit', purgePatients);

Promise.all([api('/api/catalog'), api('/api/patients')]).then(([catalog, patients]) => {
  state.catalog = catalog;
  state.patients = patients;
  renderCounts();
  renderPatientList();
  if (patients.length) selectPatient(patients[0].id);
}).catch(error => toast(error.message, true));
