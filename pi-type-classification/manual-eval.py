#!/usr/bin/env python3

import argparse
import json
import random
from itertools import chain

import numpy as np
from sklearn.metrics import classification_report
from label_studio_sdk import Client
import tqdm
from more_itertools import chunked, one
from setfit import SetFitModel


def main():
    BATCH_SIZE = 64

    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Doccano URL")
    parser.add_argument("project_id", help="Project ID")
    parser.add_argument("model_dir", help="Model path")
    parser.add_argument("-P", "--api-key", required=True, help="Password")
    args = parser.parse_args()

    model = SetFitModel.from_pretrained(args.model_dir)

    ls = Client(url=args.url, api_key=args.api_key)
    project = ls.get_project(args.project_id)

    labels_mapping = {}

    for task in project.export_tasks():
        annotations = task['annotations']
        assert len(annotations) == 1
        annotation_results = annotations[0]['result']
        assert len(annotation_results) <= 1

        if len(annotation_results) == 0:
            labels = []
        else:
            labels = annotation_results[0]['value']['choices']

        text = task['data']['text']
        labels_mapping[text] = labels

    y_pred = []
    y_gt = []

    for batch in chunked(labels_mapping, BATCH_SIZE):
        pred = model.predict(batch, batch_size=BATCH_SIZE)

        for row, text in zip(pred, batch):
            nz_indices, = row.nonzero(as_tuple=True)
            labels = [model.labels[i] for i in nz_indices]
            onehot_gt = [int(s in labels_mapping[text]) for s in model.labels]
            y_pred.append(row.numpy())
            y_gt.append(onehot_gt)
            if sum(row) == 0:
                print(text)

    selected_labels = [
        "Address",
        "DateOfBirth",
        "EmailAddress",
        "Ethnicity",
        "Gender",
        "GovernmentId",
        "LocationCityOrCoarser",
        "BankAccountNumber",
        "PersonName",
        "PhoneNumber",
        "PostalCode",
        "UsernameOrOtherId",
        "TaxId",
        "AgeOrAgeGroup",
        "CitizenshipOrImmigrationStatus",
        "MilitaryStatus"
    ]
    selected_label_indices = [model.labels.index(l) for l in selected_labels]


    y_pred = np.array(y_pred)[:, selected_label_indices]
    y_gt = np.array(y_gt)[:, selected_label_indices]
    print(y_pred.sum(0))

    print(classification_report(y_gt, y_pred, target_names=selected_labels, digits=3))

if __name__ == "__main__":
    main()
