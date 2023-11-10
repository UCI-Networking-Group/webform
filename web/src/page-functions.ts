import { StepSpec } from './types.js';
import { hashObjectSha256 } from './utils.js';

// eslint-disable-next-line import/prefer-default-export
export async function findNextSteps(args: string[]): Promise<StepSpec[]> {
  const [markAttr, markValue] = args as [string, string];

  // Ref: https://gist.github.com/iiLaurens/81b1b47f6259485c93ce6f0cdd17490a
  let clickableElements: Element[] = [];

  for (const element of document.body.querySelectorAll('*')) {
    // Skip already marked elements
    if (element.hasAttribute(markAttr)) continue;

    // Skip disabled elements
    if (element.ariaDisabled === 'true') continue;
    // But do not skip hidden elements because we may still want to click on them

    if (!!(element as HTMLElement).onclick
        || ['link', 'button'].includes(element.role || '')
        || ['A', 'BUTTON'].includes(element.tagName)) {
      element.setAttribute(markAttr, markValue);
      clickableElements.push(element);
    }
  }

  // Only keep inner clickable items
  clickableElements = clickableElements.filter((x) => !clickableElements.some((y) => x.contains(y) && x !== y));

  const possibleSteps: StepSpec[] = [];

  for (const element of clickableElements) {
    const attributes = [...element.attributes].reduce((o, a) => Object.assign(o, { [a.name]: a.value }), {});
    delete (attributes as any)[markAttr];

    const origin = {
      location: window.location.href,
      tagName: element.tagName,
      attributes,
      textContent: element.textContent || '',
    };

    if (element instanceof HTMLAnchorElement && element.onclick === null && !!element.href.match(/^https?:/)) {
      // A pure anchor element
      possibleSteps.push({
        action: ['goto', element.href],
        origin,
      });
    } else {
      // Something else that is clickable
      possibleSteps.push({
        action: ['click', await hashObjectSha256(origin)],
        origin,
      });
    }
  }

  return possibleSteps;
}
