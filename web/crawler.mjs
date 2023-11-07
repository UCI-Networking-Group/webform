import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { PlaywrightBlocker } from '@cliqz/adblocker-playwright';
import process from 'node:process';
import mnemonist from 'mnemonist';

const { Heap } = mnemonist;

/**
 * Guess the type of a form
 *
 * @param {import('playwright').Locator} locator
 * @returns {Promise<string>}
 */
async function checkFormType(locator) {
  for (const elem of await locator.locator('[type=submit]').all()) {
    const textContent = await elem.textContent();

    if (textContent.search(/\bsign\s*up\b/gi)) {
      return 'SIGN_UP';
    } if (textContent.search(/\b(sign|log)\s*in\b/gi)) {
      return 'LOGIN';
    }
  }

}

/**
 * Guess the type of a field in a form
 *
 * @param {import('playwright').Locator} formLocator
 * @param {import('playwright').Locator} fieldLocator
 * @returns {Promise<string>}
 */
async function checkFieldType(formLocator, fieldLocator) {
  // TODO:
  //   - more than one types ("Email or phone number")
  //   - check field label

  const testStrings = [];

  const placeholder = await fieldLocator.evaluate((node) => node.placeholder);
  const fieldId = await fieldLocator.evaluate((node) => node.id);
  const fieldName = await fieldLocator.evaluate((node) => node.name);
  const ariaLabel = await fieldLocator.evaluate((node) => node.getAttribute('aria-label'));
  const labelElement = formLocator.locator(`label[for="${fieldId}"]`);

  if (placeholder) testStrings.push(placeholder);
  if (fieldName) testStrings.push(fieldName.replaceAll('_', ' '));
  if (ariaLabel) testStrings.push(ariaLabel);

  if (await labelElement.count() > 0) {
    const labelText = await labelElement.textContent();
    testStrings.push(labelText);
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
 * @typedef {Object} ElementAttributes
 * @property {string} id
 * @property {string} tagName
 * @property {string} textContent
 * @property {number} width
 * @property {number} height
 */

/**
 * Get an element's attributes
 *
 * @param {import('playwright').Locator} locator
 * @returns {Promise<ElementAttributes>}
 */
async function getElementAttributes(locator) {
  const attributes = await locator.evaluate((node) => ({
    id: node.id,
    tagName: node.tagName,
    textContent: node.textContent,
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
 *
 * @param {ElementAttributes} attributes
 * @returns {number}
 */
function estimateClickReward(attributes) {
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
 *
 * @param {import('playwright').Page} page
 * @param {ElementAttributes} matchingAttributes
 * @returns {Promise<import('playwright').Locator|null>}
 */
async function locateElement(page, matchingAttributes) {
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
  constructor(message) {
    super(message);
    this.name = this.constructor.name;
  }
}

async function recoverPageState(page, url, steps) {
  const landingUrl = new URL(url);
  await page.goto(url, { waitUntil: 'networkidle' });

  const history = [url];
  const oldAttributeMark = "data-rr" + (new Date()).getTime();

  let hasNavigated = false;
  const navigationHandler = (data) => { hasNavigated = true; };
  page.on("domcontentloaded", navigationHandler)

  for (const stepInfo of steps) {
    hasNavigated = false;

    /** @type {ElementAttributes} */
    const attr = stepInfo.attributes;

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

      for (let i = 0; i < history.length; i++) {
        if (history[i] !== null) {
          const previousUrl = new URL(history[i]);

          if (currentUrl.pathname == previousUrl.pathname) {
            throw new PageStateError('Navigated to a previously visited URL');
          }
        }
      }
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

  const jobQueue = new Heap((job1, job2) => {
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
  while (jobQueue.size > 0 && jobCount < maxJobCount) {
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

    const job = jobQueue.pop();
    console.log('Current job: ', JSON.stringify(job, null, 2));

    let oldAttributeMark = null;

    try {
      oldAttributeMark = await recoverPageState(page, job.url, job.steps);
    } catch (e) {
      if (e.name === 'PageStateError' || e.name === 'TimeoutError') {
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

        newSteps.push({
          attributes,
          navigation: null,
        });

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
