const state = { data: null, view: 'overview', live: null, map: null, mapError: false, window: '7d' };

function viewName() {
  return (location.hash || '#overview').slice(1) || 'overview';
}

function render() {
  const view = document.getElementById('view');
  const data = state.data;
  if (!data) { view.innerHTML = '<p class="empty">loading…</p>'; return; }
  document.getElementById('home-path').textContent = data.home;
  for (const link of document.querySelectorAll('#nav a')) {
    link.classList.toggle('active', link.dataset.view === viewName());
  }
  if (state.live && viewName() === 'chat') {
    view.innerHTML = '<h1>Chat</h1>' + state.live.html;
    return;
  }
  if (viewName() === 'overview') {
    renderOverview();
    return;
  }
  if (typeof MapLive !== 'undefined') MapLive.stop();
  if (viewName() === 'observe') view.innerHTML = observeView(data);
  else if (viewName() === 'memory') view.innerHTML = memoryView(data);
  else if (viewName() === 'settings') view.innerHTML = settingsView(data);
  else {
    const turns = (data.turns || []).slice().reverse();
    view.innerHTML = '<h1>Chat</h1>' +
      (turns.length ? turns.map(turnCard).join('') : '<p class="empty">Say something below to start.</p>');
  }
}

function renderOverview() {
  const view = document.getElementById('view');
  if (state.mapError) {
    view.innerHTML = '<h1>Overview</h1><p class="empty">The map could not be loaded. ' +
      'Check the dashboard console and try again.</p>';
    return;
  }
  if (!state.map) {
    view.innerHTML = '<h1>Overview</h1><p class="empty">Loading the map…</p>';
    return;
  }
  view.innerHTML = overviewView(state.map);
  mapBind(state.map);
  if (typeof MapLive !== 'undefined') MapLive.start(state.map);
  if (MAP_STATE.selected) {
    const stillThere = state.map.turns.some(function (turn) { return turn.turn_id === MAP_STATE.selected; });
    if (stillThere) mapOpenTurn(MAP_STATE.selected);
    else {
      MAP_STATE.selected = null;
      mapSetStatus('The selected turn is outside this window.');
    }
  }
}

async function refresh() {
  state.data = await API.get('/api/data');
  if (viewName() === 'overview') {
    try {
      state.map = await API.get('/api/map?window=' + encodeURIComponent(state.window));
      state.mapError = false;
    } catch (error) {
      state.mapError = true;
    }
  }
  render();
}

async function refreshMap(window) {
  state.window = window || state.window;
  try {
    state.map = await API.get('/api/map?window=' + encodeURIComponent(state.window));
    state.mapError = false;
  } catch (error) {
    state.mapError = true;
  }
  if (viewName() === 'overview') render();
}

function newLive(message) {
  return { user_message: message, source: 'dashboard', state: 'live', steps: [], reply: '', receipt: null };
}

function paintLive() {
  const view = document.getElementById('view');
  for (const link of document.querySelectorAll('#nav a')) link.classList.remove('active');
  view.innerHTML = '<h1>Chat</h1><div id="live">' + turnCard(state.live) + '</div>';
}

async function sendFromOverview(message) {
  mapSetStatus('sending…');
  try {
    await API.stream(message, function (kind, payload) {
      if (kind === 'error') {
        const text = (payload.error && payload.error.message) || payload.message || 'failed';
        mapSetStatus('failed: ' + text, 'bad');
      }
    });
  } catch (error) {
    mapSetStatus('failed', 'bad');
  }
  await refresh();
}

async function send(message) {
  if (viewName() === 'overview') return sendFromOverview(message);
  state.live = newLive(message);
  paintLive();
  await API.stream(message, function (kind, payload) {
    if (!state.live) return;
    if (kind === 'text') {
      state.live.reply += payload.delta || '';
    } else if (kind === 'llm') {
      state.live.steps.push({ kind: 'llm', iteration: payload.iteration, in: payload.usage ? payload.usage.in : 0,
        out: payload.usage ? payload.usage.out : 0, model: payload.model, call: payload.stop_reason,
        duration_ms: payload.duration_ms, ok: true });
    } else if (kind === 'tool') {
      state.live.steps.push({ kind: 'tool', tool: payload.tool, args: JSON.stringify(payload.args),
        output: String(payload.output || '').slice(0, 160), duration_ms: payload.duration_ms, ok: payload.ok });
    } else if (kind === 'gate') {
      state.live.gate = { decision: payload.decision, reason: payload.reason };
    } else if (kind === 'consolidation') {
      state.live.steps.push({ kind: 'memory_write', new_facts: payload.new_facts });
    } else if (kind === 'error') {
      const message = (payload.error && payload.error.message) || payload.message || 'failed';
      state.live.steps.push({ kind: 'error', message: message, ok: false });
      state.live.state = 'failed';
    } else if (kind === 'receipt') {
      state.live.receipt = payload;
    } else if (kind === 'done') {
      state.live.reply = payload.reply || state.live.reply;
      state.live.state = 'complete';
      state.live.turn_id = payload.turn_id;
    }
    paintLive();
  });
  const finished = state.live;
  state.live = null;
  await refresh();
  return finished;
}

document.getElementById('chat-form').addEventListener('submit', async function (event) {
  event.preventDefault();
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  if (viewName() === 'overview') {
    await sendFromOverview(message);
  } else {
    await send(message);
  }
});

window.addEventListener('hashchange', function () {
  state.live = null;
  if (typeof MapLive !== 'undefined') MapLive.stop();
  if (viewName() === 'overview' && state.data && !state.map) {
    refreshMap(state.window).catch(function () { render(); });
  } else {
    render();
  }
});

refresh().catch(function (error) {
  if (typeof console !== 'undefined') console.error(error);
  const message = error && error.message ? error.message : 'unknown error';
  document.getElementById('view').innerHTML =
    '<p class="empty">dashboard unreachable: ' + esc(message) + '</p>';
});
