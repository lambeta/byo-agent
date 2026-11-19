const state = { data: null, view: 'overview', live: null, map: null, mapError: false, window: '7d',
  session: 'default', viewing: null, chatGen: 0, tools: null };

const VIEW_HEADS = {
  overview: ['Overview', 'The runtime map, live.'],
  tools: ['Tools', 'What the agent can call, and what its calls produced.'],
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
  else if (name === 'tools') { setHead('tools'); view.innerHTML = toolsView(state.tools); }
  else if (name === 'memory') { setHead('memory'); view.innerHTML = memoryView(data); }
  else if (name === 'settings') { setHead('settings'); view.innerHTML = settingsView(data); }
  else { setHead('overview'); location.hash = '#overview'; renderOverview(); }
  renderChat();
}

function bubble(message) {
  const me = message.role === 'user';
  // Replies are Markdown; what the person typed is shown exactly as typed.
  const body = me
    ? '<div class="bubble-body">' + esc(message.content) + '</div>'
    : '<div class="bubble-body md">' + renderMarkdown(message.content) + '</div>';
  return '<div class="bubble' + (me ? ' me' : '') + '">' +
    '<div class="bubble-meta">' + (me ? 'you' : 'byo') + ' · ' + esc(stamp(message.created_at)) + '</div>' +
    body + '</div>';
}

function renderChat() {
  const history = document.getElementById('chat-history');
  if (!history) return;
  const wanted = state.viewing || state.session;
  const generation = ++state.chatGen;
  API.get('/api/session?action=history&session_id=' + encodeURIComponent(wanted))
    .then(function (payload) {
      if (state.chatGen !== generation) return;  // a newer load won
      let messages = payload.messages || [];
      // The pinned live card already shows this turn's message and reply.
      const pinned = state.live && state.live.turn_id && !state.viewing;
      if (pinned && messages.length && messages[messages.length - 1].role === 'assistant') {
        messages = messages.slice(0, -1);
        if (messages.length && messages[messages.length - 1].role === 'user') {
          messages = messages.slice(0, -1);
        }
      }
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
  if (viewName() === 'tools') {
    try {
      state.tools = await API.get('/api/tools');
    } catch (error) {
      state.tools = { tools: [], results: [] };
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
  return {
    user_message: message,
    source: 'dashboard',
    state: 'live',
    items: [],
    reply: '',
    receipt: null,
    turn_id: null
  };
}

function lastItem(live, type, openOnly) {
  for (let index = live.items.length - 1; index >= 0; index -= 1) {
    const item = live.items[index];
    if (item.type !== type) continue;
    if (openOnly && !item.live) continue;
    return item;
  }
  return null;
}

function addItem(live, item) {
  live.items.push(item);
  return item;
}

const LANE_NODE = { llm: 'model', tool: 'tools', gate: 'gate', consolidation: 'consolidation' };

function settleRound(live, payload) {
  const round = lastItem(live, 'streaming', true);
  if (!round) return;
  round.live = false;
  round.meta = (payload.duration_ms || 0) + ' ms';
  if (payload.stop_reason === 'tool_use') {
    round.type = 'thinking';
    round.title = 'Thinking · round ' + (round.iteration || '?');
    round.node = 'model';
  } else {
    round.type = 'output';
    round.title = 'Output';
    round.node = 'reply';
    if (round.body) live.reply = round.body;
  }
}

function closeLive(live) {
  let output = null;
  live.items.forEach(function (item) {
    if (item.type === 'streaming') {
      item.type = 'output';
      item.title = 'Output';
      item.node = 'reply';
    }
    if (item.live) item.live = false;
    if (item.type === 'output') output = item;
  });
  if (output) {
    output.body = live.reply || output.body;
    output.node = 'reply';
    output.title = 'Output';
    return;
  }
  if (live.reply) {
    addItem(live, {
      type: 'output', node: 'reply', title: 'Output', body: live.reply, live: false, meta: ''
    });
  }
}

function paintLit(nodes) {
  const host = document.getElementById('chat-live');
  if (!host) return;
  let lit = nodes;
  if (!lit && typeof MapLive !== 'undefined' && MapLive.litNodes) lit = MapLive.litNodes();
  lit = lit || [];
  host.querySelectorAll('.lane[data-node]').forEach(function (lane) {
    const node = lane.getAttribute('data-node');
    const running = lane.getAttribute('data-open') === 'true' || node === 'reply';
    lane.classList.toggle('lit', !!node && running && lit.indexOf(node) !== -1);
  });
}

document.addEventListener('byo:lit', function (event) {
  paintLit((event.detail && event.detail.nodes) || []);
});

function paintLive() {
  const live = document.getElementById('chat-live');
  if (live) live.innerHTML = state.live ? liveCard(state.live) : '';
  paintLit();
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
    if (kind === 'gate_start') {
      addItem(state.live, {
        type: 'gate', node: 'gate', title: 'Memory gate', body: '', pending: 'deciding…', live: true
      });
    } else if (kind === 'gate') {
      const gate = lastItem(state.live, 'gate', false);
      if (gate) {
        gate.live = false;
        gate.pending = '';
        gate.title = 'Memory gate · ' + (payload.decision || '?');
        gate.body = payload.reason || '';
      }
      state.live.gate = { decision: payload.decision, reason: payload.reason };
    } else if (kind === 'llm_start') {
      addItem(state.live, {
        type: 'streaming', node: 'model', title: 'Thinking…', body: '', live: true,
        iteration: payload.iteration, model: payload.model || ''
      });
    } else if (kind === 'text') {
      const round = lastItem(state.live, 'streaming', true) || lastItem(state.live, 'streaming', false);
      const delta = payload.delta || '';
      if (round && delta) {
        round.body += delta;
        round.title = 'Output';
      }
    } else if (kind === 'llm') {
      settleRound(state.live, payload);
    } else if (kind === 'tool_start') {
      addItem(state.live, {
        type: 'tool', node: 'tools', title: 'Tool call · ' + (payload.tool || '?'),
        body: '', pending: 'running…', live: true, name: payload.tool, call_id: payload.call_id
      });
    } else if (kind === 'tool') {
      let tool = lastItem(state.live, 'tool', true);
      if (!tool) {
        tool = addItem(state.live, {
          type: 'tool', node: 'tools', title: 'Tool call · ' + (payload.tool || '?'),
          body: '', live: true, name: payload.tool
        });
      }
      tool.live = false;
      tool.pending = '';
      tool.title = 'Tool call · ' + (payload.tool || 'tool') + (payload.ok === false ? ' · failed' : '');
      tool.body = JSON.stringify(payload.args) + ' → ' + String(payload.output || '').slice(0, 160);
      tool.meta = (payload.duration_ms || 0) + ' ms';
    } else if (kind === 'consolidation') {
      addItem(state.live, {
        type: 'output', node: 'consolidation', title: 'Memory written',
        body: 'kept ' + (payload.new_facts || 0) + ' fact(s)', live: false, meta: ''
      });
    } else if (kind === 'error') {
      const message = (payload.error && payload.error.message) || payload.message || 'failed';
      const stage = payload.stage || 'turn';
      addItem(state.live, {
        type: 'error', node: LANE_NODE[stage] || '', title: 'Failed · ' + stage,
        body: message, live: false, meta: ''
      });
      state.live.state = 'failed';
      if (onMap) mapSetStatus('failed: ' + message, 'bad');
    } else if (kind === 'receipt') {
      state.live.receipt = payload;
    } else if (kind === 'done') {
      state.live.reply = payload.reply || state.live.reply;
      state.live.state = 'complete';
      state.live.turn_id = payload.turn_id;
      closeLive(state.live);
    }
    paintLive();
    scrollChat();
  });
  // Keep the finished card (its lanes are the only place the thinking and the tool
  // calls are readable) and hide its duplicate bubbles from the history list below.
  const finished = state.live;
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
    state.live = null;
    paintLive();
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
  input.style.height = '';   // fall back to the two-line min-height, never one clipped line
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