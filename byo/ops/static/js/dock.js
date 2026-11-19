// The Memory view — four sections mirroring the pipeline: the gate's calls,
// the facts, the episodes, and consolidation. Every section has an explicit
// empty state; the view never renders blank.

function memoryView(data) {
  const memory = data.memory || { facts: [], episodes: [], counts: {}, gate: {}, consolidation: {} };
  const gate = memory.gate || {};
  const consolidation = memory.consolidation || {};
  const facts = (memory.facts || []).map(function (fact) {
    return '<tr><td>' + esc(fact.id) + '</td><td>' + esc(fact.subject) + '</td><td>' +
      esc(fact.content) + '</td><td>' + esc(fact.source) + '</td>' +
      '<td><button onclick="editFact(' + fact.id + ')">edit</button> ' +
      '<button onclick="forgetFact(' + fact.id + ')">forget</button></td></tr>';
  }).join('');
  const episodes = (memory.episodes || []).map(function (episode) {
    return '<tr><td>' + esc(episode.happened_at) + '</td><td>' + esc(episode.summary) + '</td></tr>';
  }).join('');
  return (
    '<div class="grid">' +
    '<div class="card"><div class="meta">facts</div><div class="stat">' + (memory.counts.facts || 0) + '</div></div>' +
    '<div class="card"><div class="meta">episodes</div><div class="stat">' + (memory.counts.episodes || 0) + '</div></div>' +
    '<div class="card"><div class="meta">mirror</div><div class="mono">' + esc(memory.mirror_path) + '</div></div>' +
    '</div>' +
    '<section class="card"><h1>Gate</h1>' +
    (typeof gate.retrieve === 'number' && (gate.retrieve + gate.skip) > 0
      ? '<p>' + esc(String(gate.retrieve)) + ' retrieve · ' + esc(String(gate.skip)) + ' skip</p>' +
        '<p class="meta">last: ' + esc(gate.last_decision || '?') +
        (gate.last_reason ? ' — ' + esc(gate.last_reason) : '') + '</p>'
      : '<p class="empty">No gate decisions recorded yet.</p>') +
    '</section>' +
    '<section class="card"><h1>Facts</h1>' +
    '<form onsubmit="addFact(); return false;" style="margin-bottom:12px">' +
    '<input id="fact-subject" type="text" placeholder="subject" required> ' +
    '<input id="fact-content" type="text" placeholder="what to remember" required> ' +
    '<button class="primary" type="submit">remember</button></form>' +
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

async function addFact() {
  const subject = document.getElementById('fact-subject').value.trim();
  const content = document.getElementById('fact-content').value.trim();
  if (!subject || !content) return;
  await API.post('/api/memory', { action: 'add', subject: subject, content: content });
  await refresh();
}

async function editFact(id) {
  const content = window.prompt('Edit this fact:');
  if (content === null || !content.trim()) return;
  const row = (state.data.memory.facts || []).find(function (fact) { return fact.id === id; });
  await API.post('/api/memory', {
    action: 'edit', id: id, subject: row ? row.subject : '', content: content.trim()
  });
  await refresh();
}

async function forgetFact(id) {
  await API.post('/api/memory', { action: 'forget', id: id });
  await refresh();
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
