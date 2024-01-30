#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path

import tiktoken
from htmlutil import cleanup_html
from openai import BadRequestError, OpenAI

ID_NAMES = {
    'Address',
    'EmailAddress',
    'GovernmentId',
    'PaymentCardInfo',
    'PersonName',
    'PhoneNumber',
    'UsernameOrOtherId',
    'TaxId',
}

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
    parser.add_argument("labeled_jsonl_path", help="Path to labeled JSONL file")
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("output", help="Output path")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    args = parser.parse_args()

    root_dir = Path(args.root_dir)
    unique_forms = set()

    with open(args.labeled_jsonl_path, encoding='utf-8') as fin:
        for line in fin:
            row = json.loads(line)

            if not ID_NAMES.isdisjoint(row["label"]):
                unique_forms.add((row["domain"], row["job_hash"], row["filename"]))

    unique_form_html = set()
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo-1106")

    client = OpenAI() if not args.dry_run else None

    if os.path.exists(args.output):
        with open(args.output, "r", encoding='utf-8') as fin:
            for line in fin:
                row = json.loads(line)
                unique_forms.remove((row["domain"], row["job_hash"], row["filename"]))

    with open(args.output, "a", encoding='utf-8') as fout:
        for domain, job_hash, filename in sorted(unique_forms):
            form_json_path = root_dir / domain / job_hash / filename

            with form_json_path.open(encoding='utf-8') as fin:
                form_info = json.load(fin)

            try:
                form_method = form_info['element']['attributes'].get('method')
            except AttributeError:
                continue
            else:
                if form_method != 'POST':
                    continue

            form_html_raw = form_info['element']['outerHTML']
            form_html, n_tokens = cleanup_html(form_html_raw, tokenizer)

            if form_html not in unique_form_html:
                unique_form_html.add(form_html)
                print(domain, job_hash, filename, n_tokens)

                if not args.dry_run:
                    prompt = PROMPT_TEMPLATE % form_html

                    try:
                        response_obj = client.chat.completions.create(
                            model="gpt-3.5-turbo-1106",
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

                    if isinstance(response, str):
                        response = [response]

                    if not isinstance(response, list):
                        print("Invalid response:", response, file=sys.stderr)

                    jsonl_line = json.dumps({
                        "domain": domain,
                        "job_hash": job_hash,
                        "filename": filename,
                        "response": response,
                    })

                    print(jsonl_line, file=fout)
                    fout.flush()


if __name__ == '__main__':
    main()
