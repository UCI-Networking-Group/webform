/* eslint-disable func-names */

import {
  StepSpec, ElementInformation, WebFormField, WebForm,
} from './types.js';

export function initFunction() {
  const calledSpecialAPIs: { [key: string]: boolean } = {};
  (window as any).calledSpecialAPIs = calledSpecialAPIs;

  // Geolocation
  const { watchPosition, getCurrentPosition } = window.navigator.geolocation;

  window.navigator.geolocation.watchPosition = function (...args) {
    calledSpecialAPIs['geolocation.watchPostion'] = true;
    return watchPosition.apply(this, args);
  };

  window.navigator.geolocation.getCurrentPosition = function (...args) {
    calledSpecialAPIs['geolocation.getCurrentPosition'] = true;
    return getCurrentPosition.apply(this, args);
  };

  // Motion sensors through window.addEventListener
  const { addEventListener } = window;

  window.addEventListener = function (...args: any[]) {
    const eventName = args[0];

    if (['devicemotion', 'deviceorientation', 'deviceorientationabsolute'].includes(eventName)) {
      calledSpecialAPIs[`eventListener:${eventName}`] = true;
    }

    return addEventListener.apply(this, args as any);
  };

  // Sensors
  if ('Sensor' in window) {
    const { start } = (window as any).Sensor.prototype;

    (window as any).Sensor.prototype.start = function (...args: any[]) {
      calledSpecialAPIs[`${this.constructor.name}.start`] = true;
      return start.apply(this, args);
    };
  }

  // Camera, microphone and screen capture
  const { getUserMedia, getDisplayMedia } = window.MediaDevices.prototype;

  window.MediaDevices.prototype.getUserMedia = function (...args) {
    if (args[0]?.audio) calledSpecialAPIs['MediaDevices.getUserMedia:audio'] = true;
    if (args[0]?.video) calledSpecialAPIs['MediaDevices.getUserMedia:video'] = true;
    return getUserMedia.apply(this, args);
  };

  window.MediaDevices.prototype.getDisplayMedia = function (...args) {
    if (args[0]?.audio) calledSpecialAPIs['MediaDevices.getDisplayMedia:audio'] = true;
    if (args[0]?.video) calledSpecialAPIs['MediaDevices.getDisplayMedia:video'] = true;
    return getDisplayMedia.apply(this, args);
  };
}

export async function getFormInformation(formElement: HTMLFormElement): Promise<WebForm> {
  async function getElementInformation(element: Element): Promise<ElementInformation> {
    return {
      outerHTML: element.outerHTML,
      tagName: element.tagName,
      attributes: [...element.attributes].reduce((o, a) => Object.assign(o, { [a.name]: a.value }), {}),
      text: element instanceof HTMLElement ? element.innerText.trim() : '',
      isVisible: await (window as any).isElementVisible(formElement),
    };
  }

  const formData = new FormData(formElement);
  const formInfo: WebForm = {
    defaultFormData: Object.fromEntries([...formData].map((o) => [o[0], o[1].toString()])),
    element: await getElementInformation(formElement),
    fields: [],
    buttons: [],
  };

  for (const childElement of formElement.elements) {
    // A button
    if (childElement instanceof HTMLButtonElement
        || (childElement instanceof HTMLInputElement && childElement.type === 'submit')
        || (childElement.role === 'button')) {
      formInfo.buttons.push(await getElementInformation(childElement));
      continue;
    }

    // A general form field
    const fieldInfo: WebFormField = {
      name: (childElement as HTMLInputElement).name || null,
      fieldElement: await getElementInformation(childElement),
    };

    formInfo.fields.push(fieldInfo);

    // Find the label associated with the input element
    if (childElement.id) {
      const e: HTMLElement | null = formElement.querySelector(`label[for="${childElement.id}"]`);
      if (e !== null) fieldInfo.labelElement = await getElementInformation(e);
    }

    // If no label, provide the previous (visible) element as a hint
    if (fieldInfo.labelElement === undefined) {
      for (let e: Element | null = childElement; e !== null;) {
        e = e?.previousElementSibling || e?.parentElement?.previousElementSibling || null;

        if (e instanceof HTMLElement && formElement.contains(e)
            && !Array.prototype.some.call(formElement.elements, (o) => e?.contains(o))
            && (window as any).isElementVisible) {
          fieldInfo.previousElement = await getElementInformation(e);
        }
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
        action: ['click', await (window as any).hashObjectSha256(origin)],
        origin,
      });
    }
  }

  return possibleSteps;
}
