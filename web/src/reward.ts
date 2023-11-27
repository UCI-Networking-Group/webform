import * as tf from '@tensorflow/tfjs-node';
import * as use from '@tensorflow-models/universal-sentence-encoder';
import { StepSpec } from './types.js';

const SEED_PHRASES = `
login
log in
sign up
sign on
sign in
use phone or email
join
enroll
enroll in online Banking
subscribe
subscribe now
register
register now
settings
free trail
contact us
contact sales
feedback
apply
apply now
create account
my account
watch now
buy
buy now
register for an account
register here
contact center
support center
order now
download
download now
customer service
register a credit card
12 months free
request a demo
get started
account profile
see plans and pricing
business account
create free account
managing my account
opening my account
new account
new customer
subscribe today
use phone or email
continue with email
continue your quote
sign on to mobile banking
reset password
inquiry
schedule an appointment
report fraud
forgot id
forgot password
request form
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
