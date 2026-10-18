// A small Amazon EventBridge event-pattern matcher: the subset this project's
// rules use, plus a few neighbours. An operator it doesn't know is an error,
// so a rule that uses one can't silently match nothing (or everything).
//
// Semantics follow the EventBridge docs:
//   - every key in the pattern must match; arrays list allowed values (OR)
//   - an event value that is an array matches if any element matches
//   - a missing field matches nothing except {"exists": false}
//   - "$or": [p1, p2, ...] at any level: the siblings AND at least one branch
//   - an array of objects is flattened: each key collects the values of every
//     element, so {"a":{"b":[1],"c":[2]}} matches {"a":[{"b":1},{"c":2}]}
// https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-pattern-operators.html

const OPERATORS = new Set(['prefix', 'suffix', 'anything-but', 'exists', 'equals-ignore-case', 'numeric', 'wildcard']);

function wildcardToRegExp(w) {
  return new RegExp(`^${w.split('*').map((s) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*')}$`);
}

const isScalar = (v) => typeof v === 'string' || typeof v === 'number';
const NUMERIC_OPS = new Set(['<', '<=', '=', '>', '>=']);

/** Throw on an operator argument this matcher would otherwise misread. */
function checkArg(op, arg, rule) {
  const bad = () => {
    throw new Error(`event pattern: unsupported ${op} argument ${JSON.stringify(rule)}`);
  };
  switch (op) {
    case 'prefix':
    case 'suffix':
    case 'wildcard':
    case 'equals-ignore-case':
      if (typeof arg !== 'string') bad(); // e.g. {"prefix":{"equals-ignore-case":...}} isn't implemented
      break;
    case 'exists':
      if (typeof arg !== 'boolean') bad();
      break;
    case 'numeric':
      if (!Array.isArray(arg) || !arg.length || arg.length % 2) bad();
      for (let i = 0; i < arg.length; i += 2) if (!NUMERIC_OPS.has(arg[i]) || typeof arg[i + 1] !== 'number') bad();
      break;
    case 'anything-but':
      if (Array.isArray(arg)) {
        if (!arg.every(isScalar)) bad();
      } else if (arg && typeof arg === 'object') {
        const keys = Object.keys(arg);
        if (keys.length !== 1 || !['prefix', 'suffix'].includes(keys[0]) || typeof arg[keys[0]] !== 'string') bad();
      } else if (!isScalar(arg)) bad();
      break;
    default:
      bad();
  }
}

/** Merge an array of objects into one object of arrays (EventBridge's flattening). */
function flatten(list) {
  const out = {};
  for (const el of list) {
    if (el === null || typeof el !== 'object' || Array.isArray(el)) continue;
    for (const [k, v] of Object.entries(el)) (out[k] ??= []).push(...(Array.isArray(v) ? v : [v]));
  }
  return out;
}

function matchesOne(rule, value) {
  if (rule === null || typeof rule !== 'object') return value === rule;
  const ops = Object.keys(rule);
  if (ops.length !== 1 || !OPERATORS.has(ops[0])) throw new Error(`event pattern: unsupported operator ${JSON.stringify(rule)}`);
  const [op] = ops;
  const arg = rule[op];
  checkArg(op, arg, rule);
  switch (op) {
    case 'prefix':
      return typeof value === 'string' && value.startsWith(arg);
    case 'suffix':
      return typeof value === 'string' && value.endsWith(arg);
    case 'equals-ignore-case':
      return typeof value === 'string' && value.toLowerCase() === String(arg).toLowerCase();
    case 'wildcard':
      return typeof value === 'string' && wildcardToRegExp(arg).test(value);
    case 'numeric': {
      if (typeof value !== 'number') return false;
      for (let i = 0; i < arg.length; i += 2) {
        const [cmp, n] = [arg[i], arg[i + 1]];
        const ok = { '<': value < n, '<=': value <= n, '=': value === n, '>': value > n, '>=': value >= n }[cmp];
        if (!ok) return false;
      }
      return true;
    }
    case 'anything-but': {
      if (arg && typeof arg === 'object' && !Array.isArray(arg)) {
        if ('prefix' in arg) return typeof value === 'string' && !value.startsWith(arg.prefix);
        if ('suffix' in arg) return typeof value === 'string' && !value.endsWith(arg.suffix);
        throw new Error(`event pattern: unsupported anything-but ${JSON.stringify(arg)}`);
      }
      const list = Array.isArray(arg) ? arg : [arg];
      return !list.includes(value);
    }
    default:
      return false; // exists is handled by the caller
  }
}

function matchField(allowed, present, value) {
  if (!Array.isArray(allowed)) throw new Error(`event pattern: a leaf must be an array, got ${JSON.stringify(allowed)}`);
  for (const rule of allowed) {
    if (rule && typeof rule === 'object' && 'exists' in rule) {
      checkArg('exists', rule.exists, rule);
      if (rule.exists === present) return true;
      continue;
    }
    if (!present) continue;
    const values = Array.isArray(value) ? value : [value];
    if (values.some((v) => matchesOne(rule, v))) return true;
  }
  return false;
}

/** Does `event` match `pattern`? */
export function matches(pattern, event) {
  for (const [key, sub] of Object.entries(pattern)) {
    if (key === '$or') {
      if (!Array.isArray(sub) || !sub.length) throw new Error('event pattern: $or needs a non-empty array');
      if (!sub.some((branch) => matches(branch, event))) return false;
      continue;
    }
    const present = event !== null && typeof event === 'object' && Object.hasOwn(event, key) && event[key] !== undefined;
    let value = present ? event[key] : undefined;
    if (Array.isArray(value) && sub && typeof sub === 'object' && !Array.isArray(sub)) {
      value = flatten(value); // a nested pattern against an array of objects
    }
    if (Array.isArray(sub)) {
      if (!matchField(sub, present, value)) return false;
    } else if (sub && typeof sub === 'object') {
      if (!present || value === null || typeof value !== 'object') {
        // a nested pattern on a missing object matches only if every leaf allows absence
        if (!matches(sub, {})) return false;
        continue;
      }
      if (!matches(sub, value)) return false;
    } else {
      throw new Error(`event pattern: bad value for ${key}`);
    }
  }
  return true;
}

/**
 * Would EventBridge deliver this event to a rule in `state`? Read-only
 * CloudTrail management events (GetSecretValue, Describe*, List*) reach only
 * rules whose State is ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS.
 */
export function deliveredToRule(state, event) {
  if (state === 'DISABLED') return false;
  const ct = event?.detail;
  const readOnlyApiCall = event?.['detail-type'] === 'AWS API Call via CloudTrail' && ct?.readOnly === true && ct?.managementEvent !== false;
  if (readOnlyApiCall) return state === 'ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS';
  return true;
}

/** EventBridge InputTransformer: InputPathsMap ($.a.b) + InputTemplate with <name>. */
export function transformInput({ InputPathsMap = {}, InputTemplate = '' }, event) {
  const vars = {};
  for (const [name, path] of Object.entries(InputPathsMap)) {
    if (!/^\$(\.[A-Za-z0-9_-]+(\[\d+\])?)*$/.test(path)) throw new Error(`input transformer: unsupported path ${path}`);
    let v = event;
    for (const part of path.split('.').slice(1)) {
      const [, key, index] = /^([^[]+)(?:\[(\d+)\])?$/.exec(part);
      v = v == null ? undefined : v[key];
      if (index !== undefined) v = Array.isArray(v) ? v[Number(index)] : undefined;
    }
    vars[name] = v;
  }
  return InputTemplate.replace(/<([A-Za-z0-9_-]+)>/g, (whole, name) => {
    if (!(name in vars)) return whole;
    const v = vars[name];
    if (v === undefined || v === null) return '';
    return typeof v === 'string' ? v : JSON.stringify(v);
  });
}
