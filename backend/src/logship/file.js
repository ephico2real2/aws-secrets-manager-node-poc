// Append each (redacted) JSON log line to a file, for a log agent to ship
// (on EC2: the CloudWatch agent tails /var/log/secure-notes/app.jsonl).
// Like every sink, it gets exactly the line stdout gets, never a revealed one.
// Rotation: logrotate with copytruncate; the stream appends (O_APPEND).
import { createWriteStream } from 'node:fs';

export function createFileSink(path) {
  const stream = createWriteStream(path, { flags: 'a', mode: 0o640 });
  let errors = 0;
  stream.on('error', () => {
    errors++; // never log through the logger from here (it would loop)
  });
  return {
    write: (line) => stream.write(`${line}\n`),
    drain: () => new Promise((resolve) => (stream.writableNeedDrain ? stream.once('drain', resolve) : resolve())),
    stats: () => ({ path, errors }),
  };
}
