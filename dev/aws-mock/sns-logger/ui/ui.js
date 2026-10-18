// sns-logger screen. DOM APIs and textContent only: message text comes from
// publishers and is shown, never interpreted as markup.
const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') node.className = v;
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const time = (iso) => (iso ? new Date(iso).toLocaleTimeString() : '');
const short = (arn) => String(arn ?? '').split(':').pop();
const counts = { email: 0, sms: 0, chat: 0 };
let since = 0;

function meta(d, cls) {
  return el('div', { class: cls }, `MessageId ${d.messageId} · ${d.topicName ? `topic ${d.topicName}` : 'direct publish'} · published by ${short(d.publishedBy) || d.publishedBy}`);
}

function renderEmail(d) {
  return el(
    'article',
    { class: 'mail' },
    el('dl', { class: 'mail-head' },
      el('dt', {}, 'From'), el('dd', {}, d.from),
      el('dt', {}, 'To'), el('dd', {}, d.toMasked),
      el('dt', {}, 'Date'), el('dd', {}, new Date(d.timestamp).toUTCString()),
      el('dt', {}, 'Subject'), el('dd', { class: 'mail-subject' }, d.subject)),
    el('pre', { class: 'mail-body' }, d.body),
    meta(d, 'mail-meta'),
  );
}

function renderSms(d) {
  const s = d.sms ?? {};
  const parts = s.segments > 1 ? `${s.segments} parts` : '1 part';
  return el(
    'div',
    { class: 'sms' },
    el('span', { class: 'sms-from' }, `${s.senderId ? `From ${s.senderId}` : 'From a shared number (no sender ID in the US)'} · to ${d.toMasked} · ${time(d.timestamp)}`),
    el('div', { class: 'bubble' }, d.body),
    el('span', { class: 'sms-meta' }, `${s.encoding}, ${s.units} characters, ${parts} · ${s.type ?? 'Promotional'} · ${d.topicName ? `topic ${d.topicName}` : 'direct'}`),
  );
}

/** Amazon Q Developer custom notification inside an SNS envelope -> a card. */
function chatCard(envelope) {
  let msg;
  try {
    msg = JSON.parse(envelope.Message);
  } catch {
    return null;
  }
  if (msg?.source !== 'custom' || !msg.content) return null;
  const sev = msg.metadata?.additionalContext?.severity ?? 'info';
  return el(
    'div',
    { class: `chat-card sev-${sev}` },
    el('p', { class: 'chat-title' }, msg.content.title ?? ''),
    el('p', { class: 'chat-text' }, msg.content.description ?? ''),
    msg.content.nextSteps?.length ? el('ul', {}, msg.content.nextSteps.map((s) => el('li', {}, s))) : null,
  );
}

function renderChat(d) {
  let envelope = {};
  try {
    envelope = JSON.parse(d.body);
  } catch {
    /* shown raw below */
  }
  const card = chatCard(envelope) ?? el('div', { class: 'chat-card' }, el('p', { class: 'chat-title' }, envelope.Subject ?? '(no subject)'), el('p', { class: 'chat-text' }, envelope.Message ?? d.body));
  return el(
    'article',
    { class: 'chat' },
    card,
    el('details', {}, el('summary', {}, `POST ${d.toMasked} · ${d.protocol} · body`), el('pre', { class: 'chat-json' }, d.body)),
    meta(d, 'chat-meta'),
  );
}

function add(listId, node, kind) {
  const list = $(listId);
  list.querySelector('.empty')?.remove();
  list.prepend(node);
  counts[kind]++;
  $(`count-${kind}`).textContent = counts[kind];
}

async function poll() {
  try {
    const { deliveries } = await (await fetch(`/_sns/deliveries?since=${since}`)).json();
    for (const d of deliveries) {
      since = Math.max(since, d.seq);
      if (d.protocol === 'email') add('emails', renderEmail(d), 'email');
      else if (d.protocol === 'sms') add('sms', renderSms(d), 'sms');
      else add('chat', renderChat(d), 'chat');
    }
  } catch {
    /* try again next tick */
  }
}

async function topics() {
  const { topics: list } = await (await fetch('/_sns/topics')).json();
  $('badges').replaceChildren(el('span', { class: 'pill pill-info' }, `${list.length} topic${list.length === 1 ? '' : 's'}`), el('span', { class: 'pill' }, 'local only'));
  $('topics').replaceChildren(
    ...list.map((t) =>
      el('div', { class: 'topic' },
        el('strong', {}, t.name), t.displayName ? el('span', { class: 'muted small' }, ` · display name "${t.displayName}"`) : null,
        el('div', { class: 'topic-arn' }, t.arn),
        el('ul', {}, t.subscriptions.map((s) => el('li', {}, `${s.protocol}: ${s.endpoint}${s.filterPolicy ? ` · only when ${JSON.stringify(s.filterPolicy)}` : ''}`))))),
  );
}

async function pipeline() {
  const p = await (await fetch('/_sns/pipeline')).json();
  const state = $('pipeline-state');
  if (!p.deployed) {
    state.className = 'pill pill-skip';
    state.textContent = 'not deployed';
    $('rules').replaceChildren(el('li', {}, 'The log pipeline is not running. Start it with: docker compose -f docker-compose.yml -f docker-compose.observability.yml up'));
    $('pipeline-log').textContent = '';
    return;
  }
  state.className = p.errors?.length ? 'pill pill-warn' : 'pill pill-pass';
  state.textContent = p.errors?.length ? 'partly reachable' : 'receiving';
  $('rules').replaceChildren(
    ...(p.alerts?.length
      ? p.alerts.map((a) => el('li', {}, el('span', { class: `pill ${a.state === 'firing' ? 'pill-fail' : 'pill-warn'}` }, a.state), ` ${a.name} · since ${time(a.activeAt)}`))
      : [el('li', {}, 'No alert is pending or firing.')]),
    ...(p.errors ?? []).map((e) => el('li', { class: 'muted small' }, e)),
  );
  $('pipeline-log').textContent = (p.logs ?? [])
    .map((r) => `${time(r._time)}  ${(r['service.name'] ?? r._stream ?? '').toString().padEnd(12)} ${(r.severity ?? r.level ?? '').toString().padEnd(5)} ${r._msg ?? ''}${r.event_name || r.event ? `  [${r.event_name ?? r.event}]` : ''}`)
    .join('\n');
}

function show(tab) {
  document.querySelectorAll('.tab').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
  document.querySelectorAll('.panel').forEach((p) => (p.hidden = p.id !== `panel-${tab}`));
  if (tab === 'topics') void topics();
  if (tab === 'pipeline') void pipeline();
}

document.querySelectorAll('.tab').forEach((b) =>
  b.addEventListener('click', () => {
    history.replaceState(null, '', `#${b.dataset.tab}`);
    show(b.dataset.tab);
  }),
);

show((location.hash || '#email').slice(1));
window.addEventListener('hashchange', () => show((location.hash || '#email').slice(1)));
void topics();
void poll();
setInterval(poll, 2000);
setInterval(() => {
  if (!$('panel-pipeline').hidden) void pipeline();
}, 5000);
