import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { PlaywrightBlocker } from '@cliqz/adblocker-playwright';
import process from 'node:process';
import assert from 'node:assert/strict';
import mnemonist from 'mnemonist';
import { Locator, Page, errors as PlaywrightErrors } from 'playwright';
import { parseDomain, ParseResultType } from 'parse-domain';

/**
 * TODO List:
 *  - Integrate an auto cookie consent extension, like Consent-O-Matic or I-Still-Dont-Care-About-Cookies
 *  - Go deeper into multi-step forms
 *  - Store the results on disk
 */

const DOM_VISITED_ATTR = 'data-dom-visited' + (Math.random() + 1).toString(36).substring(2);

class URLPlus extends URL {
  get effectiveDomain(): string {
    const parsed = parseDomain(this.hostname);

    if (parsed.type === ParseResultType.Listed) {
      return parsed.domain + '.' + parsed.topLevelDomains.join('.');
    }

    return this.hostname;
  }
}

/**
 * Guess the type of a form
 */
async function checkFormType(locator: Locator): Promise<string | null> {
  for (const elem of await locator.locator('[type=submit]').all()) {
    const textContent = await elem.textContent() || '';

    if (textContent.search(/\bsign\s*up\b/gi) >= 0) {
      return 'SIGN_UP';
    } if (textContent.search(/\b(sign|log)\s*(in|on)\b/gi) >= 0) {
      return 'LOGIN';
    }
  }

  return null;
}

/**
 * Guess the type of a field in a form
 */
async function checkFieldType(formLocator: Locator, fieldLocator: Locator): Promise<string> {
  // TODO:
  //   - more than one types ("Email or phone number")
  //   - check field label

  const testStrings: string[] = [];

  const placeholder = await fieldLocator.evaluate((node) => (node as HTMLInputElement).placeholder);
  const fieldName = await fieldLocator.evaluate((node) => (node as HTMLInputElement).name);
  const ariaLabel = await fieldLocator.evaluate((node) => node.getAttribute('aria-label'));
  const fieldId = await fieldLocator.evaluate((node) => node.id);
  const labelElement = formLocator.locator(`label[for="${fieldId}"]`);

  if (placeholder) testStrings.push(placeholder);
  if (fieldName) testStrings.push(fieldName.replaceAll('_', ' '));
  if (ariaLabel) testStrings.push(ariaLabel);

  if (await labelElement.count() > 0) {
    const labelText = await labelElement.textContent();
    if (labelText) testStrings.push(labelText);
  }

  console.log(testStrings);

  for (const s of testStrings) {
    if (s.search(/\be-?mail\b/gi) >= 0) {
      return 'EMAIL';
    } if (s.search(/\b(mobile|(tele)?phone)\s*number\b/gi) >= 0) {
      return 'PHONE_NUMBER';
    } if (s.search(/\bpassword\b/gi) >= 0) {
      return 'PASSWORD';
    } if (s.search(/\b(first|last|full|real)\s*name\b/gi) >= 0) {
      return 'PERSON_NAME';
    } if (s.search(/\b(sex|gender)\b/gi) >= 0) {
      return 'GENDER';
    } if (s.search(/\b(birth\s*day|date\s+of\s+birth)\b/gi) >= 0) {
      return 'BIRTHDAY';
    } if (s.search(/\baddress\s+line\b/gi) >= 0) {
      return 'PHYSICAL_ADDRESS';
    } if (s.search(/\b(zip|postal)\s*code\b/gi) >= 0) {
      return 'POSTAL_CODE';
    } if (s.search(/\buser\s*(name|id)\b/gi) >= 0) {
      return 'USERNAME';
    }
  }

  return 'UNKNOWN';
}

interface StepSpec {
  action: ['goto' | 'click', ...string[]],
  origin?: {
    location: string,
    tagName: string,
    textContent: string,
    attributes: { [key: string]: string },
  },
}

/**
 * Estimate the reward of clicking an element
 */
function estimateReward(step: StepSpec): number {
  // TODO: In the future, a text classifier can be used.
  const text = step?.origin?.textContent.trim() || '';

  if (text.search(/\b(sign\s*(up|in|on)|creates?|forgot|resets?|registers?|new|enrolls?|log\s*(in|on)|settings?|joins?|subscribes?|inquiry|contacts?)\b/gi) >= 0) {
    return 500;
  }

  return 1;
}

/**
 * Locate the element that match the given attributes
 */
async function locateOriginElement(page: Page, step: StepSpec): Promise<Locator | null> {
  const tagName = step.origin?.tagName || 'invalid';

  // Match by ID
  const id = step.origin?.attributes.id || '';

  if (id.match(/^[-A-Za-z0-9_]+$/) !== null) {
    const locator = page.locator(`${tagName}#${id}`);
    if ((await locator.count()) > 0) return locator.first();
  }

  // Match by text content
  const text = step.origin?.textContent.trim();

  if (text !== '') {
    for (const element of await page.locator(tagName).all()) {
      const elemText = (await element.textContent() || '').trim();
      if (text === elemText) return element;
    }
  }

  return null;
}

class PageStateError extends Error {
  constructor(message: string) {
    super(message);
    this.name = this.constructor.name;
  }
}

async function waitForLoading(page: Page, timeout: number = 30000) {
  const tstart = performance.now();

  // Wait for networkidle but still continue if timeout
  try {
    await page.waitForLoadState('networkidle', { timeout });
  } catch (e) {
    if (!(e instanceof PlaywrightErrors.TimeoutError)) throw e;
  }

  const nextTimeout = Math.max(timeout - (performance.now() - tstart), 1);
  // At minimum, wait for DOMContentLoaded event -- should return immediately if already there
  await page.waitForLoadState('domcontentloaded', { timeout: nextTimeout });
}

function findNextSteps(args: string[]): StepSpec[] {
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
    const origin = {
      location: window.location.href,
      tagName: element.tagName,
      attributes: [...element.attributes].reduce((o, a) => Object.assign(o, { [a.name]: a.value }), {}),
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
        action: ['click'],
        origin,
      });
    }
  }

  return possibleSteps;
}

async function doSteps(page: Page, steps: StepSpec[]) {
  const history: (string | null)[] = [];
  let hasNavigated = false;

  const navigationHandler = () => { hasNavigated = true; };
  page.on('domcontentloaded', navigationHandler);

  for (const [index, step] of steps.entries()) {
    hasNavigated = false;
    const [command, ...args] = step.action;
    let actionFunc = async () => {};

    switch (command) {
      case 'goto': {
        actionFunc = async () => {
          await page.goto(args[0], { referer: step.origin?.location, waitUntil: 'commit' });
        };
        break;
      }
      case 'click': {
        const element = await locateOriginElement(page, step);
        if (element === null) throw new PageStateError('Cannot find specified element');

        actionFunc = async () => {
          try {
            await element.click();
          } catch (e) {
            if (e instanceof PlaywrightErrors.TimeoutError) {
              await element.evaluate((elem) => (elem as HTMLElement).click());
            } else {
              throw e;
            }
          }
        };

        break;
      }
      default:
        assert.fail(`Invalid action ${command}`);
    }

    if (index + 1 === steps.length) {
      // Before the last step, mark elements generated in previous steps
      await page.evaluate(findNextSteps, [DOM_VISITED_ATTR, 'old']);
    }

    const beforeUrl = page.url();

    await actionFunc();

    // Wait for possible navigation
    await page.waitForTimeout(1000);
    await waitForLoading(page);

    const afterUrl = page.url();
    if (beforeUrl !== afterUrl) hasNavigated = true;

    if (hasNavigated) {
      console.log('Navigated to:', afterUrl);

      const beforeUrlParsed = new URLPlus(beforeUrl);
      const afterUrlParsed = new URLPlus(afterUrl);

      if (index > 0 && beforeUrlParsed.effectiveDomain !== afterUrlParsed.effectiveDomain) {
        throw new PageStateError('Navigated to a different domain');
      }

      // Check navigation loop
      history.flatMap((s) => (s ? [new URLPlus(s)] : [])).forEach((historyUrl) => {
        if (afterUrlParsed.pathname === historyUrl.pathname) {
          throw new PageStateError('Navigated to a previously visited URL');
        }
      });
    }

    history.push(hasNavigated ? afterUrl : null);
  }

  page.off('domcontentloaded', navigationHandler);

  console.log('Successfully recovered page state. URL:', page.url());
}

async function checkForms(page: Page) {
  for (const form of await page.locator('form').all()) {
    if (await form.evaluate((e, attrName) => e.hasAttribute(attrName), DOM_VISITED_ATTR)) {
      // Skip because the element has been tried
      continue;
    }

    try {
      await form.scrollIntoViewIfNeeded();
    } catch (e) {
      console.warn(e);
      continue;
    }
    const formType = await checkFormType(form);

    console.log(`FORM TYPE: ${formType}`);

    for (const inputField of await form.locator('input').all()) {
      if (await inputField.isVisible()) {
        const fieldType = await checkFieldType(form, inputField);
        console.log(`- FIELD TYPE: ${fieldType}`);
      }
    }
  }
}

/**
 * Build a new step by appending the given next step to the given steps, while rejecting invalid next step
 */
function buildSteps(steps: StepSpec[], nextStep: StepSpec): StepSpec[] | null {
  if (nextStep.action[0] === 'goto') {
    const originalUrl = new URLPlus(steps[0].action[1]);
    const newUrl = new URLPlus(nextStep.action[1]);

    // Do not allow cross-domain navigation
    if (originalUrl.effectiveDomain !== newUrl.effectiveDomain) return null;

    // Avoid navigating to the same page
    if (originalUrl.pathname === newUrl.pathname) return null;

    return [nextStep];
  }

  return [...steps, nextStep];
}

await (async () => {
  const maxJobCount = 100;
  const landingURLs = process.argv.slice(2);

  interface JobSpec {
    priority: number,
    depth: number,
    steps: StepSpec[],
  }

  const jobQueue = new mnemonist.Heap<JobSpec>((job1, job2) => {
    let retVal = Math.sign(job2.priority - job1.priority);
    retVal = retVal === 0 ? Math.sign(job1.depth - job2.depth) : retVal;
    return retVal;
  });

  landingURLs.map((url) => jobQueue.push({
    priority: 1000,
    depth: 0,
    steps: [{ action: ['goto', url] }],
  }));

  // Stealth plugin - not sure if it actually helps but why not
  chromium.use(StealthPlugin());

  // Initialize the browser
  const browser = await chromium.launch();
  let jobCount = 0;

  // Main loop
  while (jobCount < maxJobCount && jobQueue.size > 0) {
    const context = await browser.newContext({
      locale: 'en-US',
      timezoneId: 'America/Los_Angeles',
      serviceWorkers: 'block',
    });
    context.setDefaultTimeout(10000);
    const page = await context.newPage();

    // Enable ad blocker to reduce noise
    await PlaywrightBlocker.fromPrebuiltAdsAndTracking(fetch).then(async (blocker) => {
      await blocker.enableBlockingInPage(page);
    });

    jobCount += 1;

    const job = jobQueue.pop()!;
    console.log('Current job: ', JSON.stringify(job, null, 2));

    try {
      await doSteps(page, job.steps);
    } catch (e) {
      if (e instanceof PageStateError || e instanceof PlaywrightErrors.TimeoutError) {
        console.log('Failed to recover page state:', e.message);
        continue;
      } else {
        throw e;
      }
    }

    // Search the webpage for forms
    console.log('Checking forms...');
    await checkForms(page);

    const possibleNextSteps = await page.evaluate(findNextSteps, [DOM_VISITED_ATTR, 'next']);
    let newJobCount = 0;

    for (const step of possibleNextSteps) {
      const reward = estimateReward(step);
      const newSteps = buildSteps(job.steps, step);

      if (reward > 0 && !!newSteps) {
        const newJobDesc = {
          priority: reward,
          depth: job.depth + 1,
          steps: newSteps,
        };

        // console.log('Enqueue new job:', JSON.stringify(newJobDesc, null, 2));

        newJobCount += 1;
        jobQueue.push(newJobDesc);
      }
    }

    console.log('New jobs:', newJobCount);
    console.log('Job queue size:', jobQueue.size);

    await page.waitForTimeout(2000); // For now, avoid running too fast
    await page.close();
    await context.close();
  }

  await browser.close();
})();
