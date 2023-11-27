import process from 'node:process';
import assert from 'node:assert/strict';
import * as fsPromises from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';

import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import mnemonist from 'mnemonist';
import { Locator, Page, errors as PlaywrightErrors } from 'playwright';
import { xdgCache } from 'xdg-basedir';
import { rimraf } from 'rimraf';

import { StepSpec, JobSpec } from './types.js';
import { URLPlus, hashObjectSha256, isElementVisible } from './utils.js';
import { findNextSteps, markInterestingElements, getFormInformation, initFunction } from './page-functions.js';
import { estimateReward } from './reward.js';

const DOM_VISITED_ATTR = 'data-dom-visited' + (Math.random() + 1).toString(36).substring(2);

/**
 * Locate the element that match the given attributes
 */
async function locateOriginElement(page: Page, step: StepSpec): Promise<Locator | null> {
  const tagName = step.origin?.tagName || 'invalid';

  // Match by ID
  const id = step.origin?.attributes.id || '';

  if (id) {
    const locator = page.locator(`${tagName}[id="${id}"]`);
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
      console.warn('Cannot take screenshot for the form');
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

async function downloadExtensions(cacheDir: string) {
  const extensionUrls = [
    'https://github.com/OhMyGuus/I-Still-Dont-Care-About-Cookies/releases/download/v1.1.1/istilldontcareaboutcookies-1.1.1.crx',
    'https://www.eff.org/files/privacy_badger-chrome.crx',
  ];
  const returnPaths = [];

  for (const url of extensionUrls) {
    const extractPath = path.join(cacheDir, 'ext-' + btoa(url).replaceAll('/', '@'));
    returnPaths.push(extractPath);

    if (await fsPromises.stat(extractPath).then(() => false).catch(() => true)) {
      console.log('Downloading extension:', url);

      const resource = await fetch(url);
      const data = await resource.arrayBuffer();

      const downloadPath = path.join(cacheDir, 'ext.crx');
      await fsPromises.writeFile(downloadPath, Buffer.from(data));

      execFileSync('7za', ['x', '-y', downloadPath, '-o' + extractPath]);
    }
  }

  return returnPaths;
}

await (async () => {
  const programName = 'web-form-crawler';
  const maxJobCount = 100;
  const priorityDecayFactor = 0.95;
  const cacheDir = path.join(xdgCache || os.tmpdir(), programName);

  const [outDir, ...landingURLs] = process.argv.slice(2);

  const jobQueue = new mnemonist.Heap<JobSpec>((job1, job2) => {
    const priority1 = job1.priority * (priorityDecayFactor ** job1.parents.length);
    const priority2 = job2.priority * (priorityDecayFactor ** job2.parents.length);
    return Math.sign(priority2 - priority1);
  });

  landingURLs.forEach((url) => jobQueue.push({
    priority: 1000,
    parents: [],
    steps: [{ action: ['goto', url] }],
  }));

  // Stealth plugin - not sure if it actually helps but why not
  chromium.use(StealthPlugin());

  // Setup extensions
  await fsPromises.mkdir(cacheDir, { recursive: true });
  const extensionPaths = await downloadExtensions(cacheDir);

  // Initialize the browser
  const userDataDir = path.join(cacheDir, `user-data-${process.pid}`);
  await rimraf(userDataDir);
  const browserContext = await chromium.launchPersistentContext(userDataDir, {
    args: [
      '--disable-extensions-except=' + extensionPaths.join(','),
      '--load-extension=' + extensionPaths.join(','),
    ],
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
  browserContext.setDefaultTimeout(10000);
  await browserContext.addInitScript(initFunction);
  await browserContext.exposeFunction('hashObjectSha256', hashObjectSha256);
  await browserContext.exposeBinding('isElementVisible', isElementVisible, { handle: true });

  const triedJobs = new Set<string>();
  let jobCount = 0;

  await fsPromises.mkdir(outDir);

  // Main loop
  while (jobCount < maxJobCount && jobQueue.size > 0) {
    browserContext.pages().forEach((page) => page.close());
    const page = await browserContext.newPage();

    do {
      const job = jobQueue.pop()!;
      const jobHash = hashObjectSha256(job.steps.map((s) => s.action));

      if (triedJobs.has(jobHash)) {
        console.log('Skipping job because it has been tried before');
        break;
      }

      console.log('Current job:', job);
      console.log(`Job ${jobHash} started`);
      triedJobs.add(jobHash);
      jobCount += 1;

      // Do the steps
      let navigationHistory: (string | null)[] = [];

      try {
        console.log('Navigating...');
        navigationHistory = await doSteps(page, job.steps);
      } catch (e) {
        if (e instanceof Error) {
          console.log('Failed to recover page state:', e.message);
          break;
        }

        throw e;
      }

      // Dump job information for later inspection
      const jobOutDir = path.join(outDir, jobHash);

      try {
        console.log('Saving job information...');

        const pageHTML = await page.content();
        const pageTitle = await page.title();
        const calledSpecialAPIs = await page.evaluate(() => (window as any).calledSpecialAPIs);
        const screenshot = await page.screenshot({ fullPage: true });

        await fsPromises.mkdir(jobOutDir);
        await fsPromises.writeFile(path.join(jobOutDir, 'page.html'), pageHTML);
        await fsPromises.writeFile(path.join(jobOutDir, 'page.png'), screenshot);
        await fsPromises.writeFile(
          path.join(jobOutDir, 'job.json'),
          JSON.stringify({ jobHash, pageTitle, ...job, navigationHistory, calledSpecialAPIs }, null, 2),
        );
      } catch (e) {
        if (e instanceof Error) {
          console.log('Failed to save job information:', e.message);
          break;
        }

        throw e;
      }

      // Search the webpage for forms
      try {
        console.log('Checking forms...');
        await checkForms(page, jobOutDir);
      } catch (e) {
        if (e instanceof Error) {
          console.log('Failed to check forms:', e.message);
          break;
        }

        throw e;
      }

      // Find possible next steps
      const possibleNextSteps = await page.evaluate(findNextSteps, DOM_VISITED_ATTR);
      let newJobCount = 0;

      for (const step of possibleNextSteps) {
        const reward = await estimateReward(step);
        const newSteps = buildSteps(job.steps, step);

        if (reward > 0 && !!newSteps) {
          jobQueue.push({
            priority: reward,
            parents: [...job.parents, jobHash],
            steps: newSteps,
          });

          newJobCount += 1;
        }
      }

      console.log(`Job queue size: ${jobQueue.size} (${newJobCount} new)`);
    // eslint-disable-next-line no-constant-condition
    } while (false);

    await page.waitForTimeout(2000); // Avoid running too fast
    await page.close();
  }

  await browserContext.close();
})();
