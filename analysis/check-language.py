#!/usr/bin/env python3

import argparse
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import tqdm
from langutil import check_html_language


def worker(jobdir):
    try:
        with open(jobdir / "page.html", "rb") as fin:
            content = fin.read()
    except FileNotFoundError:
        return None

    return check_html_language(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    args = parser.parse_args()

    rootdir = Path(args.rootdir)

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')
    con.execute('''CREATE TABLE IF NOT EXISTS page_language (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        lang_code TEXT,
        UNIQUE(domain, job_hash)
    ) STRICT''')

    done_set = set()

    for domain, job_hash in con.execute('SELECT domain, job_hash FROM page_language'):
        done_set.add((domain, job_hash))

    task_dict = {}

    for sitedir in rootdir.iterdir():
        if sitedir.is_dir():
            for jobdir in sitedir.iterdir():
                job_id = (sitedir.name, jobdir.name)

                if job_id not in done_set:
                    task_dict[jobdir] = job_id

    with ProcessPoolExecutor() as executor:
        for lang, (domain, job_hash) in zip(executor.map(worker, task_dict), tqdm.tqdm(task_dict.values())):
            if lang is not None:
                row = (domain, job_hash, lang)
                con.execute('INSERT INTO page_language VALUES (?, ?, ?)', row)
                con.commit()

    con.close()


if __name__ == '__main__':
    main()
