// byo dashboard — the live sequencer for the runtime map.
// Mechanism: poll /api/live, apply the cue list the server projects, diff by seq, hold a
// running/settle pair that lands within 150 ms just long enough to be seen, and jump to the
// true state when the display is more than a second behind. The server owns the mapping;
// this file only schedules and paints it.
// Rejected alternative: mapping events here on a fixed beat. That is what this replaces: the
// page invented a rhythm and lit a component after its step had already finished.
const MAP_LIVE_DWELL = 150;
const MAP_LIVE_LAG = 1000;
const MAP_LIVE_SETTLE = 1200;

const MapLive = {
  timer: null,
  settleTimer: null,
  fetching: false,
  turnId: null,
  applied: 0,
  generation: 0,
  liveAt: {},
  watching: false,
  pollMs: 1000,
  started: false,
  onVisibility: null,

  start() {
    this.stop();
    this.started = true;
    this.turnId = null;
    this.applied = 0;
    this.generation += 1;
    this.liveAt = {};
    this.watching = false;
    this.pollMs = 1000;
    mapResetNodes();
    mapSetStatus('Agent idle');
    mapNote('');
    this.onVisibility = function () {
      if (!document.hidden && MapLive.timer === null) MapLive.tick();
    };
    document.addEventListener('visibilitychange', this.onVisibility);
    this.tick();
  },

  stop() {
    this.started = false;
    if (this.timer) clearTimeout(this.timer);
    if (this.settleTimer) clearTimeout(this.settleTimer);
    this.timer = null;
    this.settleTimer = null;
    this.fetching = false;
    this.watching = false;
    this.liveAt = {};
    if (this.onVisibility) document.removeEventListener('visibilitychange', this.onVisibility);
    this.onVisibility = null;
    mapMarkStale(false);
  },

  tick() {
    this.timer = null;
    if (document.hidden || this.fetching || !document.getElementById('map-svg')) return;
    this.fetching = true;
    fetch('/api/live', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('live');
        return response.json();
      })
      .then(function (payload) {
        MapLive.receive(payload);
      })
      .catch(function () {
        mapMarkStale(true);
        mapNote('reconnecting', 'bad');
      })
      .finally(function () {
        MapLive.fetching = false;
        if (!document.hidden && document.getElementById('map-svg')) {
          const wait = MapLive.pollMs || 1000;
          MapLive.timer = setTimeout(function () { MapLive.tick(); }, wait);
        }
      });
  },

  receive(payload) {
    mapMarkStale(false);
    const turn = payload.turn;
    if (!turn) {
      this.turnId = null;
      this.watching = false;
      this.pollMs = payload.poll_ms || 1000;
      mapResetNodes();
      mapSetStatus('Agent idle');
      mapNote('');
      return;
    }
    this.pollMs = payload.poll_ms || 1000;
    if (this.turnId !== turn.turn_id) {
      this.turnId = turn.turn_id;
      this.applied = 0;
      this.generation += 1;
      this.liveAt = {};
      mapResetNodes();
      mapNote('');
      if (turn.state === 'running') {
        this.watching = true;
        this.applyHistory(payload.cues);
        mapNote('caught up');
      } else if (turn.state === 'interrupted') {
        this.watching = false;
        this.applyHistory(payload.cues);
      } else {
        this.watching = false;
        mapSetStatus('Agent idle');
      }
      this.applied = payload.seq;
      return;
    }
    this.applyCues(payload.cues);
    this.applied = payload.seq;
    if (turn.state !== 'running' && this.watching) {
      this.watching = false;
      this.settleLater();
    }
  },

  applyCues(cues) {
    const fresh = cues.filter(function (cue) { return cue.seq >= MapLive.applied; });
    if (!fresh.length) return;
    const oldest = Date.parse(fresh[0].at);
    if (isFinite(oldest) && Date.now() - oldest > MAP_LIVE_LAG) {
      this.applyHistory(fresh);
      mapNote('caught up');
      return;
    }
    for (let index = 0; index < fresh.length; index += 1) this.applyCue(fresh[index], false);
  },

  applyHistory(cues) {
    if (!cues || !cues.length) return;
    for (let index = 0; index < cues.length; index += 1) this.applyCue(cues[index], true);
    for (let index = cues.length - 1; index >= 0; index -= 1) {
      if (cues[index].role === 'step') {
        mapSetStatus(cues[index].label);
        return;
      }
    }
  },

  applyCue(cue, instant) {
    const generation = this.generation;
    const states = cue.states || {};
    for (const id in states) {
      if (!Object.prototype.hasOwnProperty.call(states, id)) continue;
      const state = states[id];
      if (instant) {
        mapSetNodeState(id, state);
        continue;
      }
      if (state === 'live') {
        this.liveAt[id] = Date.now();
        mapSetNodeState(id, state);
        continue;
      }
      const since = Date.now() - (this.liveAt[id] || 0);
      delete this.liveAt[id];
      const wait = since < MAP_LIVE_DWELL ? MAP_LIVE_DWELL - since : 0;
      if (wait > 0) {
        setTimeout(function () {
          if (generation !== MapLive.generation) return;
          mapSetNodeState(id, state);
        }, wait);
      } else {
        mapSetNodeState(id, state);
      }
    }
    mapApplyCueEdges(cue.edges || []);
    if (cue.role === 'step' && !instant) mapSetStatus(cue.label);
  },

  settleLater() {
    if (this.settleTimer) clearTimeout(this.settleTimer);
    const generation = this.generation;
    this.settleTimer = setTimeout(function () {
      if (generation !== MapLive.generation) return;
      mapResetNodes();
      mapSetStatus('Agent idle');
      mapNote('');
    }, MAP_LIVE_SETTLE);
  }
};
