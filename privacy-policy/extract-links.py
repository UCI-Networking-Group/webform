#!/usr/bin/env python3

import argparse
import json
import os
import re
import sqlite3
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
import torch
import tqdm
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.urls import url_fix

SEED_PHRASES = [
    'privacy policy',
    'privacy notice',
    'privacy statement',
    'privacy center',
    'privacy & terms',
    'privacy & cookies notice',
]

RePhraseMatcher = re.compile(
    '|'.join(map(lambda i: re.sub(r'\W+', r'\\W*', i), SEED_PHRASES)),
    re.IGNORECASE
)


class TextScorer:
    def __init__(self, device=None):
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device)
        self.seed_embeddings = self.model.encode(SEED_PHRASES)
        self.memory = {}

    def __call__(self, all_texts):
        new_texts = sorted({t for t in all_texts if t not in self.memory})

        if new_texts:
            new_embeddings = self.model.encode(new_texts)
            new_scores = cosine_similarity(new_embeddings, self.seed_embeddings).max(1)
            self.memory.update(zip(new_texts, new_scores))

        return np.fromiter((self.memory[t] for t in all_texts), dtype=float)


def check_privacy_policy_soup(scorer: TextScorer, soup: BeautifulSoup, page_url: str):
    unique_hrefs = set()

    for a_elem in soup.find_all('a'):
        text = a_elem.get_text().strip()

        try:
            href = urljoin(page_url, a_elem.get('href'))
        except ValueError:
            continue

        if urlparse(href).scheme in ('http', 'https'):
            unique_hrefs.add((text, url_fix(href)))

    if unique_hrefs:
        texts, urls = zip(*unique_hrefs)
        features = texts

        for _ in range(2):
            sim_score = scorer(features)
            bm_idx = sim_score.argmax()

            if sim_score[bm_idx] > 0.75:
                return texts[bm_idx], urls[bm_idx]

            # Next try use the last part of the URL as a feature
            features = []

            for u in urls:
                last_part = urlparse(u).path.rstrip('/').rsplit('/', 1)[-1]
                last_part = os.path.splitext(last_part)[0]
                features.append(last_part)

        # As last resort, do a fuzzy match
        for text, url in unique_hrefs:
            if RePhraseMatcher.search(text) or RePhraseMatcher.search(url):
                return text, url

    return None, None


def check_website(rootdir: Path, domain: str):
    global scorer

    _page_info_catch = {}

    def get_page(job_hash):
        if job_hash not in _page_info_catch:
            with open(rootdir / domain / job_hash / "job.json", "rb") as fin:
                job_info = json.load(fin)

            with open(rootdir / domain / job_hash / "page.html", "rb") as fin:
                content = fin.read()

            page_url = next(u for u in reversed(job_info["navigationHistory"]) if u)
            soup = BeautifulSoup(content, 'lxml')
            link_text, url = check_privacy_policy_soup(scorer, soup, page_url)

            _page_info_catch[job_hash] = page_url, None

            if url is not None:
                _page_info_catch[job_hash] = page_url, ('PAGE', link_text, url)
            elif job_info['parents']:
                _, pp_info = get_page(job_info['parents'][-1])

                if pp_info is not None:
                    _page_info_catch[job_hash] = page_url, ('PARENT', pp_info[1], pp_info[2])

        return _page_info_catch[job_hash]

    def _check():
        domain_dir = rootdir / domain
        all_results = {}

        for job_dir in domain_dir.iterdir():
            job_hash = job_dir.name

            for form_file in job_dir.glob('form-*.json'):
                page_url, page_pp_info = get_page(job_hash)

                with open(form_file, "rb") as fin:
                    form_info = json.load(fin)

                form_html = form_info['element']['outerHTML']
                form_soup = BeautifulSoup(form_html, 'lxml')

                link_text, url = check_privacy_policy_soup(scorer, form_soup, page_url)

                if url:
                    all_results[domain, job_hash, form_file.name] = 'FORM', link_text, url
                elif page_pp_info:
                    all_results[domain, job_hash, form_file.name] = page_pp_info
                else:
                    all_results[domain, job_hash, form_file.name] = None

        return all_results

    return _check()


def init_proc():
    global scorer
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    gpu_count = torch.cuda.device_count()
    scorer = TextScorer(device=('cuda:' + str(os.getpid() % gpu_count)) if gpu_count else 'cpu')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("--nproc", type=int, default=min(16, os.cpu_count()))
    args = parser.parse_args()

    rootdir = Path(args.rootdir)

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    con.execute('DROP TABLE IF EXISTS privacy_policy_link')
    con.execute('''CREATE TABLE privacy_policy_link (
        domain TEXT NOT NULL,
        job_hash TEXT NOT NULL,
        form_filename TEXT NOT NULL,
        scope TEXT NOT NULL,
        text TEXT,
        url TEXT,
        UNIQUE(job_hash, form_filename)
    ) STRICT''')

    cur = con.execute("SELECT DISTINCT domain FROM page_language WHERE lang_code IN ('en', 'guess:en')")
    all_domains = set(d for d, in cur)

    with ProcessPoolExecutor(args.nproc, initializer=init_proc) as executor:
        pbar = tqdm.tqdm(total=len(all_domains), smoothing=0.01)

        for results in executor.map(check_website, [rootdir] * len(all_domains), all_domains):
            for (domain, job_hash, form_filename), pp_info in results.items():
                if pp_info is None:
                    pp_info = ('UNKNOWN', None, None)

                con.execute(
                    'INSERT INTO privacy_policy_link VALUES (?, ?, ?, ?, ?, ?)',
                    (domain, job_hash, form_filename, *pp_info))

            con.commit()
            pbar.update(1)

        pbar.close()


if __name__ == '__main__':
    main()
