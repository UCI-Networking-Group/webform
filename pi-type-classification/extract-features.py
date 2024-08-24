#!/usr/bin/env python3
'''Featurize form fields as strings for classification'''

import argparse
import json
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import tqdm
from field_string import process_form


def worker(args):
    rootdir, domain, job_hash = args
    field_string_list = []

    jobdir = rootdir / domain / job_hash

    with open(jobdir / "job.json", encoding='utf-8') as fin:
        job_info = json.load(fin)
        url = next(u for u in reversed(job_info["navigationHistory"]) if u)

    for form_json_file in jobdir.glob("form-*.json"):
        with form_json_file.open(encoding='utf-8') as fin:
            form_info = json.load(fin)

        for field_str in process_form(form_info):
            info = {
                "text": field_str,
                "domain": domain,
                "job_hash": job_hash,
                "filename": form_json_file.name,
                "url": url,
                "label": [],
            }

            field_string_list.append((field_str, info))

    return field_string_list


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("output")
    args = parser.parse_args()

    rootdir = Path(args.rootdir)
    field_str_dedup = set()

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')
    cur = con.execute('''
        SELECT domain, job_hash FROM page_language
        WHERE lang_code in ('en', 'guess:en')
    ''')

    tasks = [(rootdir, domain, job_hash) for domain, job_hash in cur]

    with (
        open(args.output, "w", encoding='utf-8') as fout,
        ProcessPoolExecutor() as executor
    ):
        for fs_list in tqdm.tqdm(executor.map(worker, tasks), total=len(tasks)):
            for field_str, info in fs_list:
                if field_str and field_str not in field_str_dedup:
                    field_str_dedup.add(field_str)
                    print(json.dumps(info), file=fout)


if __name__ == "__main__":
    main()
