#!/usr/bin/env python3

import argparse
import json
import os
import tiktoken
from bs4 import BeautifulSoup

from openai import OpenAI

MAX_TOKENS = 4_096

PROMPT_TEMPLATE = '''
Analyze the provided HTML code of a web form, along with the URL and title of the web page to determine the type of the form based on its usage.

URL: {url}

Page Title: {title}

HTML Code of the Web Form:
```
{html_code}
```

Classify the form into one of the following categories:
- Account Registration Form: Used for registering a persistent account to access services provided by the website. May request various personal details depending on the services offered.
- Account Login Form: For logging into an existing user account.
- Account Recovery Form: For recovering account information or resetting passwords.
- Event Registration Form: For signing up to attend events, often asking for contact details and maybe payment information.
- Booking or Reservation Form: For making appointments, reservations, or purchasing tickets, often asking for contact and payment information.
- Subscription Form: Enables users to subscribe to newsletters, mailing lists, or similar communications, typically requiring minimal contact details like email or phone number.
- Issue Reporting Form: For reporting incidents, issues, or complaints. May include fields for contact information.
- Feedback or Survey Form: Used for collecting user feedback, opinions, or for conducting market research.
- Contact Form: Used by visitors to send messages or inquiries to the website owner, usually requesting contact information and sometimes a message field.
- Application Form: For applying to jobs, school admissions, professional titles, etc., often requiring extensive personal and professional details.
- Payment Form: Used for online purchases or donations, typically asking for payment and contact details.
- Search Form: For searching or filtering website content, generally not involving personal information.
- Configuration Form: Used for changing settings on a website, such as cookie preferences, privacy settings, languages, etc.

If none of the above categories accurately describe the form, suggest a new category.

If insufficient information is available, classify it as "Unknown".

The response should be in JSON format with a single key "Classification".
'''.strip()


def cleanup_html(html_code, tokenizer, max_tokens=MAX_TOKENS):
    def remove_trivial_attributes(soup):
        for tag in soup.find_all():
            tag.attrs.pop('style', None)
            tag.attrs.pop('class', None)

    def remove_trivial_elements(soup):
        for tag in soup.select('script, meta, style, svg, img, iframe, media, br'):
            tag.extract()

    def remove_long_attributes(soup, max_attr_length=50):
        for tag in soup.find_all():
            for k in list(tag.attrs.keys()):
                if len(tag.attrs[k]) > max_attr_length:
                    tag.attrs.pop(k, None)

    def remove_empty_tags(soup):
        for tag in soup.find_all():
            if len(tag.get_text(strip=True)) == 0:
                tag.extract()

    def keep_minimal_attributes(soup):
        for tag in soup.find_all():
            for k in list(tag.attrs.keys()):
                if k not in {'id', 'name', 'type', 'value', 'for'}:
                    tag.attrs.pop(k, None)

    def cleanup_select_options(soup, n_options=5):
        for tag in soup.find_all('select'):
            options = tag.find_all('option')

            if len(options) > n_options:
                for o in options[n_options:]:
                    o.extract()

                options[n_options - 1].string = '...'

    soup = BeautifulSoup(html_code, 'html.parser')

    cleanup_functions = [
        remove_trivial_elements,
        remove_long_attributes,
        remove_empty_tags,
        remove_trivial_attributes,
        cleanup_select_options,
        keep_minimal_attributes,
    ]

    for func in cleanup_functions:
        cleaned_code = str(soup)
        n_tokens = len(tokenizer.encode(cleaned_code))

        if n_tokens <= max_tokens:
            break

        func(soup)

    cleaned_code = str(soup)
    return cleaned_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs='+', help="Input form.json paths")
    args = parser.parse_args()

    client = OpenAI()
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo-1106")

    for path in args.inputs:
        job_dir = os.path.dirname(path)
        form_json_fname = os.path.basename(path)
        result_path = os.path.join(job_dir, form_json_fname.replace('.json', '.label'))

        if os.path.exists(result_path):
            continue

        with open(path, encoding='utf-8') as fin:
            form_data = json.load(fin)

        with open(os.path.join(job_dir, "job.json"), encoding='utf-8') as fin:
            job_data = json.load(fin)

        page_title = job_data["pageTitle"].replace('\n', ' ')
        page_url = next(u for u in job_data["navigationHistory"] if u)
        html_code = cleanup_html(form_data["element"]['outerHTML'], tokenizer)

        prompt = PROMPT_TEMPLATE.format(html_code=html_code, url=page_url, title=page_title)

        token_length = len(tokenizer.encode(prompt))

        if token_length > MAX_TOKENS:
            classification = "TOO_LONG"
            print(f"Warning: prompt length {token_length} exceeds {MAX_TOKENS} tokens")
        else:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            response = json.loads(response.choices[0].message.content)

            if isinstance(response, dict) and len(response) == 1:
                classification = next(iter(response.values()))
            else:
                classification = "INVALID_RESPONSE"

        with open(result_path, "w", encoding='utf-8') as fout:
            print(classification, file=fout)

        print(path, repr(classification))


if __name__ == '__main__':
    main()