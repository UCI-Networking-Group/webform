import * as tf from '@tensorflow/tfjs-node';
import * as use from '@tensorflow-models/universal-sentence-encoder';
import { StepSpec } from './types.js';

const SEED_PHRASES = `
12 months free
account profile
application form
apply
apply for an account
apply now
appointment
book a demo
business account
buy
buy now
chat with us
checkout
click to open account
client login
contact center
contact sales
contact us
continue
continue with email
continue your quote
create account
create free account
customer service
donate
download
download now
english
enroll
enroll in online Banking
feedback
forgot id
forgot password
free trial
get a demo
get started
get this deal
individual account
inquiry
join
log in
login
log on
logon
make an appointment
managing my account
my account
next step
new account
new customer
open an account
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
site map
sitemap
submit your application
subscribe
subscribe now
subscribe today
support center
take a product tour
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
