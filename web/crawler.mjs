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

  return 'UNKNOWN';
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
  const labelElement = formLocator.locator(`label[for="${fieldId}"]`);

  if (placeholder) testStrings.push(placeholder);
  if (fieldName) testStrings.push(fieldName.replaceAll('_', ' '));

  if (await labelElement.count() > 0) {
    const labelText = await labelElement.textContent();
    testStrings.push(labelText);
  }

  console.log(testStrings);

  for (const s of testStrings) {
    if (s.search(/\be-?mail\b/gi) >= 0) {
      return 'EMAIL';
    } if (s.search(/\bpassword\b/gi) >= 0) {
      return 'PASSWORD';
    } if (s.search(/\b(first|last|full|real)\s*name\b/gi) >= 0) {
      return 'PERSON_NAME';
    } if (s.search(/\b(sex|gender)\b/gi) >= 0) {
      return 'GENDER';
    } if (s.search(/\bbirth\s*day\b/gi) >= 0) {
      return 'BIRTHDAY';
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

  if (text.search(/\b(sign|create|forgot|reset|register|new|log|setting)s?\b/gi) >= 0) {
    return 500;
  }

  return 1;
}

/**
 * Locate the element that match the given attributes
 *
 * @param {import('playwright').Page} page
 * @param {ElementAttributes} matchingAttributes
 * @returns {import('playwright').Locator}
 */
async function locateElement(page, matchingAttributes) {
  if (matchingAttributes.id !== '') {
    const locator = page.locator(`#${matchingAttributes.id}`);
    if ((await locator.count()) > 0) return locator.first();
  }

  for (const element of await page.locator(matchingAttributes.tagName).all()) {
    const attr = await getElementAttributes(element);
    if (matchingAttributes.textContent === attr.textContent) return element;
  }

  return null;
}

(async () => {
  // TODO:
  //   - click buttons / links to discover forms
  //   - detect popup dialogs
  //   - discover privacy policy links

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
      actions: [],
      url,
    });
  }

  // Initialize the browser
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Enable ad blocker to reduce noise
  PlaywrightBlocker.fromPrebuiltAdsAndTracking(fetch).then((blocker) => {
    blocker.enableBlockingInPage(page);
  });

  // Stealth plugin - not sure if it actually helps but why not
  chromium.use(StealthPlugin());

  // Main loop
  while (jobQueue.size > 0) {
    const job = jobQueue.pop();
    console.log('Current job: ', job);

    await page.goto(job.url, { waitUntil: 'networkidle' });
    let actionsFinished = true;

    for (const actionDesc of job.actions) {
      // Do the actions

      /** @type {string} */
      const action = actionDesc._;
      /** @type {ElementAttributes} */
      const attr = actionDesc.attributes;

      console.log('Action:', action);
      console.log('Element:', attr);

      const element = await locateElement(page, attr);

      if (element === null) {
        actionsFinished = false;
        break;
      }

      if (action === 'click') {
        await element.click();
      } else {
        throw new Error(`Unsupported action: ${action}`);
      }
    }

    if (!actionsFinished) {
      console.warn('Job failed due to unfinished actions.');
      continue;
    }

    console.log('Checking forms...');

    // Search the webpage for forms
    for (const form of await page.locator('form').all()) {
      await form.scrollIntoViewIfNeeded();

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
      await element.scrollIntoViewIfNeeded();

      const attributes = await getElementAttributes(element);
      const clickReward = estimateClickReward(attributes);

      if (clickReward > 0) {
        const newActions = job.actions.slice();

        newActions.push({
          _: 'click',
          attributes,
        });

        const newJobDesc = {
          priority: clickReward,
          ts: new Date().getTime(),
          actions: newActions,
          url: job.url,
        };

        jobQueue.push(newJobDesc);
      }
    }

    await page.waitForTimeout(2000); // For now, avoid running too fast
  }

  // Log file
  // root/<URL>/<step-hash>/html
  await browser.close();
})();
