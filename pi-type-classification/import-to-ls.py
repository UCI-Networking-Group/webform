#!/usr/bin/env python3

import argparse
import json

import tqdm
from label_studio_sdk import Client
from more_itertools import chunked


def prepare_task(json_str):
    info = json.loads(json_str)
    label = info.pop("label")
    verified = info.pop("verified")

    task = {
        "data": info,
        ("annotations" if verified else "predictions"): [{
            "result": [{
                "from_name": "data_type",
                "to_name": "text",
                "type": "choices",
                "value": {"choices": label}
            }],
        }]
    }

    return task


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Label Studio URL")
    parser.add_argument("project_id", help="Project ID")
    parser.add_argument("input", help="Input dataset path")
    parser.add_argument("-P", "--api-key", required=True, help="Password")
    args = parser.parse_args()

    ls = Client(url=args.url, api_key=args.api_key)
    project = ls.get_project(args.project_id)

    project.delete_all_tasks()

    with open(args.input, encoding='utf-8') as fin:
        for samples in chunked(map(prepare_task, tqdm.tqdm(fin)), 10000):
            project.import_tasks(samples)


if __name__ == "__main__":
    main()
