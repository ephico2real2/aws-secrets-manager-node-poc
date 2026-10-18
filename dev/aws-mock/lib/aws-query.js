// AWS Query protocol helpers (form-encoded requests, XML responses), as used
// by SNS: the AWS SDK v3 and Alertmanager both send Action=Publish&... bodies.

export const xmlEscape = (s) =>
  String(s ?? '').replace(/[<>&'"]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;' })[c]);

/** Form body -> plain object of strings. */
export function parseForm(body) {
  return Object.fromEntries(new URLSearchParams(body));
}

/**
 * Collect Query "map" parameters, e.g.
 *   MessageAttributes.entry.1.Name=AWS.SNS.SMS.SenderID
 *   MessageAttributes.entry.1.Value.DataType=String
 *   MessageAttributes.entry.1.Value.StringValue=SECNOTES
 * -> { 'AWS.SNS.SMS.SenderID': { DataType: 'String', StringValue: 'SECNOTES' } }
 */
export function queryMap(params, prefix) {
  const entries = {};
  for (const [k, v] of Object.entries(params)) {
    const m = new RegExp(`^${prefix.replace(/\./g, '\\.')}\\.entry\\.(\\d+)\\.(.+)$`).exec(k);
    if (!m) continue;
    (entries[m[1]] ??= {})[m[2]] = v;
  }
  const out = {};
  for (const e of Object.values(entries)) {
    if (!e.Name) continue;
    out[e.Name] = { DataType: e['Value.DataType'] ?? 'String', StringValue: e['Value.StringValue'] ?? e['Value.BinaryValue'] };
  }
  return out;
}

/** "Attributes.entry.N.key/value" style maps (CreateTopic, Subscribe). */
export function queryKeyValues(params, prefix) {
  const entries = {};
  for (const [k, v] of Object.entries(params)) {
    const m = new RegExp(`^${prefix.replace(/\./g, '\\.')}\\.entry\\.(\\d+)\\.(key|value)$`).exec(k);
    if (m) (entries[m[1]] ??= {})[m[2]] = v;
  }
  return Object.fromEntries(Object.values(entries).filter((e) => e.key).map((e) => [e.key, e.value ?? '']));
}

export function xmlResponse(action, inner, requestId, ns = 'http://sns.amazonaws.com/doc/2010-03-31/') {
  return `<${action}Response xmlns="${ns}"><${action}Result>${inner}</${action}Result><ResponseMetadata><RequestId>${requestId}</RequestId></ResponseMetadata></${action}Response>`;
}

export function xmlError({ type = 'Sender', code, message, requestId, ns = 'http://sns.amazonaws.com/doc/2010-03-31/' }) {
  return `<ErrorResponse xmlns="${ns}"><Error><Type>${type}</Type><Code>${xmlEscape(code)}</Code><Message>${xmlEscape(message)}</Message></Error><RequestId>${requestId}</RequestId></ErrorResponse>`;
}
