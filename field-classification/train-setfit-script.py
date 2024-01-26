import argparse
import json
import os
import tempfile
from collections import Counter
from zipfile import ZipFile

import numpy as np
from datasets import Dataset
from doccano_client import DoccanoClient
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
]

BACKGROUND_LABELS = [
    'SexualOrientation',
    'Irrelevant',
    'Other',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Doccano URL")
    parser.add_argument("project_id", type=int, help="Project ID")
    parser.add_argument("-o", "--output", help="Model output path")
    parser.add_argument("-U", "--username", required=True, help="Username")
    parser.add_argument("-P", "--password", required=True, help="Password")
    args = parser.parse_args()


    client = DoccanoClient(args.url)
    client.login(username=args.username, password=args.password)

    samples = []

    with tempfile.TemporaryDirectory() as tempdir:
        zip_path = client.download(args.project_id, "JSONL", True, tempdir)

        with ZipFile(zip_path) as zipf:
            with zipf.open(f"{args.username}.jsonl") as fin:
                for line in fin:
                    samples.append(json.loads(line))

    dataset = {
        "text": [],
        "label": [],
    }

    label_counter = Counter()

    for item in samples:
        text = item['text']
        labels = item["label"]
        label_array = [0] * len(LABELS)
        label_counter.update(labels)

        assert len(labels) > 0

        if labels[0] in BACKGROUND_LABELS:
            assert len(labels) == 1
            label_array = [0] * len(LABELS)
        else:
            for l in labels:
                label_array[LABELS.index(l)] = 1

        dataset["text"].append(text)
        dataset["label"].append(label_array)

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
