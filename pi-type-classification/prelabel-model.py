#!/usr/bin/env python3

import argparse
import json

import tqdm
from more_itertools import chunked
from setfit import SetFitModel


def main():
    BATCH_SIZE = 64

    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input dataset path")
    parser.add_argument("model_dir", help="Model path")
    parser.add_argument("output", help="Output dataset path")
    args = parser.parse_args()

    model = SetFitModel.from_pretrained(args.model_dir)

    with (open(args.input, encoding='utf-8') as fin,
          open(args.output, "w", encoding='utf-8') as fout):
        for batch in chunked(map(json.loads, tqdm.tqdm(fin)), BATCH_SIZE):
            batch_text = [i["text"] for i in batch]
            pred = model.predict(batch_text, batch_size=BATCH_SIZE)

            for row, full_dict in zip(pred, batch):
                nz_indices, = row.nonzero(as_tuple=True)
                labels = [model.labels[i] for i in nz_indices]
                full_dict["label"] = labels
                print(json.dumps(full_dict), file=fout)


if __name__ == '__main__':
    main()
