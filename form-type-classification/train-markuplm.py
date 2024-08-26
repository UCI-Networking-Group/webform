#!/usr/bin/env python3

import argparse
import os
import sqlite3

import numpy as np
from datasets import Dataset
from scipy.special import expit
from sklearn.metrics import accuracy_score, classification_report
from transformers import (MarkupLMForSequenceClassification, MarkupLMProcessor, MarkupLMTokenizerFast, Trainer,
                          TrainingArguments)
from utils import LABELS, MyMarkupLMFeatureExtractor, load_html_string


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("-o", "--output", type=str, required=True, help="Model output directory")
    parser.add_argument("--nproc", type=int, default=min(os.cpu_count(), 32), help="Number of processes")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--base-model", type=str, default="microsoft/markuplm-base", help="Base model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="Learning rate")
    args = parser.parse_args()

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    ds_form_descriptors = Dataset.from_sql('''
        SELECT domain, job_hash, form_filename, annotations FROM form_classification_gpt
    ''', con, keep_in_memory=True)
    con.close()

    ds_form = ds_form_descriptors.map(
        load_html_string,
        fn_kwargs={'root_dir': args.root_dir},
        num_proc=args.nproc,
        keep_in_memory=True,
    ).filter(lambda e: e['label'] is not None)

    #feature_extractor = MarkupLMFeatureExtractor()
    feature_extractor = MyMarkupLMFeatureExtractor()
    tokenizer = MarkupLMTokenizerFast.from_pretrained(args.base_model)
    processor = MarkupLMProcessor(feature_extractor, tokenizer)

    def preprocess_function(examples):
        return processor(examples["html_strings"], truncation=True, padding='max_length')

    ds_processed = ds_form.map(preprocess_function, batched=True, num_proc=args.nproc)
    ds = ds_processed.train_test_split(test_size=0.2, seed=args.seed)

    id2label = {i: l for i, l in enumerate(LABELS)}
    label2id = {l: i for i, l in enumerate(LABELS)}

    model = MarkupLMForSequenceClassification.from_pretrained(
        args.base_model, id2label=id2label, label2id=label2id,
        problem_type="multi_label_classification")

    training_args = TrainingArguments(
        output_dir=args.output,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        bf16=True,
        seed=args.seed,
    )

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        proba = expit(logits)

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

        return metrics

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(os.path.join(args.output, 'best'))


if __name__ == "__main__":
    main()
