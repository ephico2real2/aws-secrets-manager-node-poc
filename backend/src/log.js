// Small structured JSON logger with mandatory redaction.
//
// Every record goes through the Redactor twice: once structurally (sensitive
// keys) and once on the final serialized line (registered secret values).
// The last-mile pass is what makes redaction hold even when a secret ends up
// somewhere unexpected, like an error message built by a library.

const LEVELS = { debug: 20, info: 30, warn: 40, error: 50 };

export function createLogger({ redactor, level = 'info', ringSize = 300, base = {}, out = process.stdout }) {
  const ring = [];
  const min = LEVELS[level] ?? LEVELS.info;

  function emit(levelName, bindings, args) {
    if (LEVELS[levelName] < min) return;
    let fields = {};
    let msg;
    if (typeof args[0] === 'string') {
      msg = args[0];
    } else if (args[0] instanceof Error) {
      fields = { err: args[0] };
      msg = args[1] ?? args[0].message;
    } else {
      fields = args[0] ?? {};
      msg = args[1];
    }
    const record = { time: new Date().toISOString(), level: levelName, ...bindings, ...fields, msg };
    const line = redactor.scrubString(JSON.stringify(redactor.scrub(record)));
    out.write(`${line}\n`);
    ring.push(line);
    if (ring.length > ringSize) ring.shift();
    return line;
  }

  function make(bindings) {
    return {
      debug: (...a) => emit('debug', bindings, a),
      info: (...a) => emit('info', bindings, a),
      warn: (...a) => emit('warn', bindings, a),
      error: (...a) => emit('error', bindings, a),
      child: (more) => make({ ...bindings, ...more }),
      /** Most recent (already redacted) log lines, newest last. */
      recent: (n = 100) => ring.slice(-n),
    };
  }

  return make(base);
}
