#!/usr/bin/env python3
'''Featurize form fields as strings for classification'''

import argparse
import io
import sqlite3
import json
from pathlib import Path

import lxml.html
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString


def filter_field(field_info):
    attributes = field_info["fieldElement"].get("attributes")

    if not isinstance(attributes, dict):
        return True

    for feature in attributes.get('id'), attributes.get('name'):
        if feature in [
            'q', 'vendor-search-handler', 'g-recaptcha-response', 'authenticity_token', 'form_build_id', '__VIEWSTATE',
            '__RequestVerificationToken', '__EVENTVALIDATION', 'csrfmiddlewaretoken', 'csrf_token', 'captcha_token',
            'captcha_sid', '_xfToken', '_csrf']:
            return False

    return True


def generate_field_description(field_info):
    def wrap_string(s):
        return LiteralScalarString(s.strip()) if '\n' in s else s

    field_element_info = field_info["fieldElement"]
    compact_field_info = {}

    tag_name = compact_field_info["tagName"] = field_element_info["tagName"]

    # Label or previous element
    if "labelElement" in field_info:
        compact_field_info["label"] = wrap_string(field_info["labelElement"]["text"].strip())
    elif "previousElement" in field_info:
        prev_elem = field_info['previousElement']

        if (prev_elem["tagName"] not in ["LABEL", "SCRIPT", "STYLE"]
            and (text := prev_elem["text"].strip())):
            compact_field_info["previousText"] = wrap_string(text)

    # For SELECT, get options. For INPUT and TEXTAREA, get text.
    if tag_name == "SELECT":
        compact_field_info["options"] = options = []
        outer_html = lxml.html.fromstring(field_element_info["outerHTML"])

        for child in outer_html.getchildren():
            if child.tag in ["option", "optgroup"] and child.text:
                options.append(wrap_string(child.text.strip()))
    elif tag_name in ["INPUT", "TEXTAREA"]:
        if "text" in field_info:
            compact_field_info["text"] = wrap_string(field_info["text"].strip())
    else:
        return None

    # Element attributes
    attrs_to_keep = [
        'placeholder','aria-placeholder', 'aria-description', 'aria-label', 'title', 'label', 'alt',
        'type', 'aria-valuemin', 'aria-valuemax', 'aria-valuenow', 'aria-valuetext',
        'id', 'autocomplete', 'inputmode', 'pattern', 'min', 'max', 'step', 'readonly',
        'value',
    ]

    attributes = {}

    for key in attrs_to_keep:
        if value := field_element_info["attributes"].get(key):
            attributes[key] = wrap_string(value.strip())

    if attributes:
        compact_field_info["attributes"] = attributes

    # Visibility as determined by Playwright
    compact_field_info["isVisible"] = field_element_info["isVisible"]

    return compact_field_info


def group_fields(form_info):
    '''Group fields by HTML name'''

    groups = {}
    no_name_fields = []

    for field in form_info["fields"]:
        if name := field["name"]:
            groups.setdefault(name, []).append(field)
        else:
            no_name_fields.append(field)

    yield from groups.items()
    yield from map(lambda x: (None, [x]), no_name_fields)


def process_form(form_info):
    yaml = YAML()
    yaml.width = 0x7FFFFFFF
    yaml.default_style = ""

    for name, group in group_fields(form_info):
        with io.StringIO() as buf:
            print(f"{name}", end="\n\n", file=buf)

            for field_info in group:
                if not filter_field(field_info):
                    continue

                try:
                    field_info = generate_field_description(field_info)
                except AttributeError:
                    continue

                if field_info:
                    yaml.dump(field_info, buf)
                    print(file=buf)

            yield buf.getvalue().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("output")
    args = parser.parse_args()

    rootdir = Path(args.rootdir)
    field_str_dedup = set()

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    with open(args.output, "w", encoding='utf-8') as fout:
        for domain, job_hash in con.execute('SELECT domain, job_hash FROM page_language WHERE lang_code = "en"'):
            jobdir = rootdir / domain / job_hash

            with open(jobdir / "job.json", encoding='utf-8') as fin:
                job_info = json.load(fin)
                url = next(u for u in reversed(job_info["navigationHistory"]) if u)

            for form_json_file in jobdir.glob("form-*.json"):
                with form_json_file.open(encoding='utf-8') as fin:
                    form_info = json.load(fin)

                for field_str in process_form(form_info):
                    if field_str and field_str not in field_str_dedup:
                        json_line = {
                            "text": field_str,
                            "domain": domain,
                            "job_hash": job_hash,
                            "filename": form_json_file.name,
                            "url": url,
                        }

                        field_str_dedup.add(field_str)

                        print(json.dumps(json_line), file=fout)


if __name__ == "__main__":
    main()
