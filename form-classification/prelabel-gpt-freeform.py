#!/usr/bin/env python3

import argparse
import json
import logging
import random
import sqlite3
from pathlib import Path

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

Please use a simple phrase to describe the usage of the form.

If insufficient information is available to determine the usage, output "unknown".

The response should be in JSON format with a single key "Classification".
'''.strip()

MAX_HTML_TOKENS = 4096
MAX_PROMPT_TOKENS = 8192


def main():
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("--target", type=int, default=2000,
                        help="How many forms to label")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    client = OpenAI()
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo-1106")
    root_dir = Path(args.root_dir)

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    cur = con.execute(r'''
        SELECT domain, job_hash, form_filename
        FROM field_classification
        WHERE json_array_length(field_list) > 0
    ''')

    all_forms = sorted(cur.fetchall())
    random.seed(args.seed)
    random.shuffle(all_forms)

    con.execute('''CREATE TABLE IF NOT EXISTS form_classification_gpt_freeform (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        form_filename TEXT NOT NULL,
        form_type TEXT,
        UNIQUE(job_hash, form_filename)
    ) STRICT''')
    cur.execute('SELECT domain, job_hash, form_filename FROM form_classification_gpt_freeform')
    done_forms = set(cur.fetchall())

    todo_forms = [i for i in all_forms[:args.target] if i not in done_forms]

    for domain, job_hash, form_filename in todo_forms:
        job_dir = root_dir / domain / job_hash

        with open(job_dir / form_filename, encoding='utf-8') as fin:
            form_data = json.load(fin)

        with open(job_dir / "job.json", encoding='utf-8') as fin:
            job_data = json.load(fin)

        logging.info('Processing %s/%s/%s', domain, job_hash, form_filename)

        page_title = job_data["pageTitle"].replace('\n', ' ')
        page_url = next(u for u in reversed(job_data["navigationHistory"]) if u)
        html_code, _ = cleanup_html(form_data["element"]['outerHTML'], tokenizer, target_length=MAX_HTML_TOKENS)
        logging.info('Page title: %r, URL: %s', page_title, page_url)

        prompt = PROMPT_TEMPLATE.format(html_code=html_code, url=page_url, title=page_title)
        token_length = len(tokenizer.encode(prompt))

        if token_length > MAX_PROMPT_TOKENS:
            logging.warning("Prompt length %d exceeds the limit", token_length)
            continue

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ]
        )

        response = json.loads(response.choices[0].message.content)

        if isinstance(response, dict) and 'Classification' in response:
            classification = str(response['Classification']).title()
        else:
            logging.warning("Invalid GPT response: %r", response)
            continue

        logging.info('New result: %s/%s/%s -> %s', domain, job_hash, form_filename, classification)
        con.execute('INSERT INTO form_classification_gpt_freeform VALUES (?, ?, ?, ?)',
                    (domain, job_hash, form_filename, classification))
        con.commit()


if __name__ == '__main__':
    main()
