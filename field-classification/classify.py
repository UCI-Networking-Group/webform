#!/usr/bin/env python3

import argparse
import sqlite3
import json
from pathlib import Path

import tqdm
from field_string import process_form


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-dataset", required=True, help="Prelabelled JSONL dataset")
    parser.add_argument("rootdir")
    args = parser.parse_args()

    rootdir = Path(args.rootdir)
    cached_results = {}

    with open(args.input_dataset, encoding='utf-8') as fin:
        for line in fin:
            sample = json.loads(line)
            cached_results[sample["text"]] = sample["label"]

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    con.execute('DROP TABLE IF EXISTS field_classification')
    con.execute('''CREATE TABLE field_classification (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        form_filename TEXT NOT NULL,
        field_list TEXT,
        UNIQUE(job_hash, form_filename)
    ) STRICT''')

    cur_jobs = con.execute("SELECT domain, job_hash FROM page_language WHERE lang_code IN ('en', 'guess:en')")
    total_jobs = con.execute("SELECT COUNT(*) FROM page_language WHERE lang_code IN ('en', 'guess:en')").fetchone()[0]

    for domain, job_hash in tqdm.tqdm(cur_jobs, total=total_jobs):
        jobdir = rootdir / domain / job_hash

        for form_json_file in jobdir.glob("form-*.json"):
            with form_json_file.open(encoding='utf-8') as fin:
                form_info = json.load(fin)

            form_results = []

            for field_str in process_form(form_info):
                if result := cached_results.get(field_str):
                    form_results.extend(result)

            if form_results:
                form_results = sorted(set(form_results))
                con.execute('INSERT INTO field_classification VALUES (?, ?, ?, json(?))',
                            (domain, job_hash, form_json_file.name, json.dumps(form_results)))
                con.commit()


if __name__ == "__main__":
    main()
