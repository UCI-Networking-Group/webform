import {
  StepSpec, ElementInformation, WebFormField, WebForm,
} from './types.js';
import { hashObjectSha256 } from './utils.js';

export async function getFormInformation(formElement: HTMLFormElement): Promise<WebForm> {
  function fetchElementInformation(element: HTMLElement): ElementInformation {
    return {
      outerHTML: element.outerHTML,
      tagName: element.tagName,
      attributes: [...element.attributes].reduce((o, a) => Object.assign(o, { [a.name]: a.value }), {}),
      text: element.innerText.trim(),
    };
  }

  const formData = new FormData(formElement);
  const formInfo: WebForm = {
    defaultFormData: {},
    element: fetchElementInformation(formElement),
    fields: [],
  };

  for (const [key, defaultValue] of formData.entries()) {
    formInfo.defaultFormData[key] = defaultValue.toString();
    const allNodes = formElement.querySelectorAll(`[name="${key}"]`);

    for (const fieldElement of allNodes) {
      const fieldInfo: WebFormField = {
        name: key,
        fieldElement: fetchElementInformation(fieldElement as HTMLElement),
        labelElement: null,
      };
      formInfo.fields.push(fieldInfo);

      // Find the label associated with the input element
      if (fieldElement.id.match(/^[-A-Za-z0-9_]+$/) !== null) {
        const e: HTMLElement | null = formElement.querySelector(`label[for="${fieldElement.id}"]`);
        if (e !== null) fieldInfo.labelElement = fetchElementInformation(e);
      }
    }
  }

  return formInfo;
}

export function markInterestingElements(markAttr: string) {
  for (const element of document.body.querySelectorAll('*')) {
    if (['link', 'button', 'form'].includes(element.role || '')
        || ['A', 'BUTTON', 'FORM'].includes(element.tagName)) {
      element.setAttribute(markAttr, '');
    }
  }
}

export async function findNextSteps(markAttr: string): Promise<StepSpec[]> {
  // Ref: https://gist.github.com/iiLaurens/81b1b47f6259485c93ce6f0cdd17490a
  let clickableElements: Element[] = [];

  for (const element of document.body.querySelectorAll(`*:not([${markAttr}])`)) {
    // Skip disabled elements
    if (element.ariaDisabled === 'true') continue;
    // But do not skip hidden elements because we may still want to click on them

    if (!!(element as HTMLElement).onclick
        || ['link', 'button'].includes(element.role || '')
        || ['A', 'BUTTON'].includes(element.tagName)) {
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
