// The Memory view — four sections mirroring the pipeline: the gate's calls,
// the facts, the episodes, and consolidation. Facts add and edit in place;
// every section has an explicit empty state; the view never renders blank.
//
// Editing state lives in MEMORY_UI so a refusal can re-render without losing
// what the person typed. The server decides every outcome; this file only
// presents it, moves focus and keeps the payload in sync.

const MEMORY_UI = {
  editingId: null,
  addDraft: null,
  editDraft: null,
  editBaseline: null,
  errors: {},
  general: null,
  notice: '',
  saving: false,
  focusSubject: false,
  focusEditId: null,
};

function resetMemoryUi() {
  MEMORY_UI.editingId = null;
  MEMORY_UI.addDraft = null;
  MEMORY_UI.editDraft = null;
  MEMORY_UI.editBaseline = null;
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  MEMORY_UI.notice = '';
  MEMORY_UI.saving = false;
  MEMORY_UI.focusSubject = false;
  MEMORY_UI.focusEditId = null;
}

function memoryPayload() {
  return state.memory || (state.data && state.data.memory) || {
    facts: [], episodes: [], counts: {}, gate: {}, consolidation: {}, warnings: []
  };
}

function fieldError(id, message) {
  return '<p class="field-error" id="' + id + '" role="alert">' + esc(message) + '</p>';
}

function addFactForm() {
  const draft = MEMORY_UI.addDraft || { subject: '', content: '' };
  const errors = MEMORY_UI.errors || {};
  const locked = MEMORY_UI.editingId !== null || MEMORY_UI.saving;
  const dis = locked ? ' disabled' : '';
  const subjectInvalid = errors.subject
    ? ' aria-invalid="true" aria-describedby="fact-subject-error"' : '';
  const contentInvalid = errors.content
    ? ' aria-invalid="true" aria-describedby="fact-content-error"' : '';
  return '<form id="fact-form" class="fact-form" novalidate onsubmit="addFact(); return false;">' +
    '<div class="fact-field">' +
    '<label for="fact-subject">subject</label>' +
    '<input id="fact-subject" type="text" placeholder="subject" value="' + esc(draft.subject) + '"' +
      subjectInvalid + dis + '>' +
    (errors.subject ? fieldError('fact-subject-error', errors.subject) : '') +
    '</div>' +
    '<div class="fact-field">' +
    '<label for="fact-content">what to remember</label>' +
    '<textarea id="fact-content" rows="3" placeholder="what to remember"' +
      contentInvalid + dis + '>' + esc(draft.content) + '</textarea>' +
    (errors.content ? fieldError('fact-content-error', errors.content) : '') +
    '</div>' +
    '<p><button class="primary" type="submit" id="fact-submit"' + dis + '>remember</button></p>' +
    '</form>';
}

function editFactRow(fact) {
  const draft = MEMORY_UI.editDraft || { subject: fact.subject, content: fact.content };
  const errors = MEMORY_UI.errors || {};
  const dis = MEMORY_UI.saving ? ' disabled' : '';
  const subjectId = 'edit-subject-' + esc(fact.id);
  const contentId = 'edit-content-' + esc(fact.id);
  const subjectInvalid = errors.subject
    ? ' aria-invalid="true" aria-describedby="' + subjectId + '-error"' : '';
  const contentInvalid = errors.content
    ? ' aria-invalid="true" aria-describedby="' + contentId + '-error"' : '';
  return '<tr class="fact-editing"><td>' + esc(fact.id) + '</td><td colspan="4">' +
    '<div class="fact-field">' +
    '<label for="' + subjectId + '">subject</label>' +
    '<input id="' + subjectId + '" type="text" value="' + esc(draft.subject) + '"' +
      subjectInvalid + dis + '>' +
    (errors.subject ? fieldError(subjectId + '-error', errors.subject) : '') +
    '</div>' +
    '<div class="fact-field">' +
    '<label for="' + contentId + '">what to remember</label>' +
    '<textarea id="' + contentId + '" rows="3"' + contentInvalid + dis + '>' +
      esc(draft.content) + '</textarea>' +
    (errors.content ? fieldError(contentId + '-error', errors.content) : '') +
    '</div>' +
    '<div class="fact-actions">' +
    '<button type="button" class="primary" onclick="saveEditFact(' + Number(fact.id) + ')"' +
      dis + '>save</button> ' +
    '<button type="button" onclick="cancelEditFact(' + Number(fact.id) + ')"' + dis + '>cancel</button>' +
    '</div></td></tr>';
}

function factRow(fact) {
  if (MEMORY_UI.editingId === Number(fact.id)) return editFactRow(fact);
  const locked = MEMORY_UI.editingId !== null || MEMORY_UI.saving;
  const dis = locked ? ' disabled' : '';
  return '<tr><td>' + esc(fact.id) + '</td><td>' + esc(fact.subject) + '</td>' +
    '<td class="fact-body">' + esc(fact.content) + '</td><td>' + esc(fact.source) + '</td>' +
    '<td class="fact-actions">' +
    '<button type="button" id="fact-edit-' + esc(fact.id) + '" onclick="startEditFact(' +
      Number(fact.id) + ')"' + dis + '>edit</button> ' +
    '<button type="button" onclick="forgetFact(' + Number(fact.id) + ')"' + dis + '>forget</button>' +
    '</td></tr>';
}

function memoryView(memory) {
  memory = memory || {};
  const gate = memory.gate || {};
  const consolidation = memory.consolidation || {};
  const counts = memory.counts || {};
  const warnings = (memory.warnings || []).map(function (warning) {
    return '<p class="fact-warning" role="status">' +
      esc(warning.message || warning.code || 'Mirror warning') + '</p>';
  }).join('');
  const general = MEMORY_UI.general
    ? '<p class="fact-error" role="alert">' + esc(MEMORY_UI.general.message) +
      (MEMORY_UI.general.existingId
        ? ' <button type="button" class="linkish" onclick="startEditFact(' +
          Number(MEMORY_UI.general.existingId) + ')">edit fact ' +
          esc(MEMORY_UI.general.existingId) + '</button>'
        : '') +
      '</p>'
    : '';
  const notice = MEMORY_UI.notice
    ? '<p class="fact-notice" role="status">' + esc(MEMORY_UI.notice) + '</p>' : '';
  const facts = (memory.facts || []).map(factRow).join('');
  const episodes = (memory.episodes || []).map(function (episode) {
    return '<tr><td>' + esc(episode.happened_at) + '</td><td>' + esc(episode.summary) + '</td></tr>';
  }).join('');
  return (
    '<div class="grid">' +
    '<div class="card"><div class="meta">facts</div><div class="stat">' + (counts.facts || 0) + '</div></div>' +
    '<div class="card"><div class="meta">episodes</div><div class="stat">' + (counts.episodes || 0) + '</div></div>' +
    '<div class="card"><div class="meta">mirror</div><div class="mono">' + esc(memory.mirror_path) + '</div></div>' +
    '</div>' +
    '<section class="card"><h1>Gate</h1>' +
    (typeof gate.retrieve === 'number' && (gate.retrieve + gate.skip) > 0
      ? '<p>' + esc(String(gate.retrieve)) + ' retrieve · ' + esc(String(gate.skip)) + ' skip</p>' +
        '<p class="meta">last: ' + esc(gate.last_decision || '?') +
        (gate.last_reason ? ' — ' + esc(gate.last_reason) : '') + '</p>'
      : '<p class="empty">No gate decisions recorded yet.</p>') +
    '</section>' +
    '<section class="card"><h1>Facts</h1>' + warnings + notice + general + addFactForm() +
    '<table><tr><th>id</th><th>subject</th><th>fact</th><th>source</th><th></th></tr>' +
    (facts || '<tr><td colspan="5" class="empty">nothing remembered yet</td></tr>') + '</table></section>' +
    '<section class="card"><h1>Episodes</h1><table><tr><th>when</th><th>what</th></tr>' +
    (episodes || '<tr><td colspan="2" class="empty">no episodes yet</td></tr>') + '</table></section>' +
    '<section class="card"><h1>Consolidation</h1>' +
    (typeof consolidation.pending === 'number'
      ? '<p>' + esc(String(consolidation.pending)) + ' of ' + esc(String(consolidation.threshold)) +
        ' messages waiting to be distilled</p>' +
        '<p class="meta">last run: ' + (consolidation.last_run_at ? esc(stamp(consolidation.last_run_at)) : 'never') + '</p>'
      : '<p class="empty">Consolidation has not run yet.</p>') +
    '</section>'
  );
}

function renderMemory() {
  const view = document.getElementById('view');
  if (!view) return;
  view.innerHTML = memoryView(memoryPayload());
  focusMemory();
}

function focusMemory() {
  const errors = MEMORY_UI.errors || {};
  if (errors.subject || errors.content) {
    const subject = Boolean(errors.subject);
    let id = subject ? 'fact-subject' : 'fact-content';
    if (MEMORY_UI.editingId !== null) {
      id = (subject ? 'edit-subject-' : 'edit-content-') + MEMORY_UI.editingId;
    }
    const field = document.getElementById(id);
    if (field) { field.focus(); return; }
  }
  if (MEMORY_UI.focusEditId !== null) {
    const button = document.getElementById('fact-edit-' + MEMORY_UI.focusEditId);
    MEMORY_UI.focusEditId = null;
    if (button) { button.focus(); return; }
  }
  if (MEMORY_UI.focusSubject) {
    MEMORY_UI.focusSubject = false;
    const field = document.getElementById('fact-subject');
    if (field) field.focus();
  }
}

function applyMemoryResult(result, kind) {
  state.memory = result.memory;
  if (result.warnings) state.memory.warnings = result.warnings;
  if (state.data) state.data.memory = result.memory;
  MEMORY_UI.saving = false;
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  if (kind === 'add') {
    MEMORY_UI.addDraft = null;
    MEMORY_UI.notice = 'Remembered' + (result.fact ? ': [' + result.fact.subject + ']' : '.');
    MEMORY_UI.focusSubject = true;
  } else {
    const id = result.fact ? result.fact.id : MEMORY_UI.editingId;
    MEMORY_UI.editingId = null;
    MEMORY_UI.editDraft = null;
    MEMORY_UI.editBaseline = null;
    MEMORY_UI.notice = 'Updated fact ' + id + '.';
    MEMORY_UI.focusEditId = id;
  }
  renderMemory();
}

function handleMemoryError(error) {
  const code = error.code || 'fact_failed';
  const message = error.message || 'The change was refused.';
  MEMORY_UI.saving = false;
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  MEMORY_UI.notice = '';
  if (code === 'fact_validation' && (error.field === 'subject' || error.field === 'content')) {
    MEMORY_UI.errors[error.field] = message;
    renderMemory();
    return;
  }
  if (code === 'fact_duplicate') {
    MEMORY_UI.general = { message: message, existingId: error.existing_id || null };
    renderMemory();
    return;
  }
  if (code === 'fact_conflict' || code === 'fact_not_found') {
    MEMORY_UI.editingId = null;
    MEMORY_UI.editDraft = null;
    MEMORY_UI.editBaseline = null;
    MEMORY_UI.general = { message: message };
    renderMemory();
    reloadMemory().then(function () { renderMemory(); });
    return;
  }
  MEMORY_UI.general = { message: message };
  renderMemory();
}

async function postMemory(payload, kind) {
  try {
    const result = await API.post('/api/memory', payload);
    if (result && result.error) {
      handleMemoryError(result.error);
      return;
    }
    if (!result || !result.memory) {
      handleMemoryError({ code: 'fact_failed', message: 'The dashboard returned no memory payload.' });
      return;
    }
    applyMemoryResult(result, kind);
  } catch (error) {
    MEMORY_UI.saving = false;
    MEMORY_UI.errors = {};
    MEMORY_UI.general = {
      message: 'The change could not be saved: ' +
        (error && error.message ? error.message : 'network error') + '.'
    };
    renderMemory();
  }
}

async function reloadMemory() {
  try {
    const memory = await API.get('/api/memory');
    state.memory = memory;
    if (state.data) state.data.memory = memory;
  } catch (error) {
    // Keep whatever is on screen; the next navigation will try again.
  }
}

function startEditFact(id) {
  const fact = (memoryPayload().facts || []).find(function (row) {
    return Number(row.id) === Number(id);
  });
  if (!fact) return;
  MEMORY_UI.editingId = Number(fact.id);
  MEMORY_UI.editDraft = { subject: fact.subject, content: fact.content };
  MEMORY_UI.editBaseline = { subject: fact.subject, content: fact.content };
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  MEMORY_UI.notice = '';
  renderMemory();
  const input = document.getElementById('edit-subject-' + fact.id);
  if (input) input.focus();
}

function saveEditFact(id) {
  if (MEMORY_UI.saving || !MEMORY_UI.editBaseline) return;
  const subject = document.getElementById('edit-subject-' + id);
  const content = document.getElementById('edit-content-' + id);
  if (!subject || !content) return;
  MEMORY_UI.editDraft = { subject: subject.value, content: content.value };
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  MEMORY_UI.notice = '';
  MEMORY_UI.saving = true;
  renderMemory();
  postMemory({
    action: 'edit',
    id: Number(id),
    subject: MEMORY_UI.editDraft.subject,
    content: MEMORY_UI.editDraft.content,
    baseline_subject: MEMORY_UI.editBaseline.subject,
    baseline_content: MEMORY_UI.editBaseline.content,
  }, 'edit');
}

function cancelEditFact(id) {
  MEMORY_UI.editingId = null;
  MEMORY_UI.editDraft = null;
  MEMORY_UI.editBaseline = null;
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  MEMORY_UI.notice = '';
  MEMORY_UI.focusEditId = Number(id);
  renderMemory();
}

function addFact() {
  if (MEMORY_UI.saving || MEMORY_UI.editingId !== null) return;
  const subject = document.getElementById('fact-subject');
  const content = document.getElementById('fact-content');
  if (!subject || !content) return;
  MEMORY_UI.addDraft = { subject: subject.value, content: content.value };
  MEMORY_UI.errors = {};
  MEMORY_UI.general = null;
  MEMORY_UI.notice = '';
  MEMORY_UI.saving = true;
  renderMemory();
  postMemory({
    action: 'add',
    subject: MEMORY_UI.addDraft.subject,
    content: MEMORY_UI.addDraft.content,
  }, 'add');
}

async function forgetFact(id) {
  if (MEMORY_UI.saving || MEMORY_UI.editingId !== null) return;
  MEMORY_UI.saving = true;
  renderMemory();
  try {
    const result = await API.post('/api/memory', { action: 'forget', id: Number(id) });
    MEMORY_UI.saving = false;
    if (result && result.error) {
      handleMemoryError(result.error);
      return;
    }
    if (result && result.memory) {
      state.memory = result.memory;
      if (result.warnings) state.memory.warnings = result.warnings;
      if (state.data) state.data.memory = result.memory;
    }
    MEMORY_UI.general = null;
    MEMORY_UI.errors = {};
    MEMORY_UI.notice = 'Forgot fact ' + Number(id) + '.';
    renderMemory();
  } catch (error) {
    MEMORY_UI.saving = false;
    MEMORY_UI.general = {
      message: 'The fact could not be forgotten: ' +
        (error && error.message ? error.message : 'network error') + '.'
    };
    renderMemory();
  }
}

function settingsView(data) {
  const settings = data.settings || {};
  return '<section class="card">' +
    '<div class="meta"><span>home ' + esc(settings.home) + '</span></div>' +
    '<label for="provider">provider</label>' +
    '<input id="provider" type="text" value="' + esc(settings.provider) + '">' +
    '<label for="model">model</label>' +
    '<input id="model" type="text" value="' + esc(settings.model) + '">' +
    '<label for="api_key">API key ' + (settings.has_key ? '(a key is set)' : '(none set)') + '</label>' +
    '<input id="api_key" type="password" placeholder="paste to replace, never shown again">' +
    '<p><button class="primary" onclick="saveSettings()">Save</button></p>' +
    '</section>';
}

async function saveSettings() {
  const provider = document.getElementById('provider').value;
  const model = document.getElementById('model').value;
  const apiKey = document.getElementById('api_key').value;
  const payload = { provider: provider, model: model };
  if (apiKey) payload.api_key = apiKey;
  await API.post('/api/settings', payload);
  await refresh();
}
