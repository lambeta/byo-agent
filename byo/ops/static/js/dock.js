function memoryView(data) {
  const memory = data.memory || { facts: [], episodes: [], counts: {} };
  const rows = (memory.facts || []).map(function (fact) {
    return '<tr><td>' + esc(fact.id) + '</td><td>' + esc(fact.subject) + '</td><td>' +
      esc(fact.content) + '</td><td>' + esc(fact.source) + '</td>' +
      '<td><button onclick="forgetFact(' + fact.id + ')">forget</button></td></tr>';
  }).join('');
  const episodes = (memory.episodes || []).map(function (episode) {
    return '<tr><td>' + esc(episode.happened_at) + '</td><td>' + esc(episode.summary) + '</td></tr>';
  }).join('');
  return '<h1>Memory</h1>' +
    '<div class="grid">' +
    '<div class="card"><div class="meta">facts</div><div class="stat">' + (memory.counts.facts || 0) + '</div></div>' +
    '<div class="card"><div class="meta">episodes</div><div class="stat">' + (memory.counts.episodes || 0) + '</div></div>' +
    '<div class="card"><div class="meta">mirror</div><div class="mono">' + esc(memory.mirror_path) + '</div></div>' +
    '</div>' +
    '<section class="card bento-4"><h1>Facts</h1><table><tr><th>id</th><th>subject</th><th>fact</th><th>source</th><th></th></tr>' +
    (rows || '<tr><td colspan="5" class="empty">nothing remembered yet</td></tr>') + '</table></section>' +
    '<section class="card bento-2"><h1>Episodes</h1><table><tr><th>when</th><th>what</th></tr>' +
    (episodes || '<tr><td colspan="2" class="empty">no episodes yet</td></tr>') + '</table></section>';
}

function settingsView(data) {
  const settings = data.settings || {};
  return '<h1>Settings</h1><section class="card bento-4">' +
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