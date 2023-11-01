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

(async () => {
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
  const context = await browser.newContext({serviceWorkers: "block"});
  const page = await browser.newPage();

  page.on('domcontentloaded', (page) => {
    console.log("domcontentloaded:", page.url());
  });

  // Enable ad blocker to reduce noise
  await PlaywrightBlocker.fromPrebuiltAdsAndTracking(fetch).then((blocker) => {
    blocker.enableBlockingInPage(page);
  });

  const flagAttributeName = "data-rr" + (new Date()).getTime();

  // Main loop
  while (jobQueue.size > 0) {
    const job = jobQueue.pop();
    console.log('Current job: ', JSON.stringify(job, null, 2));

    await page.goto(job.url, { waitUntil: 'networkidle' });
    let finishedAllSteps = true;

    for (const stepInfo of job.steps) {
      // Do the steps

      /** @type {ElementAttributes} */
      const attr = stepInfo.attributes;

      console.log('Element:', attr);

      const element = await locateElement(page, attr);

      if (element === null) {
        finishedAllSteps = false;
        break;
      }

      page.getByRole('button').or(page.getByRole('link'))
        .evaluateAll((el, attrName) => el.forEach((e) => e.setAttribute(attrName, '')), flagAttributeName);

      await element.click();

      // Wait for possible navigation
      await page.waitForTimeout(1000);
      await page.waitForLoadState('networkidle');
    }

    if (!finishedAllSteps) {
      console.warn('Job failed due to unfinished steps.');
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

      if (await element.evaluate((e, attrName) => e.hasAttribute(attrName), flagAttributeName)) {
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

        console.log('Enqueue new job:', JSON.stringify(newJobDesc, null, 2));

        jobQueue.push(newJobDesc);
      }
    }

    console.log('Job queue size:', jobQueue.size);
    await page.waitForTimeout(2000); // For now, avoid running too fast
  }

  await browser.close();
})();
