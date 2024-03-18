#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import sqlite3

import networkx as nx
import tqdm
import yaml

from poligrapher.graph_utils import KGraph


POLIGRAPH_DATA_MAPPING = {
    'email address': 'EmailAddress',

    'date of birth': 'DateOfBirth',
    'birth year': 'DateOfBirth',
    'birth month': 'DateOfBirth',

    'postal address': 'Address',

    "race / ethnicity": 'Ethnicity',

    'gender': 'Gender',
    'sexual preference': 'Gender',
    'sexuality': 'Gender',
    'sex gender': 'Gender',
    'sexual orientation identity': 'Gender',

    "credit / debit card number": 'BankAccountNumber',
    'bank card number': 'BankAccountNumber',

    'person name': 'PersonName',

    'phone number': 'PhoneNumber',

    'ssn': 'TaxId',
    'social security numbers': 'TaxId',
    'social security id': 'TaxId',
    'tax identification number': 'TaxId',
    'tax id': 'TaxId',
    'tax id number': 'TaxId',
    'tax identifier': 'TaxId',

    'age': 'AgeOrAgeGroup',
    'age group': 'AgeOrAgeGroup',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("privacy_policy_dir")
    args = parser.parse_args()

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    con.execute('DROP TABLE IF EXISTS privacy_policy_disclosures')
    con.execute('''
    CREATE TABLE IF NOT EXISTS privacy_policy_disclosures (
        url TEXT UNIQUE NOT NULL,
        disclosures TEXT NOT NULL
    )
    ''')

    cur = con.execute('SELECT DISTINCT url FROM privacy_policy_link WHERE url IS NOT NULL')
    url_list = [url for url, in cur]

    for url in tqdm.tqdm(url_list):
        url_black2s = hashlib.blake2s(url.encode()).hexdigest()
        pp_dir = os.path.join(args.privacy_policy_dir, url_black2s)

        if not os.path.exists(pp_dir):
            continue

        graph = KGraph(os.path.join(pp_dir, 'graph-extended.full.yml'))

        disclosures = {}

        for dt in graph.datatypes:
            mapped_dt = POLIGRAPH_DATA_MAPPING.get(dt.split('@')[0].strip())

            if mapped_dt is not None:
                disclosures.setdefault(mapped_dt, set())

                for entity in graph.who_collect(dt):
                    purposes = graph.purposes(entity, dt)
                    disclosures[mapped_dt].update(purposes)

        if len(disclosures) == 0:
            continue

        con.execute('INSERT INTO privacy_policy_disclosures VALUES (?, json(?))',
                    (url, json.dumps({k: list(v) for k, v in disclosures.items()}, sort_keys=True, indent=2)))
        con.commit()

if __name__ == '__main__':
    main()
