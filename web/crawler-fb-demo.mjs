import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { PlaywrightBlocker } from '@cliqz/adblocker-playwright';

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

(async () => {
  // TODO:
  //   - click buttons / links to discover forms
  //   - detect popup dialogs
  //   - discover privacy policy links

  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Enable ad blocker to reduce noise
  PlaywrightBlocker.fromPrebuiltAdsAndTracking(fetch).then((blocker) => {
    blocker.enableBlockingInPage(page);
  });

  // Stealth plugin - not sure if it acutall helps but why not
  chromium.use(StealthPlugin());

  await page.goto('https://www.facebook.com/', { waitUntil: 'networkidle' });

  await page.getByText('Create new account').click();
  await page.waitForTimeout(2000);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot.png' });

  const formLocator = page.locator('form');

  for (const form of await formLocator.all()) {
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

  await browser.close();
})();
