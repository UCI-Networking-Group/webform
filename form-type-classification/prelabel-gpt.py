#!/usr/bin/env python3

import argparse
import hashlib
import html
import json
import logging
import re
import sqlite3
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import tiktoken
from htmlutil import cleanup_html
from openai import OpenAI

PROMPT_TEMPLATE = '''
Analyze the provided HTML code of a web form, along with the URL and title of the web page to determine the type of the form based on its usage.

URL: {url}

Page Title: {title}

HTML Code of the Web Form:
```
{html_code}
```

Classify the web form based on its intended usage.

Here are the possible categories for classification:
- "Account Registration Form": For creating new online user accounts.
- "Account Login Form": For users to log into existing accounts using their credentials.
- "Account Recovery Form": For retrieving or resetting forgotten account credentials.
- "Payment Form": For financial transactions, such as bill payments, online purchases or donations.
- "Financial Application Form": For applying to financial services like credit cards, loans, financial aid, insurance, investment accounts.
- "Role Application Form": For applying to positions such as employment, school admissions, or volunteer opportunities.
- "Subscription Form": For users to sign up for newsletters, mailing lists, or similar channels of periodic updates.
- "Reservation Form": For users to book services, schedule appointments, register for events, or similar.
- "Contact Form": For users to send private messages, inquiries, or feedback to the website owner.
- "Content Submission Form": For submitting user-generated content like comments, reviews, or ratings, intended to be published on the website.
- "Search Form": Used to search or filter website content, typically featuring a search query field and/or filter options.
- "Configuration Form": For customizing the user experience on the website, like setting preferences for cookies, language, or display settings.

Please choose the category that best describes the form.
If none of the above categories accurately describe the form, suggest a new category.
If the information is insufficient to make a confident classification, label it as "Unknown".

Format the response in JSON with one key "Classification".
'''.strip()

MAX_HTML_TOKENS = 8000
MAX_PROMPT_TOKENS = 16000


def main():
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("--list", type=str, required=False, help="List of forms to label")
    parser.add_argument("--target", type=int, default=1000,
                        help="How many forms to label")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--n_tries", type=int, default=10, help="Number of GPT calls for each form")
    parser.add_argument("--per-domain-limit", type=int, default=10,
                        help="Maximum number of forms to label for each domain")
    args = parser.parse_args()

    client = OpenAI()
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo-0125")
    root_dir = Path(args.root_dir)

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    con.create_function("REGEXP", 2, lambda pattern, text: 1 if re.search(pattern, text) else 0)

    all_forms = []
    weights = []

    if args.list:
        df = pd.read_csv(args.list, usecols=['domain', 'job_hash', 'form_filename', 'weight'])
        cur = df.itertuples(index=False)
    else:
        cur = con.execute(r'''
            SELECT domain, job_hash, form_filename, weight
            FROM
                field_classification a
                LEFT JOIN (
                    SELECT 1.0 / count(*) weight, field_list
                    FROM field_classification GROUP BY field_list
                ) b
                ON a.field_list = b.field_list
            WHERE a.field_list REGEXP
                '"(Address|EmailAddress|GovernmentId|BankAccountNumber|PersonName|PhoneNumber|UsernameOrOtherId|TaxId)"'
        ''')

    for row in cur:
        *form_spec, weight = row
        all_forms.append(tuple(form_spec))
        weights.append(weight)

    np.random.seed(args.seed)
    weights = np.array(weights) / sum(weights)
    selected_idx = np.random.choice(len(all_forms), size=min(args.target, len(all_forms)), replace=False, p=weights)
    selected_forms = [all_forms[i] for i in selected_idx]

    con.execute('''CREATE TABLE IF NOT EXISTS form_classification_gpt (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        form_filename TEXT NOT NULL,
        annotations TEXT,
        form_html_hash TEXT UNIQUE NOT NULL
    ) STRICT''')

    cur = con.execute('''
        SELECT domain, job_hash, form_filename, form_html_hash FROM form_classification_gpt
    ''')

    domain_counter = Counter()
    done_forms = set()
    done_hashes = set()

    for domain, job_hash, form_filename, form_html_hash in cur:
        done_forms.add((domain, job_hash, form_filename))
        done_hashes.add(form_html_hash)
        domain_counter[domain] += 1

    for descriptor in selected_forms:
        if descriptor in done_forms:
            continue

        domain, job_hash, form_filename = descriptor
        job_dir = root_dir / domain / job_hash

        if domain_counter[domain] >= args.per_domain_limit:
            logging.info('Skip due to domain limit')
            continue

        with open(job_dir / form_filename, encoding='utf-8') as fin:
            form_data = json.load(fin)

        with open(job_dir / "job.json", encoding='utf-8') as fin:
            job_data = json.load(fin)

        logging.info('Processing %s/%s/%s', domain, job_hash, form_filename)

        page_title = job_data["pageTitle"].replace('\n', ' ')
        page_url = next(u for u in reversed(job_data["navigationHistory"]) if u)
        form_html = form_data["element"]['outerHTML']

        html_string = f'<title>{html.escape(page_title)}</title>{form_html}'
        checksum = hashlib.blake2s(html_string.encode()).hexdigest()

        if checksum in done_hashes:
            logging.info('Skip due to duplication')
            continue

        cleaned_html, _ = cleanup_html(form_html, tokenizer, target_length=MAX_HTML_TOKENS)
        logging.info('Page title: %r, URL: %s', page_title, page_url)

        prompt = PROMPT_TEMPLATE.format(html_code=cleaned_html, url=page_url, title=page_title)
        token_length = len(tokenizer.encode(prompt))

        if token_length > MAX_PROMPT_TOKENS:
            logging.warning("Prompt length %d exceeds the limit", token_length)
            continue

        full_response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            #model="gpt-4-0125-preview",
            response_format={"type": "json_object"},
            seed=args.seed,
            n=args.n_tries,
            temperature=0.8,
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ]
        )

        annotations = []

        for choice in full_response.choices:
            response = json.loads(choice.message.content)

            if isinstance(response, dict) and "Classification" in response:
                annotations.append(str(response['Classification']))
            else:
                logging.warning("Invalid GPT response: %r", response)
                continue

        logging.info('New result: %s/%s/%s -> %r', domain, job_hash, form_filename, annotations)
        con.execute('INSERT INTO form_classification_gpt VALUES (?, ?, ?, ?, ?)',
                    (domain, job_hash, form_filename, json.dumps(annotations, separators=(',', ':')), checksum))
        con.commit()

        domain_counter[domain] += 1
        done_hashes.add(checksum)


if __name__ == '__main__':
    main()
