#!/usr/bin/env python3

import argparse
import csv
import json
import sqlite3
from statistics import NormalDist


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("output", help="CSV file to write the results to")
    args = parser.parse_args()

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    cur = con.execute('SELECT domain, job_hash, form_filename, scores FROM form_classification')

    al_scores = {}
    norm_func = NormalDist(mu=0.5, sigma=0.15).pdf

    for domain, job_hash, form_filename, scores_json in cur:
        scores = json.loads(scores_json)
        al_scores[domain, job_hash, form_filename] = max(norm_func(i) for i in scores.values())

    with open(args.output, "w", encoding='utf-8', newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["domain", "job_hash", "form_filename", "al_score"])

        for key, al_score in sorted(al_scores.items(), key=lambda x: -x[1]):
            writer.writerow([*key, al_score])

    con.close()


if __name__ == "__main__":
    main()
