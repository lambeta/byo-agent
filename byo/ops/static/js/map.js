// byo dashboard — the runtime map and its secondary turn detail.
// Mechanism: render a server-owned graph as inline SVG, expose the same graph as a text
// list, and let live.js drive node/edge state from the recorded event feed. The map is a
// renderer, not a second source of truth; every label and number comes from /api/map.
// Rejected alternative: a hand-authored SVG or a graph library. Both drift from the Python
// graph and make the destination/event invariants untestable outside a browser.
const MAP_STATE = { data: null, window: '7d', selected: null, detail: null };

const MAP_STATE_WORDS = {
  idle: 'idle', live: 'running', done: 'done', skipped: 'skipped',
  degraded: 'degraded', failed: 'failed', 'not-reached': 'not reached', partial: 'partial'
};

function mapSource(source) {
  return source === 'cli' ? 'cli' : (source || 'dashboard');
}

function mapTruncate(value, limit) {
  const text = String(value == null ? '' : value);
  return text.length > limit ? text.slice(0, limit - 1) + '…' : text;
}

function mapMoney(value, estimate) {
  if (value == null) return 'not recorded';
  const text = Number(value).toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  return (estimate ? '~' : '') + '$' + (text || '0');
}

function mapStatus(text, kind) {
  const el = document.getElementById('map-status');
  if (!el) return;
  el.textContent = text;
  if (kind) el.setAttribute('data-kind', kind); else el.removeAttribute('data-kind');
}

function mapSetStatus(text, kind) {
  mapStatus(text, kind);
}

function mapMarkStale(flag) {
  const el = document.getElementById('map-status');
  if (el) el.setAttribute('data-stale', flag ? 'true' : 'false');
  const svg = document.getElementById('map-svg');
  if (svg) svg.setAttribute('data-stale', flag ? 'true' : 'false');
}

function mapNodeById(id) {
  if (!MAP_STATE.data || !MAP_STATE.data.map) return null;
  return MAP_STATE.data.map.nodes.find(function (node) { return node.id === id; }) || null;
}

function mapStateWord(state) {
  return MAP_STATE_WORDS[state] || state;
}

function mapSetNodeState(id, state) {
  const node = mapNodeById(id);
  const el = document.querySelector('[data-node="' + id + '"]');
  if (el) {
    el.setAttribute('data-state', state);
    const stateEl = el.querySelector('.map-node-state');
    if (stateEl) stateEl.textContent = mapStateWord(state);
    if (node) {
      el.setAttribute('aria-label', node.label + ' — ' + node.summary + ' — ' + mapStateWord(state));
    }
  }
  const text = document.querySelector('[data-text-node="' + id + '"]');
  if (text) {
    text.setAttribute('data-state', state);
    const dot = text.querySelector('.state-dot');
    if (dot) dot.setAttribute('data-state', state);
    const stateEl = text.querySelector('.text-state');
    if (stateEl) stateEl.textContent = mapStateWord(state);
  }
}

function mapSetEdgeState(id, state) {
  const el = document.querySelector('[data-edge="' + id + '"]');
  if (el) el.setAttribute('data-state', state);
}

function mapResetNodes() {
  if (!MAP_STATE.data || !MAP_STATE.data.map) return;
  MAP_STATE.data.map.nodes.forEach(function (node) { mapSetNodeState(node.id, 'idle'); });
  MAP_STATE.data.map.edges.forEach(function (edge) { mapSetEdgeState(edge.id, 'idle'); });
  mapMarkStale(false);
}

function mapMarkUnreached(touched) {
  if (!MAP_STATE.data || !MAP_STATE.data.map) return;
  MAP_STATE.data.map.nodes.forEach(function (node) {
    if (!touched || !touched.has(node.id)) mapSetNodeState(node.id, 'not-reached');
  });
}

function mapNodeCenter(node) {
  return { x: node.x + node.w / 2, y: node.y + node.h / 2 };
}

function mapEdgePath(edge, nodes) {
  const a = nodes[edge.source];
  const b = nodes[edge.target];
  if (!a || !b) return '';
  const ca = mapNodeCenter(a);
  const cb = mapNodeCenter(b);
  if (edge.id === 'e-reply-surfaces') {
    return 'M ' + ca.x + ' ' + ca.y + ' C ' + ca.x + ' 26, ' + cb.x + ' 26, ' + cb.x + ' ' + cb.y;
  }
  const offset = edge.id === 'e-tools-model' ? -10 : (edge.id === 'e-model-tools' ? 10 : 0);
  const mx = (ca.x + cb.x) / 2 + offset;
  const my = (ca.y + cb.y) / 2;
  if (Math.abs(ca.y - cb.y) < 2 || Math.abs(ca.x - cb.x) < 2) {
    return 'M ' + ca.x + ' ' + ca.y + ' L ' + cb.x + ' ' + cb.y;
  }
  return 'M ' + ca.x + ' ' + ca.y + ' C ' + mx + ' ' + ca.y + ', ' + mx + ' ' + cb.y + ', ' + cb.x + ' ' + cb.y;
}

function mapSvg(data) {
  const nodes = {};
  data.map.nodes.forEach(function (node) { nodes[node.id] = node; });
  const groups = data.map.groups.map(function (group) {
    return '<rect class="map-group" x="' + group.x + '" y="' + group.y + '" width="' + group.w +
      '" height="' + group.h + '" rx="14"/>' +
      '<text class="map-group-label" x="' + (group.x + 12) + '" y="' + (group.y + 20) + '">' +
      esc(group.label) + '</text>';
  }).join('');
  const labelled = new Set([
    'e-gate-facts', 'e-model-tools', 'e-tools-model', 'e-reply-surfaces',
    'e-reply-record', 'e-reply-consolidation', 'e-consolidation-facts', 'e-record-cost'
  ]);
  const edges = data.map.edges.map(function (edge) {
    const a = nodes[edge.source];
    const b = nodes[edge.target];
    const ca = mapNodeCenter(a);
    const cb = mapNodeCenter(b);
    let labelX = (ca.x + cb.x) / 2;
    let labelY = (ca.y + cb.y) / 2 - 5;
    if (edge.id === 'e-reply-surfaces') {
      labelX = (ca.x + cb.x) / 2;
      labelY = 20;
    } else if (edge.id === 'e-model-tools') {
      labelX = ca.x - 12;
      labelY = (ca.y + cb.y) / 2;
    } else if (edge.id === 'e-tools-model') {
      labelX = ca.x + 20;
      labelY = (ca.y + cb.y) / 2;
    }
    const label = labelled.has(edge.id)
      ? '<text class="map-edge-label" x="' + labelX + '" y="' + labelY + '">' +
        esc(edge.label) + '</text>'
      : '';
    return '<g class="map-edge-group" aria-hidden="true"><title>' + esc(edge.label) + '</title>' +
      '<path class="map-edge' + (edge.dashed ? ' dashed' : '') + '" data-edge="' + edge.id +
      '" d="' + mapEdgePath(edge, nodes) + '" marker-end="url(#map-arrow)"/>' + label +
      '</g>';
  }).join('');
  const nodesHtml = data.map.nodes.map(function (node) {
    const center = mapNodeCenter(node);
    const shape = node.shape === 'diamond'
      ? '<polygon class="node-box" points="' + center.x + ',' + node.y + ' ' +
        (node.x + node.w) + ',' + center.y + ' ' + center.x + ',' + (node.y + node.h) + ' ' +
        node.x + ',' + center.y + '"/>'
      : '<rect class="node-box" x="' + node.x + '" y="' + node.y + '" width="' + node.w +
        '" height="' + node.h + '" rx="9"/>';
    const textX = node.shape === 'diamond' ? center.x : node.x + 10;
    const anchor = node.shape === 'diamond' ? 'middle' : 'start';
    const labelY = node.shape === 'diamond' ? center.y - 5 : node.y + 19;
    const summaryY = node.shape === 'diamond' ? center.y + 12 : node.y + 35;
    const stateY = node.shape === 'diamond' ? center.y + 28 : node.y + 50;
    const summary = mapTruncate(node.summary, node.shape === 'diamond' ? 22 : 30);
    const aria = node.label + ' — ' + node.summary + ' — idle';
    return '<g class="map-node" data-node="' + node.id + '" data-stage="' + esc(node.stage || '') +
      '" data-state="idle" tabindex="0" role="button" aria-label="' + esc(aria) + '">' +
      '<title>' + esc(node.label + ' — ' + node.summary) + '</title>' +
      shape +
      '<text class="map-node-label" x="' + textX + '" y="' + labelY + '" text-anchor="' + anchor + '">' +
      esc(node.label) + '</text>' +
      '<text class="map-node-summary" x="' + textX + '" y="' + summaryY + '" text-anchor="' + anchor + '">' +
      esc(summary) + '</text>' +
      '<text class="map-node-state" x="' + textX + '" y="' + stateY + '" text-anchor="' + anchor + '">idle</text>' +
      '</g>';
  }).join('');
  return '<svg id="map-svg" class="map" viewBox="0 0 1040 680" role="img" aria-labelledby="map-title">' +
    '<title id="map-title">Agent runtime map</title>' +
    '<defs><marker id="map-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">' +
    '<path d="M0 0 L10 5 L0 10 z" class="map-arrow-head"/></marker></defs>' +
    groups + edges + nodesHtml + '</svg>';
}

function mapTextList(data) {
  return data.map.nodes.map(function (node) {
    return '<li class="map-text-item" data-text-node="' + node.id + '" data-state="idle">' +
      '<span class="state-dot" data-state="idle" aria-hidden="true"></span>' +
      '<button type="button" class="linkish" onclick="mapNodeClick(\'' + node.id + '\')">' +
      esc(node.label) + '</button>' +
      '<span class="text-summary">' + esc(node.summary) + '</span>' +
      '<span class="text-state">idle</span></li>';
  }).join('');
}

function mapPlural(value, word) {
  const count = Number(value) || 0;
  return count + ' ' + word + (count === 1 ? '' : 's');
}

function mapRecent(data) {
  if (!data.turns.length) {
    return '<p class="empty">No turns recorded yet. Say something in the dock to start.</p>';
  }
  return data.turns.map(function (turn) {
    const cost = turn.usd == null ? 'cost not recorded' : mapMoney(turn.usd, turn.estimate);
    return '<button type="button" class="recent-row" onclick="mapOpenTurn(\'' + turn.turn_id + '\')">' +
      '<span class="recent-when">' + esc(stamp(turn.started_at)) + '</span>' +
      '<span class="recent-source">' + esc(turn.source || 'cli') + '</span>' +
      '<span class="recent-state" data-state="' + esc(turn.state) + '">' + esc(turn.state) + '</span>' +
      '<span class="recent-meta">' + mapPlural(turn.iterations, 'call') + ' · ' +
      mapPlural(turn.tool_calls, 'tool') + ' · ' + esc(cost) + '</span></button>';
  }).join('');
}

function overviewView(data) {
  const window = data.window || '7d';
  const buttons = ['today', '7d', 'all'].map(function (name) {
    return '<button type="button" class="window-btn' + (name === window ? ' active' : '') +
      '" data-map-window="' + name + '" onclick="mapSetWindow(\'' + name + '\')">' +
      (name === 'today' ? 'Today' : name === '7d' ? '7 days' : 'All') + '</button>';
  }).join('');
  return '<h1>Overview</h1>' +
    '<div class="map-toolbar"><div id="map-status" class="map-status" role="status" aria-live="polite">Agent idle</div>' +
    '<div class="map-windows">' + buttons + '</div></div>' +
    '<div id="live-indicator" class="live-indicator" hidden>' +
    '<span class="live-sticker">LIVE</span>' +
    '<button type="button" class="linkish" onclick="mapReturnToLive()">A new turn is running — return to the map</button></div>' +
    '<div class="map-wrap">' + mapSvg(data) + '</div>' +
    '<details class="map-text"><summary>Text view of the map</summary><ul class="map-text-list">' +
    mapTextList(data) + '</ul></details>' +
    '<section class="recent"><div class="section-head"><h2>Recent turns</h2>' +
    '<span class="meta">' + esc(window === 'today' ? 'today' : window === 'all' ? 'all recorded' : '7 days') +
    '</span></div><div class="recent-list">' + mapRecent(data) + '</div></section>' +
    '<aside id="turn-detail" class="turn-detail" hidden aria-labelledby="detail-title"></aside>';
}

function mapBind(data) {
  MAP_STATE.data = data;
  MAP_STATE.window = data.window || MAP_STATE.window;
  document.querySelectorAll('.map-node').forEach(function (el) {
    const id = el.getAttribute('data-node');
    el.addEventListener('click', function () { mapNodeClick(id); });
    el.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        mapNodeClick(id);
      }
    });
  });
}

function mapSetWindow(window) {
  MAP_STATE.window = window;
  if (typeof refreshMap === 'function') refreshMap(window);
}

function mapNodeClick(id) {
  const node = mapNodeById(id);
  if (!node) return;
  if (node.destination === 'chat') location.hash = '#chat';
  else if (node.destination === 'session') location.hash = '#chat';
  else if (node.destination === 'memory') location.hash = '#memory';
  else if (node.destination === 'observability') location.hash = '#observe';
  else if (node.destination === 'turn') mapOpenSelected();
}

function mapOpenSelected() {
  const selected = MAP_STATE.selected;
  const newest = MAP_STATE.data && MAP_STATE.data.turns && MAP_STATE.data.turns[0];
  const id = selected || (newest && newest.turn_id);
  if (!id) {
    mapStatus('No turn yet — send a message to start one.');
    return;
  }
  mapOpenTurn(id);
}

function mapOpenTurn(turnId) {
  MAP_STATE.selected = turnId;
  mapStatus('Loading turn…');
  const window = MAP_STATE.window || '7d';
  API.get('/api/turn?turn_id=' + encodeURIComponent(turnId) + '&window=' + encodeURIComponent(window))
    .then(function (payload) {
      if (payload.error) {
        mapDetailError(payload.error.message || 'no such turn');
        return;
      }
      MAP_STATE.detail = payload;
      renderTurnDetail(payload);
    })
    .catch(function () {
      mapDetailError('Could not load that turn.');
    });
}

function mapCloseDetail() {
  const panel = document.getElementById('turn-detail');
  if (panel) {
    panel.hidden = true;
    panel.innerHTML = '';
  }
  MAP_STATE.selected = null;
  mapHideLiveIndicator();
}

function mapShowLiveIndicator() {
  const panel = document.getElementById('turn-detail');
  const indicator = document.getElementById('live-indicator');
  if (panel && indicator && !panel.hidden) indicator.hidden = false;
}

function mapHideLiveIndicator() {
  const indicator = document.getElementById('live-indicator');
  if (indicator) indicator.hidden = true;
}

function mapReturnToLive() {
  mapHideLiveIndicator();
  mapCloseDetail();
  mapSetStatus('live', 'live');
}

function mapDetailError(message) {
  const panel = document.getElementById('turn-detail');
  if (!panel) return;
  panel.hidden = false;
  panel.innerHTML = '<div class="detail-head"><h2 id="detail-title">Turn detail</h2>' +
    '<button type="button" class="linkish" onclick="mapCloseDetail()">Close</button></div>' +
    '<p class="empty">' + esc(message) + '</p>';
  mapStatus('Turn detail unavailable.');
}

function mapStepStart(step, axisStart) {
  const end = Date.parse(step.ts);
  const duration = Number(step.duration_ms) || 0;
  if (!isFinite(end)) return axisStart;
  return duration > 0 ? end - duration : end;
}

function mapBar(step, axisStart, total) {
  const duration = Number(step.duration_ms) || 0;
  const start = mapStepStart(step, axisStart);
  const left = Math.max(0, Math.min(100, (start - axisStart) / total * 100));
  const width = duration > 0 ? Math.max(0.8, Math.min(100 - left, duration / total * 100)) : 0.8;
  return '<span class="tl-bar' + (duration > 0 ? '' : ' instant') + '" style="left:' +
    left.toFixed(2) + '%;width:' + width.toFixed(2) + '%"></span>';
}

function mapHotBadges(index, hotspots) {
  const badges = [];
  if (hotspots && hotspots.slowest === index) badges.push('<span class="hot">slowest</span>');
  if (hotspots && hotspots.most_usd === index) badges.push('<span class="hot">most $</span>');
  return badges.join(' ');
}

function mapStepMeta(step) {
  if (step.kind === 'gate') return esc(step.decision || '?') + ' — ' + esc(step.reason || '');
  if (step.kind === 'llm') {
    return 'iteration ' + esc(step.iteration) + ' · ' + esc(step.model || '') + ' · ' +
      esc(step.in) + ' in / ' + esc(step.out) + ' out · stop ' + esc(step.call || '?') + ' · ' +
      esc(step.duration_ms || 0) + ' ms · ' + mapMoney(step.usd, false);
  }
  if (step.kind === 'tool') {
    return esc(step.tool) + ' · ' + esc(step.duration_ms || 0) + ' ms · ' +
      (step.ok === false ? '<span class="bad">failed</span>' : 'ok');
  }
  if (step.kind === 'memory_write') return 'kept ' + esc(step.new_facts || 0) + ' fact(s)';
  if (step.kind === 'error') return esc(step.stage) + ' · ' + esc(step.error_kind) + ' — ' + esc(step.message);
  return esc(step.kind);
}

function mapStepDetail(step) {
  const lines = [];
  if (step.kind === 'llm') {
    lines.push('duration: ' + esc(step.duration_ms) + ' ms');
    lines.push('stop reason: ' + esc(step.call || '?'));
    lines.push('tokens: ' + esc(step.in) + ' in / ' + esc(step.out) + ' out');
    lines.push('cost: ' + mapMoney(step.usd, false));
  }
  if (step.kind === 'tool') {
    lines.push('duration: ' + esc(step.duration_ms) + ' ms');
    lines.push('args: ' + esc(step.args));
    lines.push('output: ' + esc(step.output));
  }
  if (step.kind === 'gate') {
    lines.push('decision: ' + esc(step.decision));
    lines.push('reason: ' + esc(step.reason));
    if (step.found != null) lines.push('found: ' + esc(step.found));
  }
  if (step.kind === 'error') {
    lines.push('stage: ' + esc(step.stage));
    lines.push('error: ' + esc(step.error_kind) + ' — ' + esc(step.message));
  }
  return '<details class="tl-step"><summary>recorded detail</summary><pre>' + lines.join('\n') + '</pre></details>';
}

function renderTurnDetail(payload) {
  const panel = document.getElementById('turn-detail');
  if (!panel) return;
  const turn = payload.turn;
  const steps = turn.steps || [];
  const hotspots = payload.hotspots || {};
  const start = Date.parse(turn.started_at);
  const lastStep = steps.map(function (step) { return Date.parse(step.ts); }).filter(isFinite).pop();
  const end = Date.parse(turn.ended_at) || lastStep || (isFinite(start) ? start + 1 : 1);
  const axisStart = isFinite(start) ? start : 0;
  const total = Math.max(1, end - axisStart);
  const rows = [];

  const gateIndex = steps.findIndex(function (step) { return step.kind === 'gate'; });
  if (gateIndex >= 0) {
    const step = steps[gateIndex];
    rows.push('<div class="tl-row" data-stage="gate"><div class="tl-label">gate ' +
      mapHotBadges(gateIndex, hotspots) + '</div><div class="tl-track">' + mapBar(step, axisStart, total) +
      '</div><div class="tl-meta">' + mapStepMeta(step) + '</div></div>' +
      '<div class="tl-detail">' + mapStepDetail(step) + '</div>');
  }

  let index = 0;
  let loopNumber = 1;
  while (index < steps.length) {
    const step = steps[index];
    if (step.kind !== 'llm') { index += 1; continue; }
    const llmIndex = index;
    const tools = [];
    let next = index + 1;
    while (next < steps.length && steps[next].kind === 'tool') {
      tools.push({ step: steps[next], index: next });
      next += 1;
    }
    const failed = tools.some(function (tool) { return tool.step.ok === false; });
    const toolRows = tools.map(function (tool) {
      return '<div class="tl-row child" data-stage="tool"><div class="tl-label">↳ ' +
        esc(tool.step.tool) + ' ' + mapHotBadges(tool.index, hotspots) + '</div>' +
        '<div class="tl-track">' + mapBar(tool.step, axisStart, total) + '</div>' +
        '<div class="tl-meta">' + mapStepMeta(tool.step) + '</div></div>' +
        '<div class="tl-detail">' + mapStepDetail(tool.step) + '</div>';
    }).join('');
    rows.push('<details class="tl-loop"' + (failed ? ' open' : '') + '>' +
      '<summary class="tl-row" data-stage="loop"><div class="tl-label"><span class="tl-caret">▸</span>' +
      'loop ' + loopNumber + ' ' + mapHotBadges(llmIndex, hotspots) +
      '</div><div class="tl-track">' +
      mapBar(step, axisStart, total) + '</div><div class="tl-meta">' + mapStepMeta(step) + '</div></summary>' +
      '<div class="tl-loop-body">' + mapStepDetail(step) + toolRows + '</div></details>');
    loopNumber += 1;
    index = next;
  }

  const replyTime = Date.parse(turn.ended_at) || end;
  const replyLeft = Math.max(0, Math.min(100, (replyTime - axisStart) / total * 100));
  rows.push('<div class="tl-row" data-stage="reply"><div class="tl-label">reply</div>' +
    '<div class="tl-track"><span class="tl-bar instant" style="left:' + replyLeft.toFixed(2) +
    '%;width:0.8%"></span></div><div class="tl-meta">' +
    (turn.state === 'failed' ? 'failed' : turn.state === 'unfinished' ? 'unfinished' : 'delivered') +
    '</div></div>');
  if (turn.reply) rows.push('<div class="reply detail-reply">' + esc(turn.reply) + '</div>');

  const memoryIndex = steps.findIndex(function (step) { return step.kind === 'memory_write'; });
  if (memoryIndex >= 0) {
    const step = steps[memoryIndex];
    rows.push('<div class="tl-row" data-stage="memory"><div class="tl-label">memory ' +
      mapHotBadges(memoryIndex, hotspots) + '</div><div class="tl-track">' +
      mapBar(step, axisStart, total) + '</div><div class="tl-meta">' + mapStepMeta(step) +
      '</div></div><div class="tl-detail">' + mapStepDetail(step) + '</div>');
  }

  const errorIndex = steps.findIndex(function (step) { return step.kind === 'error'; });
  if (errorIndex >= 0) {
    const step = steps[errorIndex];
    rows.push('<div class="tl-row bad-row" data-stage="error"><div class="tl-label">error ' +
      mapHotBadges(errorIndex, hotspots) + '</div><div class="tl-track">' +
      mapBar(step, axisStart, total) + '</div><div class="tl-meta">' + mapStepMeta(step) +
      '</div></div><div class="tl-detail">' + mapStepDetail(step) + '</div>');
  }

  const receipt = turn.receipt;
  if (receipt) {
    rows.push('<div class="tl-row" data-stage="receipt"><div class="tl-label">receipt</div>' +
      '<div class="tl-track"><span class="tl-bar instant" style="left:100%;width:0.8%"></span></div>' +
      '<div class="tl-meta">' + mapPlural(receipt.iterations, 'call') + ' · ' +
      mapPlural(receipt.tool_calls, 'tool') + ' · ' + esc(receipt.tokens_in) + ' in / ' +
      esc(receipt.tokens_out) + ' out · ' + mapMoney(receipt.usd, receipt.estimate) +
      '</div></div>');
  }

  const rawLines = (payload.raw || []).map(function (event) { return JSON.stringify(event); }).join('\n');
  const slowest = hotspots.slowest == null ? 'no timed steps' : 'slowest: step ' + (hotspots.slowest + 1);
  const priciest = hotspots.most_usd == null ? 'no costed steps' : 'most $: step ' + (hotspots.most_usd + 1);
  panel.hidden = false;
  panel.innerHTML = '<div class="detail-head"><div><h2 id="detail-title">Turn ' +
    esc(turn.turn_id) + '</h2><div class="meta">' + esc(turn.started_at) + ' · ' +
    esc(turn.source || 'cli') + ' · <span data-state="' + esc(turn.state) + '">' + esc(turn.state) +
    '</span></div></div><button type="button" class="linkish" onclick="mapCloseDetail()">Close</button></div>' +
    '<div class="detail-summary">' + esc(payload.summary) + '</div>' +
    '<div class="detail-legend"><span>' + esc(slowest) + '</span><span>' + esc(priciest) + '</span>' +
    '<span>' + esc(payload.skipped_lines) + ' bad line(s) skipped</span></div>' +
    '<div class="tl-axis"><span>' + esc(stamp(turn.started_at)) + '</span><span>' +
    esc(turn.ended_at ? stamp(turn.ended_at) : 'unfinished') + '</span></div>' +
    '<div class="timeline">' + rows.join('') + '</div>' +
    '<details class="raw"><summary>Raw record (' + (payload.raw || []).length + ' lines)</summary>' +
    '<pre>' + esc(rawLines) + '</pre></details>';
  mapStatus('Turn ' + turn.state + ' · ' + (turn.source || 'cli'));
}
