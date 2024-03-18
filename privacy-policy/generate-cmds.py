import argparse
import json
import os
import sqlite3
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
import hashlib
import shlex

import numpy as np
import torch
import tqdm
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.urls import url_fix


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("outdir")
    args = parser.parse_args()

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    cur = con.execute('SELECT DISTINCT url FROM privacy_policy_link WHERE url IS NOT NULL')
    all_urls = set(d for d, in cur)

    con.close()

    for privacy_policy_url in all_urls:
        url_black2s = hashlib.blake2s(privacy_policy_url.encode()).hexdigest()
        out_dir = os.path.join(args.outdir, url_black2s)
        cmd1 = shlex.join(["test", "-e", out_dir])
        cmd2 = shlex.join(["python3", "html_crawler.py", privacy_policy_url, out_dir, "--no-readability-js"])
        print(cmd1 + " || " + cmd2)

if __name__ == '__main__':
    main()
