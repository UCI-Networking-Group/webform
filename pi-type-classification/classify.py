#!/usr/bin/env python3

import argparse
import json
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import tqdm
from field_string import process_form

_classification_map = {}


def worker(rootdir, job_descriptor):
    global _classification_map

    domain, job_hash = job_descriptor
    jobdir = rootdir / domain / job_hash
    rows = []

    for form_json_file in jobdir.glob("form-*.json"):
        with form_json_file.open(encoding='utf-8') as fin:
            form_info = json.load(fin)

        form_results = []

        for field_str in process_form(form_info):
            if result := _classification_map.get(field_str):
                form_results.extend(result)

        if form_results:
            rows.append((domain, job_hash, form_json_file.name, json.dumps(form_results)))

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-dataset", required=True, help="Prelabelled JSONL dataset")
    parser.add_argument("rootdir")
    args = parser.parse_args()

    rootdir = Path(args.rootdir)

    with open(args.input_dataset, encoding='utf-8') as fin:
        for line in fin:
            sample = json.loads(line)
            _classification_map[sample["text"]] = sample["label"]

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    con.execute('DROP TABLE IF EXISTS field_classification')
    con.execute('''CREATE TABLE field_classification (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        form_filename TEXT NOT NULL,
        field_list TEXT,
        UNIQUE(job_hash, form_filename)
    ) STRICT''')

    cur = con.execute("SELECT domain, job_hash FROM page_language WHERE lang_code IN ('en', 'guess:en')")
    job_descriptors = list(cur)

    with ProcessPoolExecutor() as executor:
        it = executor.map(worker, [rootdir] * len(job_descriptors), job_descriptors)

        for rows in tqdm.tqdm(it, total=len(job_descriptors)):
            con.executemany('INSERT INTO field_classification VALUES (?, ?, ?, ?)', rows)
            con.commit()

    con.close()


if __name__ == "__main__":
    main()
