const state = { data: null, view: 'overview', live: null, map: null, mapError: false, window: '7d',
  session: 'default', viewing: null, chatGen: 0 };

const VIEW_HEADS = {
  overview: ['Overview', 'The runtime map, live.'],
  memory: ['Memory', 'Facts and episodes the agent kept.'],
  observe: ['Observability', 'Turns, timing and spend.'],
  settings: ['Settings', 'Provider, model and key.'],
};

function setHead(name) {
  const head = VIEW_HEADS[name] || VIEW_HEADS.overview;
  document.getElementById('title').textContent = head[0];
  document.getElementById('sub').textContent = head[1];
}

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
  const name = viewName();
  if (name === 'overview') {
    setHead('overview');
    renderOverview();
    renderChat();
    return;
  }
  if (typeof MapLive !== 'undefined') MapLive.stop();
  if (name === 'observe') { setHead('observe'); view.innerHTML = observeView(data); }
  else if (name === 'memory') { setHead('memory'); view.innerHTML = memoryView(data); }
  else if (name === 'settings') { setHead('settings'); view.innerHTML = settingsView(data); }
  else { setHead('overview'); location.hash = '#overview'; renderOverview(); }
  renderChat();
}

function bubble(message) {
  const me = message.role === 'user';
  return '<div class="bubble' + (me ? ' me' : '') + '">' +
    '<div class="bubble-meta">' + (me ? 'you' : 'byo') + ' · ' + esc(stamp(message.created_at)) + '</div>' +
    '<div class="bubble-body">' + esc(message.content) + '</div></div>';
}

function renderChat() {
  const history = document.getElementById('chat-history');
  if (!history) return;
  const wanted = state.viewing || state.session;
  const generation = ++state.chatGen;
  API.get('/api/session?action=history&session_id=' + encodeURIComponent(wanted))
    .then(function (payload) {
      if (state.chatGen !== generation) return;  // a newer load won
      const messages = payload.messages || [];
      const past = state.viewing && state.viewing !== state.session;
      history.innerHTML =
        (past ? '<p class="empty">Reading a past session — sending returns to the current chat.</p>' : '') +
        (messages.length
          ? messages.map(bubble).join('')
          : '<p class="empty">Say something in the composer to start.</p>');
      scrollChat();
    })
    .catch(function () {
      if (state.chatGen !== generation) return;
      history.innerHTML = '<p class="empty">History unavailable.</p>';
    });
}

function scrollChat() {
  const log = document.getElementById('docklog');
  if (log) log.scrollTop = log.scrollHeight;
}

function renderSessionPicker(sessions) {
  const select = document.getElementById('chat-sessions');
  if (!select) return;
  const list = [{ session_id: state.session, messages: 0, last: '' }].concat(
    (sessions || []).filter(function (row) { return row.session_id !== state.session; })
  );
  select.innerHTML = list.map(function (row) {
    const label = row.session_id + (row.messages ? ' · ' + row.messages : '');
    const current = (state.viewing || state.session) === row.session_id;
    return '<option value="' + esc(row.session_id) + '"' + (current ? ' selected' : '') + '>' +
      esc(label) + '</option>';
  }).join('');
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
  if (typeof MapLive !== 'undefined') {
    // A refresh re-renders the SVG; keep the running poller so the settle is not cut short.
    if (MapLive.started) MapLive.tick(); else MapLive.start();
  }
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
  try {
    const session = await API.get('/api/session');
    state.session = session.current || state.session;
    renderSessionPicker(session.sessions);
  } catch (error) { /* older server: keep the default session */ }
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
  const live = document.getElementById('chat-live');
  if (live) live.innerHTML = state.live ? turnCard(state.live) : '';
}

async function send(message) {
  if (state.viewing && state.viewing !== state.session) {
    state.viewing = null;
    renderSessionPicker(state.data && state.data.sessions);
    renderChat();
  }
  state.live = newLive(message);
  paintLive();
  scrollChat();
  const onMap = typeof mapSetStatus === 'function' && document.getElementById('map-status');
  if (onMap) mapSetStatus('sending…');
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
      if (onMap) mapSetStatus('failed: ' + message, 'bad');
    } else if (kind === 'receipt') {
      state.live.receipt = payload;
    } else if (kind === 'done') {
      state.live.reply = payload.reply || state.live.reply;
      state.live.state = 'complete';
      state.live.turn_id = payload.turn_id;
    }
    paintLive();
    scrollChat();
  });
  const finished = state.live;
  state.live = null;
  paintLive();
  await refresh();
  return finished;
}

// Shell behaviors: rail collapse, dock collapse/reopen, drag resizer, autogrow composer.
(function () {
  const body = document.body;

  const navCollapse = document.getElementById('nav-collapse');
  navCollapse.addEventListener('click', function () {
    const collapsed = body.classList.toggle('rail-collapsed');
    navCollapse.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    navCollapse.innerHTML = collapsed ? '&#8250;' : '&#8249;';
  });

  const dockClose = document.getElementById('dock-close');
  dockClose.addEventListener('click', function () { body.classList.add('dock-closed'); });
  document.getElementById('dock-reopen').addEventListener('click', function () {
    body.classList.remove('dock-closed');
    const input = document.getElementById('chat-input');
    if (input) input.focus();
  });

  const resizer = document.getElementById('dock-resizer');
  let dragging = false;
  resizer.addEventListener('mousedown', function (event) {
    dragging = true;
    event.preventDefault();
  });
  window.addEventListener('mousemove', function (event) {
    if (!dragging) return;
    const width = Math.min(640, Math.max(280, window.innerWidth - event.clientX - 8));
    document.documentElement.style.setProperty('--dock-w', width + 'px');
  });
  window.addEventListener('mouseup', function () {
    if (!dragging) return;
    dragging = false;
    try {
      localStorage.setItem('byo-dock-w',
        document.documentElement.style.getPropertyValue('--dock-w'));
    } catch (error) { /* private mode */ }
  });
  try {
    const savedWidth = localStorage.getItem('byo-dock-w');
    if (savedWidth) document.documentElement.style.setProperty('--dock-w', savedWidth);
  } catch (error) { /* private mode */ }

  const input = document.getElementById('chat-input');
  function autogrow() {
    input.style.height = 'auto';
    input.style.height = Math.min(160, input.scrollHeight) + 'px';
  }
  input.addEventListener('input', autogrow);
  input.addEventListener('keydown', function (event) {
    // Never submit mid-composition: CJK IMEs confirm candidates with Enter.
    if (event.isComposing || event.keyCode === 229) return;
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      document.getElementById('chat-form').requestSubmit();
    }
  });

  document.getElementById('new-chat').addEventListener('click', async function () {
    const result = await API.post('/api/session', { action: 'new' });
    if (result && result.session_id) {
      state.session = result.session_id;
      state.viewing = null;
      await refresh();
    }
  });
  document.getElementById('chat-sessions').addEventListener('change', function (event) {
    state.viewing = event.target.value;
    renderChat();
  });
})();

// Theme toggle: light is the default; the choice persists across visits.
(function () {
  const button = document.getElementById('theme-toggle');
  if (!button) return;
  function paint() {
    const mode = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    button.textContent = 'theme: ' + mode;
    button.setAttribute('aria-pressed', mode === 'dark' ? 'true' : 'false');
  }
  button.addEventListener('click', function () {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('byo-theme', next); } catch (error) { /* private mode */ }
    paint();
  });
  paint();
})();

document.getElementById('chat-form').addEventListener('submit', async function (event) {
  event.preventDefault();
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  input.style.height = 'auto';
  await send(message);
});

window.addEventListener('hashchange', function () {
  state.live = null;
  paintLive();
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