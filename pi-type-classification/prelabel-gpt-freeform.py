#!/usr/bin/env python3

import argparse
import json
import os
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import tiktoken
from openai import BadRequestError, OpenAI

sys.path.insert(0, os.path.join(sys.path[0], '..', 'pylib'))
from htmlutil import cleanup_html  # pylint: disable=wrong-import-position

PROMPT_TEMPLATE = '''
I will provide the HTML code of a web form. Please analyze the form and identify the types of personal data that are being requested in the form fields.

"Personal data" (or "personal information") should be understood according to the following definitions in privacy laws:

1. **California Consumer Privacy Act (CCPA)**: "Personal information" means information that identifies, relates to, describes, is reasonably capable of being associated with, or could reasonably be linked, directly or indirectly, with a particular consumer or household. Personal information includes, but is not limited to, the following if it identifies, relates to, describes, is reasonably capable of being associated with, or could be reasonably linked, directly or indirectly, with a particular consumer or household:
   - (A) Identifiers such as a real name, alias, postal address, unique personal identifier, online identifier, Internet Protocol address, email address, account name, social security number, driver’s license number, passport number, or other similar identifiers.
   - (B) Any personal information described in subdivision (e) of Section 1798.80.
   - (C) Characteristics of protected classifications under California or federal law.
   - (D) Commercial information, including records of personal property, products or services purchased, obtained, or considered, or other purchasing or consuming histories or tendencies.
   - (E) Biometric information.
   - (F) Internet or other electronic network activity information, including, but not limited to, browsing history, search history, and information regarding a consumer’s interaction with an internet website application, or advertisement.
   - (G) Geolocation data.
   - (H) Audio, electronic, visual, thermal, olfactory, or similar information.
   - (I) Professional or employment-related information.
   - (J) Education information, defined as information that is not publicly available personally identifiable information as defined in the Family Educational Rights and Privacy Act (20 U.S.C. Sec. 1232g; 34 C.F.R. Part 99).
   - (K) Inferences drawn from any of the information identified in this subdivision to create a profile about a consumer reflecting the consumer’s preferences, characteristics, psychological trends, predispositions, behavior, attitudes, intelligence, abilities, and aptitudes.
   - (L) Sensitive personal information.
2. **General Data Protection Regulation (GDPR)**: "Personal data" means any information relating to an identified or identifiable natural person (‘data subject’); an identifiable natural person is one who can be identified, directly or indirectly, in particular by reference to an identifier such as a name, an identification number, location data, an online identifier or to one or more factors specific to the physical, physiological, genetic, mental, economic, cultural or social identity of that natural person;

Please analyze the given HTML code of a web form and identify fields that may collect personal data as per these definitions.

The output should be in JSON format and include concise and easily interpretable noun phrases that clearly indicate each type of personal data being requested, for example: `{ "personal_data_types": ["Name", "Email Address", "Phone Number"] }`

Remember, the focus is on identifying personal data that are being requested in the form. Exclude any data that does not fit abovementioned definitions. If no personal data is being collected, simply output an empty list: `{ "personal_data_types": [] }`

Here is the HTML code of the form:

```
%s
```
'''.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("output", help="Output path")
    parser.add_argument("--target", type=int, default=4000,
                        help="How many forms to label")
    parser.add_argument("--min_samples_per_category", type=int, default=40,
                        help="Minimum number of samples per category")
    parser.add_argument("--model", default="gpt-4-0125-preview",
                        help="OpenAI model name")
    args = parser.parse_args()

    root_dir = Path(args.root_dir)

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')

    cur = con.execute('SELECT domain, content_categories FROM domain_info')

    cat_domain_map = defaultdict(list)

    for domain, content_categories_json in cur:
        content_categories = json.loads(content_categories_json)

        for cat in content_categories:
            if "super_category_id" in cat:
                cat_domain_map[cat["name"]].append(domain)

    for cat in list(cat_domain_map.keys()):
        if len(cat_domain_map[cat]) <= args.min_samples_per_category:
            cat_domain_map['Other'].extend(cat_domain_map[cat])
            del cat_domain_map[cat]

    candidate_forms = {}
    tokenizer = tiktoken.encoding_for_model(args.model)
    client = OpenAI()

    while len(candidate_forms) < args.target:
        cat = random.choice(list(cat_domain_map.keys()))
        domain = random.choice(cat_domain_map[cat])

        job_dir = random.choice(list((root_dir / domain).iterdir()))

        try:
            form_file = random.choice(list(job_dir.glob("form-*.json")))
        except IndexError:
            continue

        form_info = json.loads(form_file.read_text())

        try:
            form_method = form_info['element']['attributes'].get('method')
            form_html_raw = form_info['element']['outerHTML']
        except AttributeError:
            continue

        # Some heuristics to increase the chance of discovering personal data

        # POST forms more likely to require personal data
        if form_method != 'POST':
            continue

        # Visible forms only
        if not form_info['element']['isVisible']:
            continue

        # With at least two fields
        if len(form_info['fields']) <= 1:
            continue

        form_html, _ = cleanup_html(form_html_raw, tokenizer)

        candidate_forms[form_html] = (domain, job_dir.name, form_file.name)
        print(domain, job_dir.name, form_file.name)

    # Append mode, so previous results are preserved
    with open(args.output, "a", encoding='utf-8') as fout:
        for form_html, (domain, job_hash, form_file) in candidate_forms.items():
            prompt = PROMPT_TEMPLATE % form_html

            try:
                response_obj = client.chat.completions.create(
                    model=args.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                        {"role": "user", "content": prompt}
                    ]
                )
            except BadRequestError:
                print("Bad request!", file=sys.stderr)
                continue

            response = json.loads(response_obj.choices[0].message.content)

            if isinstance(response, dict) and len(response) == 1:
                response = next(iter(response.values()))

            if not isinstance(response, list):
                print("Invalid response:", response, file=sys.stderr)

            jsonl_line = json.dumps({
                "domain": domain,
                "job_hash": job_hash,
                "filename": form_file,
                "response": response,
            })

            print(response)
            print(jsonl_line, file=fout)
            fout.flush()


if __name__ == '__main__':
    main()
