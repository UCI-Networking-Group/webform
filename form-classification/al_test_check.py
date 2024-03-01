#!/usr/bin/env python3

import argparse
import json
import os
import sqlite3
import csv

import numpy as np
from datasets import Dataset
from sklearn.metrics import accuracy_score, classification_report
from utils import LABELS, load_html_string


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("test_csv", help="CSV list of test samples")
    parser.add_argument('--output', '-o', type=str, required=True, help="JSON output file")
    parser.add_argument("--nproc", type=int, default=min(os.cpu_count(), 32), help="Number of processes")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    test_descs = set()

    with open(args.test_csv, "r", encoding='utf-8', newline="") as fin:
        reader = csv.DictReader(fin)

        for row in reader:
            test_descs.add((row['domain'], row['job_hash'], row['form_filename']))

    # Repeat how the training script loads the dataset
    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')

    ds_form_descriptors = Dataset.from_sql('''
        SELECT domain, job_hash, form_filename, annotations FROM form_classification_gpt
    ''', con, keep_in_memory=True
    ).filter(lambda e: (e['domain'], e['job_hash'], e['form_filename']) in test_descs)

    ds_form = ds_form_descriptors.map(
        load_html_string,
        fn_kwargs={'root_dir': args.root_dir},
        num_proc=args.nproc,
        keep_in_memory=True,
    ).filter(lambda e: e['label'] is not None)

    # Add predictions to the dataset
    cur = con.execute('SELECT domain, job_hash, form_filename, scores FROM form_classification')
    all_proba = {}

    for domain, job_hash, form_filename, scores_json in cur:
        if (domain, job_hash, form_filename) in test_descs:
            scores_dict = json.loads(scores_json)
            all_proba[domain, job_hash, form_filename] = [scores_dict[label] for label in LABELS]

    con.close()

    def add_proba(example):
        domain = example['domain']
        job_hash = example['job_hash']
        form_filename = example['form_filename']
        return {'proba': all_proba[domain, job_hash, form_filename]}

    ds = ds_form.map(add_proba)

    labels = np.array(ds['label'])
    proba = np.array(ds['proba'])

    hard_labels = np.int32(labels >= 0.5)
    hard_predicts = np.int32(proba >= 0.5)

    cls_report = classification_report(
        hard_labels,
        hard_predicts,
        target_names=LABELS,
        output_dict=True,
        zero_division=np.nan,
    )

    metrics = {
        'accuracy': accuracy_score(hard_labels, hard_predicts),
    }

    for key1, d1 in cls_report.items():
        for key2, value in d1.items():
            metrics[f'{key1}/{key2}'] = value

    print(metrics)

    with open(args.output, "w", encoding='utf-8') as fout:
        json.dump(metrics, fout, indent=2)


if __name__ == "__main__":
    main()
