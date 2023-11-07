import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { PlaywrightBlocker } from '@cliqz/adblocker-playwright';
import process from 'node:process';
import mnemonist from 'mnemonist';
import { Locator, Page } from 'playwright';

const { Heap } = mnemonist;

/**
 * Guess the type of a form
 */
async function checkFormType(locator: Locator): Promise<string|null> {
  for (const elem of await locator.locator('[type=submit]').all()) {
    const textContent = await elem.textContent();

    if (textContent?.search(/\bsign\s*up\b/gi)) {
      return 'SIGN_UP';
    } if (textContent?.search(/\b(sign|log)\s*in\b/gi)) {
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
    } if (s.search(/\bzip\s*code\b/gi) >= 0) {
      return 'ZIP_CODE';
    } if (s.search(/\buser\s*(name|id)\b/gi) >= 0) {
      return 'USERNAME';
    }
  }

  return 'UNKNOWN';
}

/**
 * Attributes of an element (locator)
 */
interface ElementAttributes {
    id: string;
    tagName: string;
    textContent: string;
    width: number;
    height: number;
}

/**
 * Get an element's attributes
 */
async function getElementAttributes(locator: Locator): Promise<ElementAttributes> {
  const attributes: ElementAttributes = await locator.evaluate((node) => ({
    id: node.id,
    tagName: node.tagName,
    textContent: node.textContent || "",
    width: 0, height: 0,
  }));

  const boundingBox = await locator.boundingBox();

  if (boundingBox !== null) {
    attributes.width = boundingBox.width;
    attributes.height = boundingBox.height;
  } else {
    attributes.width = 0;
    attributes.height = 0;
  }

  return attributes;
}

/**
 * Estimate the reward of clicking an element
 */
function estimateClickReward(attributes: ElementAttributes): number {
  // Not likely clickable if too small
  if (attributes.width <= 16 || attributes.height <= 16) {
    return 0;
  }

  // TODO: In the future, a text classifier can be used.
  const text = attributes.textContent;

  if (text.search(/\b(sign|create|forgot|reset|register|new|log|setting|join|subscribe)s?\b/gi) >= 0) {
    return 500;
  }

  return 1;
}

/**
 * Locate the element that match the given attributes
 */
async function locateElement(page: Page, matchingAttributes: ElementAttributes): Promise<Locator|null>  {
  const id = matchingAttributes.id;

  if (id.match(/^[-A-Za-z0-9_]+$/) !== null) {
    const locator = page.locator(`#${id}`);
    if ((await locator.count()) > 0) return locator.first();
  }

  const text = matchingAttributes.textContent;

  if (text !== '') {
    for (const element of await page.locator(matchingAttributes.tagName).all()) {
      const attr = await getElementAttributes(element);
      if (text === attr.textContent) return element;
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

async function recoverPageState(page: Page, url: string, steps: ElementAttributes[]) {
  const landingUrl = new URL(url);
  await page.goto(url, { waitUntil: 'networkidle' });

  const history: (string|null)[] = [url];
  const oldAttributeMark = "data-rr" + (new Date()).getTime();

  let hasNavigated = false;
  const navigationHandler = (data: any) => { hasNavigated = true; };
  page.on("domcontentloaded", navigationHandler)

  for (const attr of steps) {
    hasNavigated = false;
    console.log('Element:', attr);

    const element = await locateElement(page, attr);

    if (element === null) {
      throw new PageStateError('Cannot find specified element');
    }

    page.getByRole('button').or(page.getByRole('link'))
      .evaluateAll((el, attrName) => el.forEach((e) => e.setAttribute(attrName, '')), oldAttributeMark);

    await element.click();

    // Wait for possible navigation
    await page.waitForTimeout(1000);
    await page.waitForLoadState('networkidle');

    // Check navigation loop
    if (hasNavigated) {
      const currentUrl = new URL(page.url());

      history.flatMap((s) => s ? [new URL(s)] : []).forEach((previousUrl) => {
        if (currentUrl.pathname == previousUrl.pathname) {
          throw new PageStateError('Navigated to a previously visited URL');
        }
      });
    }

    history.push(hasNavigated ? page.url() : null);
  }

  page.off("domcontentloaded", navigationHandler);

  console.log('Successfully recovered page state. URL:', page.url());

  return oldAttributeMark;
}

(async () => {
  const maxJobCount = 100;
  const landingURLs = process.argv.slice(2);

  interface JobSpec {
    priority: number,
    ts: number,
    url: string,
    steps: ElementAttributes[],
  }

  const jobQueue = new Heap<JobSpec>((job1, job2) => {
    let retVal = Math.sign(job2.priority - job1.priority);
    retVal = retVal === 0 ? Math.sign(job2.ts - job1.ts) : retVal;
    return retVal;
  });

  for (const url of landingURLs) {
    jobQueue.push({
      priority: 1000,
      ts: new Date().getTime(),
      steps: [],
      url,
    });
  }

  // Stealth plugin - not sure if it actually helps but why not
  chromium.use(StealthPlugin());

  // Initialize the browser
  const browser = await chromium.launch();
  let jobCount = 0;

  // Main loop
  while (jobCount < maxJobCount && jobQueue.size > 0) {
    const context = await browser.newContext({
      locale: "en-US",
      timezoneId: "America/Los_Angeles",
      serviceWorkers: "block",
    });
    context.setDefaultTimeout(10000);
    const page = await context.newPage();

    // Enable ad blocker to reduce noise
    await PlaywrightBlocker.fromPrebuiltAdsAndTracking(fetch).then((blocker) => {
      blocker.enableBlockingInPage(page);
    });

    jobCount++;

    const job = jobQueue.pop()!;
    console.log('Current job: ', JSON.stringify(job, null, 2));

    let oldAttributeMark = "";

    try {
      oldAttributeMark = await recoverPageState(page, job.url, job.steps);
    } catch (e) {
      if ((e instanceof Error) && (e.name === 'PageStateError' || e.name === 'TimeoutError')) {
        console.log('Failed to recover page state:', e.message);
        continue;
      } else {
        throw e;
      }
    }

    console.log('Checking forms...');

    // Search the webpage for forms
    for (const form of await page.locator('form').all()) {
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

    // Identify possible next steps
    const locator = page.getByRole('button').or(page.getByRole('link'));
    for (const element of await locator.all()) {
      try {
        await element.scrollIntoViewIfNeeded();
      } catch (e) {
        console.warn(e);
        continue;
      }

      const attributes = await getElementAttributes(element);
      const clickReward = estimateClickReward(attributes);

      if (await element.evaluate((e, attrName) => e.hasAttribute(attrName), oldAttributeMark)) {
        // Skip because the element has been tried
        continue;
      }

      if (clickReward > 0) {
        const newSteps = job.steps.slice();

        newSteps.push(attributes);

        const newJobDesc = {
          priority: clickReward,
          ts: new Date().getTime(),
          steps: newSteps,
          url: job.url,
        };

        // console.log('Enqueue new job:', JSON.stringify(newJobDesc, null, 2));

        jobQueue.push(newJobDesc);
      }
    }

    console.log('Job queue size:', jobQueue.size);

    await page.waitForTimeout(2000); // For now, avoid running too fast
    await page.close();
    await context.close();
  }

  await browser.close();
})();
