import argparse
import json
import os
import re
import sqlite3
from contextlib import nullcontext

import torch
import tqdm
from datasets import Dataset
from torch.utils.data import DataLoader, default_collate
from transformers import MarkupLMForSequenceClassification, MarkupLMProcessor, MarkupLMTokenizerFast
from utils import MyMarkupLMFeatureExtractor, load_html_string


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir", help="Path to the model directory")
    parser.add_argument("root_dir", help="Root directory of the dataset")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size")
    parser.add_argument("--nproc", type=int, default=min(os.cpu_count(), 32), help="Number of processes")
    parser.add_argument("--bf16", action="store_true", help="Use bfloat16")
    args = parser.parse_args()

    con = sqlite3.connect(args.root_dir.rstrip('/') + '.db')
    con.create_function("REGEXP", 2, lambda pattern, text: 1 if re.search(pattern, text) else 0)

    ds_form = Dataset.from_sql(r'''
        SELECT domain, job_hash, form_filename
            FROM field_classification
            WHERE field_list REGEXP
                '"(Address|EmailAddress|GovernmentId|BankAccountNumber|PersonName|PhoneNumber|UsernameOrOtherId|TaxId)"'
    ''', con, keep_in_memory=True)

    ds_form = ds_form.map(
        load_html_string,
        fn_kwargs={'root_dir': args.root_dir},
        num_proc=args.nproc,
        keep_in_memory=True,
    )

    # Deduplicate HTML strings
    ds_form = ds_form.sort("html_strings")
    last_html_string = None
    selected_indices = []

    for idx, example in enumerate(ds_form):
        if example['html_strings'] != last_html_string:
            last_html_string = example['html_strings']
            selected_indices.append(idx)

    ds_deduplicated = ds_form.select(selected_indices).select_columns(['html_strings'])

    # Process the HTML strings into MarkupLM model inputs
    feature_extractor = MyMarkupLMFeatureExtractor()
    tokenizer = MarkupLMTokenizerFast.from_pretrained("microsoft/markuplm-large")
    processor = MarkupLMProcessor(feature_extractor, tokenizer)

    def collate_fn(examples):
        html_strings = [e['html_strings'] for e in examples]
        processed = processor(html_strings, truncation=True, padding=True, return_tensors='pt')

        batch = default_collate(examples)
        batch.update(processed)

        return batch

    model = MarkupLMForSequenceClassification.from_pretrained(args.model_dir, device_map='cuda')
    model.eval()

    dataloader = DataLoader(
        ds_deduplicated,
        batch_size=args.batch_size,
        collate_fn=collate_fn,
        pin_memory=True,
        num_workers=args.nproc,
        shuffle=False,
    )

    con.execute('DROP TABLE IF EXISTS form_classification')
    con.execute('''CREATE TABLE form_classification (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        form_filename TEXT NOT NULL,
        form_type TEXT NOT NULL,
        scores TEXT NOT NULL,
        UNIQUE(job_hash, form_filename)
    ) STRICT''')

    # Main inference loop
    with (tqdm.tqdm(total=len(ds_form), smoothing=0.1) as pbar,
          torch.no_grad(),
          torch.autocast(device_type="cuda", dtype=torch.bfloat16) if args.bf16 else nullcontext()):
        ds_idx = 0

        for batch in dataloader:
            html_strings = batch.pop('html_strings')

            output, = model(**{k: v.to(model.device) for k, v in batch.items()}, return_dict=False)
            output.sigmoid_()
            output_list = output.tolist()

            for html_string, scores in zip(html_strings, output_list):
                dict_scores = {model.config.id2label[i]: score for i, score in enumerate(scores)}

                form_type = max(dict_scores, key=dict_scores.get)
                if dict_scores[form_type] < 0.5:
                    form_type = 'Unknown'

                scores_json = json.dumps(dict_scores, separators=(',', ':'))

                db_rows = []

                while ds_idx < len(ds_form) and ds_form[ds_idx]['html_strings'] == html_string:
                    desc = [ds_form[ds_idx][k] for k in ('domain', 'job_hash', 'form_filename')]
                    db_rows.append([*desc, form_type, scores_json])
                    ds_idx += 1

                assert len(db_rows) > 0
                con.executemany('INSERT INTO form_classification VALUES (?, ?, ?, ?, ?)', db_rows)
                con.commit()
                pbar.update(len(db_rows))

        assert ds_idx == len(ds_form)

    con.close()


if __name__ == "__main__":
    main()
