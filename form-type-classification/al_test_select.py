#!/usr/bin/env python3

import argparse
import csv
import sqlite3
from collections import defaultdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("output", help="CSV file to write the results to")
    parser.add_argument("--target", type=int, default=20,
                        help="How many samples for each form type")
    args = parser.parse_args()

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    cur = con.execute('''
        SELECT domain, job_hash, form_filename, form_type FROM form_classification
        WHERE job_hash NOT IN (SELECT job_hash FROM form_classification_gpt)
        ORDER BY RANDOM()
    ''')

    form_selection = defaultdict(list)

    for domain, job_hash, form_filename, form_type in cur:
        if len(form_selection[form_type]) < args.target:
            form_selection[form_type].append((domain, job_hash, form_filename))

    with open(args.output, "w", encoding='utf-8', newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["domain", "job_hash", "form_filename", "weight"])

        for form_type, forms in sorted(form_selection.items()):
            print(form_type, len(forms))

            for domain, job_hash, form_filename in forms:
                writer.writerow([domain, job_hash, form_filename, 1.0])

    con.close()


if __name__ == "__main__":
    main()
