#!/usr/bin/env python3

import argparse
import csv
import json
import sqlite3
import numpy as np
from statistics import NormalDist
from itertools import zip_longest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("output", help="CSV file to write the results to")
    args = parser.parse_args()

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    cur = con.execute('''
        SELECT domain, job_hash, form_filename, scores FROM form_classification
        WHERE job_hash NOT IN (SELECT job_hash FROM form_classification_gpt)
    ''')

    N_BINS = 20

    descriptors = []
    sample_score = []

    for domain, job_hash, form_filename, scores_json in cur:
        scores = json.loads(scores_json)
        descriptors.append((domain, job_hash, form_filename))
        sample_score.append(min(scores.values(), key=lambda v: abs(v - 0.5)))
        # sample_score.append(scores['Content Submission Form'])

    bin_edges = np.linspace(0.0, 1.0, N_BINS, endpoint=False)
    bin_indices = np.digitize(sample_score, bin_edges)
    bin_counts = np.bincount(bin_indices, minlength=N_BINS + 1)
    bin_weights = np.zeros(N_BINS + 1)
    norm = NormalDist(mu=0.5, sigma=0.15)

    for i, (left, right) in enumerate(zip_longest(bin_edges, bin_edges[1:], fillvalue=1.0)):
        cdf = norm.cdf(right) - norm.cdf(left)
        sample_weight = cdf / bin_counts[i + 1]
        bin_weights[i + 1] = sample_weight

    sample_weights = bin_weights[bin_indices]

    with open(args.output, "w", encoding='utf-8', newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["domain", "job_hash", "form_filename", "sample_score", "weight"])

        for i, desc in enumerate(descriptors):
            writer.writerow([*desc, sample_score[i], sample_weights[i]])

    con.close()


if __name__ == "__main__":
    main()
