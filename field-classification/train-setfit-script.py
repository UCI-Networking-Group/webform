import argparse
import os
from collections import Counter

import numpy as np
from datasets import Dataset
from label_studio_sdk import Client
from setfit import SetFitModel, Trainer, TrainingArguments
from sklearn.metrics import classification_report

LABELS = [
    'Address',
    'DateOfBirth',
    'EmailAddress',
    'Ethnicity',
    'Fingerprints',
    'Gender',
    'GovernmentId',
    'LocationCityOrCoarser',
    'BankAccountNumber',
    'PersonName',
    'PhoneNumber',
    'PostalCode',
    'UsernameOrOtherId',
    'TaxId',
    'Password',
    'AgeOrAgeGroup',
    'CitizenshipOrImmigrationStatus',
    'BusinessInfo',
    'MilitaryStatus',
]

BACKGROUND_LABELS = [
    'SexualOrientation',
]

NEGATIVE_LABELS = [
    'Irrelevant',
    'Other',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Label Studio URL")
    parser.add_argument("project_id", help="Project ID")
    parser.add_argument("-P", "--api-key", required=True, help="Password")
    parser.add_argument("-o", "--output", help="Model output path")
    args = parser.parse_args()

    ls = Client(url=args.url, api_key=args.api_key)
    project = ls.get_project(args.project_id)

    dataset = {
        "text": [],
        "label": [],
    }

    label_counter = Counter()

    for task in project.export_tasks():
        annotations = task['annotations']
        assert len(annotations) == 1
        annotation_results = annotations[0]['result']
        assert len(annotation_results) == 1

        text = task['data']['text']
        labels = annotation_results[0]['value']['choices']

        label_array = [0] * len(LABELS)

        assert len(labels) > 0

        for l in labels:
            if l in NEGATIVE_LABELS:
                assert len(labels) == 1
                continue

            if l in BACKGROUND_LABELS:
                continue

            if l in LABELS:
                label_array[LABELS.index(l)] = 1
                label_counter[l] += 1
            else:
                raise ValueError(f"Unknown label {l}")

        dataset["text"].append(text)
        dataset["label"].append(label_array)

        if sum(label_array) == 0:
            label_counter["NEGATIVE"] += 1

    print(label_counter)
    train_dataset = Dataset.from_dict(dataset)

    model = SetFitModel.from_pretrained(
        "BAAI/bge-small-en-v1.5",
        #"allenai/longformer-base-4096",
        #"google/bigbird-roberta-base",
        #"andersonbcdefg/bge-small-4096",
        #"sentence-transformers/all-distilroberta-v1",
        #multi_target_strategy="one-vs-rest",
        multi_target_strategy="multi-output",
        labels=LABELS,
    )

    # Create trainer
    training_args = TrainingArguments(
        batch_size=20,
        sampling_strategy='undersampling',
        num_epochs=2,
        use_amp=True,
        output_dir=args.output,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
    )

    trainer.train()

    predictions = model(train_dataset["text"])
    y_pred = predictions.numpy()
    y_true = np.array(train_dataset["label"])
    print(classification_report(y_true, y_pred, target_names=LABELS, zero_division=np.nan))

    model.save_pretrained(os.path.join(args.output, "latest"), safe_serialization=True)


if __name__ == '__main__':
    main()
