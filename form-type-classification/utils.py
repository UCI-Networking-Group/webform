import html
import json
import os
import sys
from collections import Counter
from pathlib import Path

import bs4
from bs4 import BeautifulSoup
from transformers import MarkupLMFeatureExtractor

sys.path.insert(0, os.path.join(sys.path[0], '..', 'pylib'))
# pylint: disable=wrong-import-position
from htmlutil import cleanup_list_options, remove_long_attributes, remove_trivial_elements


class MyMarkupLMFeatureExtractor(MarkupLMFeatureExtractor):
    def get_three_from_single(self, html_string):
        html_code = BeautifulSoup(html_string, "html.parser")

        remove_trivial_elements(html_code)
        remove_long_attributes(html_code)
        cleanup_list_options(html_code)

        all_doc_strings = []
        string2xtag_seq = []
        string2xsubs_seq = []

        # Main code
        for element in html_code.descendants:
            if isinstance(element, bs4.element.PreformattedString):
                # Skip comments and other special strings
                continue

            if type(element.parent) != bs4.element.Tag:
                continue

            if isinstance(element, bs4.element.NavigableString):
                text_in_this_tag = html.unescape(element).strip()
                if not text_in_this_tag:
                    continue

                all_doc_strings.append(text_in_this_tag)

                xpath_tags, xpath_subscripts = self.xpath_soup(element)
                string2xtag_seq.append(xpath_tags)
                string2xsubs_seq.append(xpath_subscripts)
            elif isinstance(element, bs4.element.Tag):
                attributes_to_check = []

                if element.name == 'form':
                    attributes_to_check.extend([('action',), ('name', 'id')])
                elif element.name in ['input', 'textarea']:
                    input_type = element.attrs.get('type', 'text')

                    if input_type == 'hidden':
                        continue
                    elif input_type in ['button', 'submit']:
                        attributes_to_check.extend([('value',), ('name', 'id')])
                    else:
                        attributes_to_check.extend([('placeholder',), ('name', 'id')])

                for idx, attr_list in enumerate(attributes_to_check):
                    for key in attr_list:
                        if attr_value := element.attrs.get(key, "").strip():
                            all_doc_strings.append(attr_value)
                            xpath_tags, xpath_subscripts = self.xpath_soup(element)
                            xpath_tags.append('ATTRIBUTE')
                            xpath_subscripts.append(idx)
                            string2xtag_seq.append(xpath_tags)
                            string2xsubs_seq.append(xpath_subscripts)

        if len(all_doc_strings) != len(string2xtag_seq):
            raise ValueError("Number of doc strings and xtags does not correspond")
        if len(all_doc_strings) != len(string2xsubs_seq):
            raise ValueError("Number of doc strings and xsubs does not correspond")

        return all_doc_strings, string2xtag_seq, string2xsubs_seq


RAW_LABEL_MAP = {
    'Donation Form': 'Payment Form',
    'Gift Card Purchase Form': 'Payment Form',

    'Appointment Form': 'Reservation Form',
    'Schedule a meeting Form': 'Reservation Form',
    'Schedule Form': 'Reservation Form',
    'Schedule a Demo Form': 'Reservation Form',
    'Webinar Registration Form': 'Reservation Form',

    'Insurance Application Form': 'Financial Application Form',
    'Insurance Claim Form': 'Financial Application Form',

    'Unknown': None,
    'Other Form': None,
    'Filter Form': None,
    'Search Form': None,
    'Age Verification Form': None,
    'Location Search Form': None,
    'Location Selection Form': None,
    'Order Tracking Form': None,
    'Order Status Form': None,
}

LABELS = [
    'Account Registration Form',
    'Account Login Form',
    'Account Recovery Form',
    'Payment Form',
    'Role Application Form',
    'Financial Application Form',
    #'Service Application Form',
    'Subscription Form',
    'Reservation Form',
    'Contact Form',
    'Content Submission Form',
    #'Feedback Form',
    #'Information Request Form',
]


def load_html_string(example, root_dir):
    root_dir = Path(root_dir)

    domain = example['domain']
    job_hash = example['job_hash']
    form_filename = example['form_filename']

    job_dir = root_dir / domain / job_hash

    with open(job_dir / 'job.json', 'rb') as fin:
        job_data = json.load(fin)

    page_title = job_data["pageTitle"].replace('\n', ' ')

    with open(job_dir / form_filename, 'rb') as fin:
        form_data = json.load(fin)

    form_html = form_data["element"]['outerHTML']

    returned_obj = {"html_strings": f'<title>{html.escape(page_title)}</title>{form_html}'}

    if 'annotations' in example:
        votes = json.loads(example['annotations'])
        n_votes = len(votes)
        vote_counter = Counter(RAW_LABEL_MAP.get(i, i) for i in votes)

        if (vote_counter.most_common(1)[0][1] <= n_votes // 2
            or any((k and k not in LABELS) for k in vote_counter)):
            returned_obj['label'] = None
        else:
            returned_obj['label'] = [vote_counter[i] / n_votes for i in LABELS]

    return returned_obj
