#!/usr/bin/env python3

import argparse
import sqlite3
from collections import Counter

from whatwg_url import parse_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    args = parser.parse_args()

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    cur = con.execute("SELECT DISTINCT url FROM privacy_policy_link WHERE url IS NOT NULL")
    all_urls = list(d for d, in cur)

    # Step 1: domain -> HTTP / HTTPs
    scheme_map = {}
    norm_map = {}

    for url in all_urls:
        parsed = parse_url(url)

        # Prefer HTTPs
        if scheme_map.get(parsed.hostname) != 'https':
            scheme_map[parsed.hostname] = parsed.scheme

    for url in all_urls:
        parsed = parse_url(url)
        parsed.scheme = scheme_map[parsed.hostname]
        norm_map[url] = parsed.href

    # Step 2: Try to strip (1) fragment; (2) query; (3) trailing / in the path
    component_to_strip = ['fragment', 'query', 'path']

    for i in range(len(component_to_strip)):
        prefix_counter = Counter()
        prefix_map = {}

        for url in frozenset(norm_map.values()):
            parsed = parse_url(url)

            for component in component_to_strip[:i + 1]:
                setattr(parsed, component, parsed.path.rstrip('/') if component == 'path' else None)

            norm_url = parsed.href

            prefix_counter[norm_url] += 1
            prefix_map[url] = norm_url

        for url in all_urls:
            norm_url = prefix_map[norm_map[url]]

            if prefix_counter[norm_url] > 1:
                norm_map[url] = norm_url

    con.execute('DROP TABLE IF EXISTS privacy_policy_link_normalized')
    con.execute('''CREATE TABLE privacy_policy_link_normalized (
        url TEXT UNIQUE NOT NULL,
        normalized_url TEXT NOT NULL
    ) STRICT''')
    con.executemany('INSERT INTO privacy_policy_link_normalized VALUES (?, ?)', norm_map.items())
    con.commit()


if __name__ == '__main__':
    main()
