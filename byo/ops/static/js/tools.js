// The Tools view — what the agent can call, and what its calls produced.
// Available is the live registry (the same list the model is offered); Results
// is the trajectory's tool events, newest first. Both come from /api/tools.

function toolsView(data) {
  const tools = (data && data.tools) || [];
  const results = (data && data.results) || [];
  const cards = tools.map(function (tool) {
    return '<div class="card"><div class="meta"><code>' + esc(tool.name) + '</code></div>' +
      '<div>' + esc(tool.description) + '</div>' +
      '<details><summary class="meta">input schema</summary>' +
      '<pre class="mono">' + esc(JSON.stringify(tool.input_schema, null, 2)) + '</pre></details></div>';
  }).join('');
  const rows = results.map(function (r) {
    return '<tr><td><code>' + esc(r.tool) + '</code></td>' +
      '<td>' + (r.ok ? 'ok' : 'error') + '</td>' +
      '<td>' + esc(String(r.duration_ms)) + ' ms</td>' +
      '<td>' + esc(r.output) + '</td>' +
      '<td class="meta">' + esc(stamp(r.at)) + '</td></tr>';
  }).join('');
  return (
    '<section class="card"><h1>Available</h1>' +
    '<p class="meta">The capabilities the model can call this turn — served from the live registry.</p>' +
    '<div class="grid">' + (cards || '<p class="empty">No tools registered.</p>') + '</div></section>' +
    '<section class="card"><h1>Results</h1>' +
    '<p class="meta">What recent tool calls produced, read from the recorded trajectory.</p>' +
    (rows
      ? '<table><tr><th>tool</th><th>outcome</th><th>took</th><th>result</th><th>when</th></tr>' + rows + '</table>'
      : '<p class="empty">No tool calls recorded yet — ask for something that needs one.</p>') +
    '</section>'
  );
}
