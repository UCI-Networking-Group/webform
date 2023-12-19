import { pipeline, cos_sim } from '@xenova/transformers';
import { StepSpec } from './types.js';

const SEED_PHRASES = `
account profile
application form
apply
apply for an account
apply now
appointment
book a demo
business account
buy now
chat with us
check status of request
checkout
click to open account
click here to continue
client login
complaint form
contact center
contact sales
contact us
continue
continue with email
create account
create free account
customer service
data request form
donate
download
download now
english
enter the site
enquiry form
enroll
enroll in online banking
fee payment
feedback
forgot id
forgot password
free trial
get a quote
get started
get this deal
individual account
inquiry
join
log in
logon
managing my account
my account
next step
new account
new customer
open an account
opt-out here
order now
preferences
register
register a credit card
register for an account
register now
report fraud
request a demo
request records
reset password
retrieve a quote
schedule an appointment
see plans and pricing
settings
sign in
sign on
sign on to mobile banking
sign up
sitemap
submit your application
subscribe
subscribe now
subscribe today
support center
take a product tour
try for free
use phone or email
`.trim().split('\n');

/**
 * Estimate the reward of clicking an element
 */
// eslint-disable-next-line import/prefer-default-export
export const estimateReward = await (async () => {
  let pipe = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
  const seedEmbeddings = await pipe(SEED_PHRASES, { pooling: 'mean', normalize: true });

  return async (step: StepSpec, randomFactor=0.05): Promise<number> => {
    let text = step?.origin?.text;
    let maxSimilarity = -1.0;

    if (!!!text && step.action[0] == 'goto') {
      const parsedUrl = new URL(step.action[1]);
      text = parsedUrl.pathname + parsedUrl.search;
    }

    if (text) {
      const embedding = await pipe(text, { pooling: 'mean', normalize: true });

      for (let i = 0; i < SEED_PHRASES.length; i++) {
        const similarity = cos_sim(seedEmbeddings[i].data, embedding.data);

        if (similarity > maxSimilarity) maxSimilarity = similarity;
      }
    }

    return maxSimilarity + randomFactor * Math.random();
  };
})();
