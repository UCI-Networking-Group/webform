import { createHash } from 'node:crypto';
import { parseDomain, ParseResultType } from 'parse-domain';

/**
 * Hash an object using SHA256
 */
export async function hashObjectSha256(object: any): Promise<string> {
  return createHash('sha256').update(JSON.stringify(object)).digest('hex');
}

/**
 * Extend the URL class to returns the effective domain
 */
export class URLPlus extends URL {
  get effectiveDomain(): string {
    const parsed = parseDomain(this.hostname);

    if (parsed.type === ParseResultType.Listed) {
      return parsed.domain + '.' + parsed.topLevelDomains.join('.');
    }

    return this.hostname;
  }
}
