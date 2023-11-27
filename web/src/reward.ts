import * as tf from '@tensorflow/tfjs-node';
import * as use from '@tensorflow-models/universal-sentence-encoder';
import { StepSpec } from './types.js';

const SEED_PHRASES = `
12 months free
account profile
apply
apply now
business account
buy
buy now
contact center
contact sales
contact us
continue with email
continue your quote
create account
create free account
customer service
download
download now
enroll
enroll in online Banking
feedback
forgot id
forgot password
free trail
get started
inquiry
join
log in
login
managing my account
my account
new account
new customer
opening my account
order now
register
register a credit card
register for an account
register here
register now
report fraud
request a demo
request form
reset password
schedule an appointment
see plans and pricing
settings
sign in
sign on
sign on to mobile banking
sign up
subscribe
subscribe now
subscribe today
support center
try for free
use phone or email
watch now
`.trim().split('\n');

/**
 * Estimate the reward of clicking an element
 */
// eslint-disable-next-line import/prefer-default-export
export const estimateReward = await (async () => {
  const model = await use.load();
  const seedEmbeddings = await model.embed(SEED_PHRASES);

  return async (step: StepSpec): Promise<number> => {
    const textContent = step?.origin?.textContent;
    const ariaLabel = step?.origin?.attributes['aria-label'];

    for (const text of [textContent, ariaLabel]) {
      if (text) {
        const embedding = await model.embed(text.trim().toLowerCase());
        const score = await tf.matMul(embedding, seedEmbeddings, false, true).max(1).array();
        return (score as number[])[0];
      }
    }

    return 0.0;
  };
})();
