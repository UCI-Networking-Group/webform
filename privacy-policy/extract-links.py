#!/usr/bin/env python3

import argparse
import functools
import json
import multiprocessing as mp
import os
import queue
import re
import sqlite3
import urllib.parse as urlparse
import warnings
from pathlib import Path

import numpy as np
import tldextract
import tqdm
import whatwg_url
from bs4 import BeautifulSoup
from sklearn.metrics.pairwise import cosine_similarity

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

def cpu_worker(args: tuple[mp.Queue, Path, str], match_threshold=0.75):
    gpu_queue, rootdir, domain = args
    conn, conn_other = mp.Pipe()

    @functools.cache
    def get_job_info(job_hash: str) -> tuple[str, list[str]]:
        with open(rootdir / domain / job_hash / "job.json", "rb") as fin:
            job_info = json.load(fin)

        page_url = next(u for u in reversed(job_info["navigationHistory"]) if u)
        parents = job_info['parents']

        return page_url, parents

    @functools.cache
    def check_page(job_hash: str):
        page_url, _ = get_job_info(job_hash)

        with open(rootdir / domain / job_hash / "page.html", "rb") as fin:
            soup = BeautifulSoup(fin, 'lxml')

        return check_privacy_policy_soup(soup, page_url)

    def check_privacy_policy_soup(soup: BeautifulSoup, page_url: str) -> tuple[str, str] | None:
        core_domain = tldextract.extract(page_url).domain

        # Collect unique pairs of (text, url)
        _unique_hrefs = set()

        for a_elem in soup.find_all('a', {"href": True}):
            text = a_elem.get_text().strip()

            try:
                full_url = whatwg_url.parse_url(a_elem.get('href'), base=page_url,
                                                encoding=soup.original_encoding or 'utf-8')
            except whatwg_url.UrlParserError:
                continue

            if full_url.scheme in ('http', 'https'):
                _unique_hrefs.add((text, full_url.href))

        if not _unique_hrefs:
            return None

        unique_hrefs = sorted(_unique_hrefs)

        features = []
        scores = np.zeros(len(unique_hrefs))

        for i, (text, url) in enumerate(unique_hrefs):
            # If containing seed phrases, set the score to at least match_threshold
            if RePhraseMatcher.search(text) or RePhraseMatcher.search(url):
                scores[i] = match_threshold

            # Use the link text as features
            features.append(text)

            # Use the last part of URL as features
            last_part = os.path.basename(urlparse.urlsplit(url).path.rstrip('/'))
            last_part = urlparse.unquote(last_part)
            last_part = os.path.splitext(last_part)[0]
            features.append(last_part)

        # Get text similarity scores
        gpu_queue.put((conn_other, features))
        sim_scores: np.ndarray = conn.recv()
        scores = np.maximum(scores, sim_scores.reshape(-1, 2).max(1))

        # Prioritize links that are in the same domain
        domain_match = np.fromiter(
            (tldextract.extract(url).domain == core_domain for _, url in unique_hrefs),
            dtype=bool,
        )

        for mask in domain_match, ~domain_match:
            bm_idx = (scores * mask).argmax()

            if scores[bm_idx] >= match_threshold:
                return unique_hrefs[bm_idx]

        return None

    def _check():
        all_results = {}

        for job_dir in (rootdir / domain).iterdir():
            job_hash = job_dir.name
            form_files = list(job_dir.glob('form-*.json'))

            if form_files:
                page_url, parents = get_job_info(job_hash)

            for f in form_files:
                with f.open("rb") as fin:
                    form_info = json.load(fin)

                form_html = form_info['element']['outerHTML']
                form_soup = BeautifulSoup(form_html, 'lxml')

                # Check the form for links
                if href := check_privacy_policy_soup(form_soup, page_url):
                    all_results[domain, job_hash, f.name] = ('FORM', *href)
                    continue

                # Check current pages for links
                if href := check_page(job_hash):
                    all_results[domain, job_hash, f.name] = ('PAGE', *href)
                    continue

                # Check parent pages for links
                for parent_job_hash in parents[::-1]:
                    if href := check_page(parent_job_hash):
                        all_results[domain, job_hash, f.name] = ('PARENT', *href)
                        break
                else:
                    # No privacy policy link found
                    all_results[domain, job_hash, f.name] = ('UNKNOWN', None, None)

        return all_results

    return _check()


def gpu_worker(gpu_queue: mp.Queue, worker_index: int, model_name: str):
    warnings.filterwarnings('ignore', module='transformers.utils')

    # Disable parallelism in ML libraries
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'

    # Somehow importing torch at top-level cause a major slowdown...
    # pylint: disable=import-outside-toplevel
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)

    gpu_count = torch.cuda.device_count()

    model = SentenceTransformer(model_name, device=f'cuda:{worker_index % gpu_count}')
    seed_embeddings = model.encode(SEED_PHRASES)
    memory: dict[str, float] = {}

    while task_tuple := gpu_queue.get():
        batch = [task_tuple]

        while True:
            try:
                task_tuple = gpu_queue.get_nowait()
            except queue.Empty:
                break

            batch.append(task_tuple)

        all_texts = [t for _, tl in batch for t in tl]
        new_texts = list({t for t in all_texts if t not in memory})

        if new_texts:
            new_embeddings = model.encode(new_texts)
            # Convert to float16 to mitigate numerical instability
            new_scores = cosine_similarity(new_embeddings, seed_embeddings).max(1).astype(np.float16)
            memory.update(zip(new_texts, new_scores))

        for conn, features in batch:
            sim_score = np.fromiter((memory[t] for t in features), dtype=float)
            conn.send(sim_score)
            conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("--n_cpu", type=int, default=os.cpu_count())
    parser.add_argument("--n_gpu", type=int, default=1)
    parser.add_argument("--model", default='sentence-transformers/all-MiniLM-L6-v2')
    args = parser.parse_args()

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

    cur = con.execute("SELECT DISTINCT domain FROM form_classification")
    all_domains = sorted({d for d, in cur})
    n_domain = len(all_domains)

    rootdir = Path(args.rootdir)

    manager = mp.Manager()
    gpu_queue = manager.Queue()

    # Warm up: make sure the model is downloaded in one process
    p = mp.Process(target=gpu_worker, args=(gpu_queue, 0, args.model))
    p.start()
    gpu_queue.put(None)
    p.join()

    # Create GPU workers
    gpu_workers = []

    for idx in range(args.n_gpu):
        p = mp.Process(target=gpu_worker, args=(gpu_queue, idx, args.model))
        gpu_workers.append(p)
        p.start()

    # Run CPU workers
    with mp.pool.Pool(args.n_cpu) as pool:
        tasks = pool.imap_unordered(cpu_worker, [(gpu_queue, rootdir, d) for d in all_domains])

        for results in tqdm.tqdm(tasks, total=n_domain, smoothing=0.01):
            for (domain, job_hash, form_filename), pp_info in results.items():
                con.execute(
                    'INSERT INTO privacy_policy_link VALUES (?, ?, ?, ?, ?, ?)',
                    (domain, job_hash, form_filename, *pp_info))

            con.commit()

    # Gracefully shutdown GPU workers
    for idx in range(args.n_gpu):
        gpu_queue.put(None)

    for p in gpu_workers:
        p.join()


if __name__ == '__main__':
    main()
