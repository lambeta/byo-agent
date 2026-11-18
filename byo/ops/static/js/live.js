// byo dashboard — the live player for the runtime map.
// Mechanism: poll the existing /api/events cursor, map each record through the server's
// EVENT_MAP, and play a short queue of node/edge highlights. The cursor is the only state;
// the player is read-only and never starts, stops or delays a turn.
// Rejected alternative: an in-process SSE broadcast. The terminal writes the trajectory from
// another process, so it would never reach this page.
const MapLive = {
  cursor: 0,
  timer: null,
  playTimer: null,
  resetTimer: null,
  queue: [],
  playing: false,
  fetching: false,
  generation: 0,
  touched: new Set(),
  failed: new Set(),
  stale: false,
  skipped: 0,
  onVisibility: null,

  start(data) {
    this.stop();
    this.cursor = data.cursor || 0;
    this.queue = [];
    this.playing = false;
    this.fetching = false;
    this.generation = 0;
    this.touched = new Set();
    this.failed = new Set();
    this.skipped = 0;
    this.stale = false;
    mapResetNodes();
    mapSetStatus('Agent idle');
    if (data.active && data.active.events && data.active.events.length) {
      this.generation += 1;
      this.queue = data.active.events.slice();
      mapSetStatus('message in · ' + mapSource(data.active.turn && data.active.turn.source));
      this.play();
    }
    this.onVisibility = function () {
      if (!document.hidden) MapLive.tick();
    };
    document.addEventListener('visibilitychange', this.onVisibility);
    this.timer = setInterval(function () { MapLive.tick(); }, 500);
  },

  stop() {
    if (this.timer) clearInterval(this.timer);
    if (this.playTimer) clearTimeout(this.playTimer);
    if (this.resetTimer) clearTimeout(this.resetTimer);
    this.timer = null;
    this.playTimer = null;
    this.resetTimer = null;
    this.queue = [];
    this.playing = false;
    this.fetching = false;
    if (this.onVisibility) document.removeEventListener('visibilitychange', this.onVisibility);
    this.onVisibility = null;
    mapMarkStale(false);
  },

  tick() {
    if (document.hidden || this.fetching || !MAP_STATE.data) return;
    this.fetching = true;
    fetch('/api/events?cursor=' + encodeURIComponent(this.cursor), { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('feed');
        return response.json();
      })
      .then(function (payload) {
        MapLive.cursor = typeof payload.cursor === 'number' ? payload.cursor : MapLive.cursor;
        if (payload.skipped > 0) {
          MapLive.skipped += payload.skipped;
          mapSetStatus('skipped ' + MapLive.skipped + ' bad line(s)');
        }
        if (payload.events && payload.events.length) {
          MapLive.queue.push.apply(MapLive.queue, payload.events);
          if (!MapLive.playing) MapLive.play();
        }
        if (MapLive.stale) {
          MapLive.stale = false;
          mapMarkStale(false);
          mapSetStatus('caught up');
        }
      })
      .catch(function () {
        MapLive.stale = true;
        mapMarkStale(true);
        mapSetStatus('reconnecting', 'bad');
      })
      .finally(function () {
        MapLive.fetching = false;
      });
  },

  play() {
    if (!this.queue.length) {
      this.playing = false;
      return;
    }
    const oldest = Date.parse(this.queue[0] && this.queue[0].ts);
    const tooOld = isFinite(oldest) && Date.now() - oldest > 2000;
    if (this.queue.length > 8 || tooOld) {
      const backlog = this.queue;
      this.queue = [];
      backlog.forEach(function (event) { MapLive.apply(event, true); });
      this.playing = false;
      mapSetStatus('caught up');
      return;
    }
    const event = this.queue.shift();
    this.apply(event, false);
    this.playing = true;
    this.playTimer = setTimeout(function () {
      MapLive.playing = false;
      MapLive.play();
    }, 550);
  },

  apply(event, instant) {
    const type = event && event.type;
    const eventMap = MAP_STATE.data && MAP_STATE.data.map && MAP_STATE.data.map.event_map;
    const entry = eventMap && eventMap[type];
    if (!entry) {
      mapSetStatus('unmapped step: ' + (type || 'unknown'));
      return;
    }
    if (type === 'turn_start') {
      mapResetNodes();
      this.touched = new Set();
      this.failed = new Set();
      this.generation += 1;
      mapShowLiveIndicator();
    }
    let nodes = entry.nodes.slice();
    let edges = entry.edges.slice();
    if (type === 'gate' && event.decision === 'retrieve' && entry.retrieve) {
      nodes = nodes.concat(entry.retrieve.nodes);
      edges = edges.concat(entry.retrieve.edges);
    }
    let stageNode = null;
    if (type === 'error') {
      stageNode = entry.stage_nodes && entry.stage_nodes[event.stage];
      if (stageNode) {
        nodes = [stageNode];
        edges = [];
      }
    }
    nodes.forEach(function (id) { MapLive.touched.add(id); });
    const gen = this.generation;
    nodes.forEach(function (id) {
      if (!mapNodeById(id)) return;
      let state = 'live';
      if (type === 'gate' && event.decision === 'skip' && id === 'gate') state = 'skipped';
      if (type === 'tool' && event.ok === false && id === 'tools') state = 'failed';
      if (type === 'tool' && MapLive.failed.has('tools')) state = 'failed';
      if (type === 'error') state = 'failed';
      if (state === 'failed') MapLive.failed.add(id);
      mapSetNodeState(id, state);
      if (instant) {
        if (state === 'live') mapSetNodeState(id, 'done');
        return;
      }
      if (state === 'live') {
        setTimeout(function () {
          if (gen !== MapLive.generation || MapLive.failed.has(id)) return;
          mapSetNodeState(id, 'done');
        }, 650);
      }
    });
    edges.forEach(function (id) {
      mapSetEdgeState(id, 'live');
      if (instant) {
        mapSetEdgeState(id, 'idle');
        return;
      }
      setTimeout(function () {
        if (gen !== MapLive.generation) return;
        mapSetEdgeState(id, 'idle');
      }, 650);
    });

    let label = entry.label;
    if (type === 'turn_start') label += ' · ' + mapSource(event.source);
    if (type === 'gate') label += ' · ' + (event.decision || '?');
    if (type === 'llm' && event.kind === 'final') label = entry.final_label || 'final answer';
    if (type === 'tool') label += ' · ' + (event.tool || '?');
    if (type === 'tool' && event.ok === false) label += ' · failed';
    if (type === 'error') label += ': ' + (event.stage || '?');
    if (type === 'turn_end') label = MapLive.failed.size ? 'reply · failed' : 'reply';
    mapSetStatus(label, type === 'error' ? 'bad' : '');

    if (type === 'turn_end') {
      mapMarkUnreached(this.touched);
      if (this.resetTimer) clearTimeout(this.resetTimer);
      this.resetTimer = setTimeout(function () {
        if (gen !== MapLive.generation) return;
        mapResetNodes();
        mapSetStatus('Agent idle');
      }, 1500);
    }
  }
};
