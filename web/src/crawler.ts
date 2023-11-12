import process from 'node:process';
import assert from 'node:assert/strict';
import * as fsPromises from 'node:fs/promises';
import path from 'node:path';

import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { PlaywrightBlocker } from '@cliqz/adblocker-playwright';
import mnemonist from 'mnemonist';
import { Locator, Page, errors as PlaywrightErrors } from 'playwright';

import { StepSpec, JobSpec } from './types.js';
import { URLPlus, hashObjectSha256, isElementVisible } from './utils.js';
import { findNextSteps, markInterestingElements, getFormInformation, initFunction } from './page-functions.js';

/**
 * TODO List:
 *  - Integrate an auto cookie consent extension, like Consent-O-Matic or I-Still-Dont-Care-About-Cookies
 *  - Go deeper into multi-step forms
 *  - Store the results on disk
 */

const DOM_VISITED_ATTR = 'data-dom-visited' + (Math.random() + 1).toString(36).substring(2);

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

async function doSteps(page: Page, steps: StepSpec[]): Promise<(string | null)[]> {
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
      await page.evaluate(markInterestingElements, DOM_VISITED_ATTR);
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

  return history;
}

async function checkForms(page: Page, outDir: string) {
  let formIndex = 0;

  for (const form of await page.locator(`form:not([${DOM_VISITED_ATTR}])`).all()) {
    formIndex += 1;

    try {
      // await form.scrollIntoViewIfNeeded();
      await form.screenshot({ path: path.join(outDir, `form-${formIndex}.png`) });
    } catch (e) {
      console.warn('Cannot scroll the form into view and take screenshot');
    }

    const formInfo = await form.evaluate(getFormInformation);
    await fsPromises.writeFile(
      path.join(outDir, `form-${formIndex}.json`),
      JSON.stringify(formInfo, null, 2),
    );
    console.log(`Web form #${formIndex} saved`);
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
  const [outDir, ...landingURLs] = process.argv.slice(2);

  const jobQueue = new mnemonist.Heap<JobSpec>((job1, job2) => {
    let retVal = Math.sign(job2.priority - job1.priority);
    retVal = retVal === 0 ? Math.sign(job1.parents.length - job2.parents.length) : retVal;
    return retVal;
  });

  landingURLs.forEach((url) => jobQueue.push({
    priority: 1000,
    parents: [],
    steps: [{ action: ['goto', url] }],
  }));

  // Stealth plugin - not sure if it actually helps but why not
  chromium.use(StealthPlugin());

  // Initialize the browser
  const browser = await chromium.launch();
  const triedJobs = new Set<string>();
  let jobCount = 0;

  await fsPromises.mkdir(outDir);

  // Main loop
  while (jobCount < maxJobCount && jobQueue.size > 0) {
    const context = await browser.newContext({
      locale: 'en-US',
      timezoneId: 'America/Los_Angeles',
      serviceWorkers: 'block',
      geolocation: { latitude: 38.581667, longitude: -121.494444 },
      permissions: [
        'geolocation',
        'camera', 'microphone',
        'ambient-light-sensor', 'accelerometer', 'gyroscope', 'magnetometer',
      ],
    });
    context.setDefaultTimeout(10000);
    await context.grantPermissions(['geolocation']);
    await context.addInitScript(initFunction);
    await context.exposeFunction('hashObjectSha256', hashObjectSha256);
    await context.exposeBinding('isElementVisible', isElementVisible, { handle: true });

    const page = await context.newPage();

    // Enable ad blocker to reduce noise
    await PlaywrightBlocker.fromPrebuiltAdsAndTracking(fetch).then(async (blocker) => {
      await blocker.enableBlockingInPage(page);
    });

    const job = jobQueue.pop()!;
    console.log('Current job: ', job);

    const jobHash = hashObjectSha256(job.steps.map((s) => s.action));
    if (triedJobs.has(jobHash)) {
      console.log('Skipping job because it has been tried before');
      continue;
    }

    console.log(`Job ${jobHash} started`);
    triedJobs.add(jobHash);
    jobCount += 1;

    const jobOutDir = path.join(outDir, jobHash);
    await fsPromises.mkdir(jobOutDir);

    let navigationHistory: (string | null)[] = [];

    try {
      navigationHistory = await doSteps(page, job.steps);
    } catch (e) {
      if (e instanceof PageStateError
          || e instanceof PlaywrightErrors.TimeoutError
          || (e instanceof Error && e.message.startsWith('page.goto: net::ERR_ABORTED '))) {
        console.log('Failed to recover page state:', e.message);
        continue;
      } else {
        throw e;
      }
    }

    // Dump some information for later inspection
    const pageHTML = await page.content();
    await fsPromises.writeFile(path.join(jobOutDir, 'page.html'), pageHTML);

    await page.screenshot({
      path: path.join(jobOutDir, 'page.png'),
      fullPage: true,
    });

    const pageTitle = await page.title();
    const calledSpecialAPIs = await page.evaluate(() => (window as any).calledSpecialAPIs);

    await fsPromises.writeFile(
      path.join(jobOutDir, 'job.json'),
      JSON.stringify({ jobHash, pageTitle, ...job, navigationHistory, calledSpecialAPIs }, null, 2),
    );

    // Search the webpage for forms
    console.log('Checking forms...');
    await checkForms(page, jobOutDir);

    const possibleNextSteps = await page.evaluate(findNextSteps, DOM_VISITED_ATTR);
    let newJobCount = 0;

    for (const step of possibleNextSteps) {
      const reward = estimateReward(step);
      const newSteps = buildSteps(job.steps, step);

      if (reward > 0 && !!newSteps) {
        const newJobDesc = {
          priority: reward,
          parents: [...job.parents, jobHash],
          steps: newSteps,
        };

        newJobCount += 1;
        jobQueue.push(newJobDesc);
      }
    }

    console.log(`Job queue size: ${jobQueue.size} (${newJobCount} new)`);

    await page.waitForTimeout(2000); // For now, avoid running too fast
    await page.close();
    await context.close();
  }

  await browser.close();
})();
