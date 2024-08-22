#!/usr/bin/env python3

import argparse
import json
import random
from itertools import chain

from label_studio_sdk import Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Doccano URL")
    parser.add_argument("project_id", help="Project ID")
    parser.add_argument("input", help="Input dataset path")
    parser.add_argument("output", help="Output dataset path")
    parser.add_argument("-P", "--api-key", required=True, help="Password")
    args = parser.parse_args()

    ls = Client(url=args.url, api_key=args.api_key)
    project = ls.get_project(args.project_id)

    labels_mapping = {}

    for task in project.export_tasks():
        annotations = task['annotations']
        assert len(annotations) == 1
        annotation_results = annotations[0]['result']
        assert len(annotation_results) == 1

        text = task['data']['text']
        labels = annotation_results[0]['value']['choices']

        labels_mapping[text] = labels

    verified_samples = []
    other_samples = []

    with open(args.input, encoding='utf-8') as fin:
        for line in fin:
            sample = json.loads(line)
            text = sample["text"]

            if text in labels_mapping:
                sample["label"] = labels_mapping.pop(text)
                sample["verified"] = 1
                verified_samples.append(sample)
            else:
                sample["verified"] = 0
                other_samples.append(sample)

    random.shuffle(other_samples)
    for k, v in labels_mapping.items():
        if set(v) - {'Irrelevant', 'Other'}:
            print(k)

    with open(args.output, "w", encoding="utf-8") as fout:
        for sample in chain(verified_samples, other_samples):
            print(json.dumps(sample), file=fout)


if __name__ == "__main__":
    main()
