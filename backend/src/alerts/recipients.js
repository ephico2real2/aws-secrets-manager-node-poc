// Mask alert recipients before they appear in a log line or on a screen.
// No dependencies: the aws-mock image (sns-logger) copies this file too.
//
//   maskEmail('oncall@example.com') -> 'on****@example.com'
//   maskPhone('+15555550100')       -> '+1******0100'

export function maskEmail(address) {
  const s = String(address ?? '');
  const at = s.lastIndexOf('@');
  if (at < 1) return '***';
  const local = s.slice(0, at);
  const keep = local.length <= 2 ? 1 : 2;
  return `${local.slice(0, keep)}${'*'.repeat(Math.max(local.length - keep, 1))}${s.slice(at)}`;
}

export function maskPhone(number) {
  const s = String(number ?? '').replace(/[^\d+]/g, '');
  const digits = s.replace(/\D/g, '');
  if (digits.length < 6) return '***';
  const plus = s.startsWith('+') ? '+' : '';
  const country = plus ? digits.slice(0, 1) : '';
  const tail = digits.slice(-4);
  return `${plus}${country}${'*'.repeat(digits.length - country.length - 4)}${tail}`;
}

/** Mask by SNS protocol: email/email-json -> email; sms -> phone; http(s) -> host only. */
export function maskEndpoint(protocol, endpoint) {
  if (protocol === 'email' || protocol === 'email-json') return maskEmail(endpoint);
  if (protocol === 'sms') return maskPhone(endpoint);
  if (protocol === 'http' || protocol === 'https') {
    try {
      const u = new URL(endpoint);
      return `${u.protocol}//${u.host}/…`;
    } catch {
      return '***';
    }
  }
  return '***';
}
