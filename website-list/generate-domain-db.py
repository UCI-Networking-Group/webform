import csv
import dbm
import json
import sqlite3
from urllib.parse import urlsplit

import tldextract


def main():
    con = sqlite3.connect("domain.db")
    con.execute('''CREATE TABLE domain_info (
        domain TEXT PRIMARY KEY,
        tranco_82NJV_ranking INTEGER UNIQUE NOT NULL,
        application TEXT,
        content_categories TEXT,
        additional_information TEXT,
        type TEXT,
        notes TEXT
    ) STRICT''')

    con.execute('''CREATE TABLE http_info (
        domain TEXT PRIMARY KEY,
        ip TEXT,
        url TEXT,
        redirected_url TEXT,
        lang TEXT,
        domain_has_changed INTEGER,
        FOREIGN KEY(domain) REFERENCES domain(domain)
    ) STRICT''')

    with (open('cloudflare-domain-intel.csv', encoding='utf-8', newline='') as fin,
          dbm.open('domain-connection-info.db', 'r') as db):

        domain_info_rows = []
        http_info_rows = []

        for row in csv.DictReader(fin):
            row['tranco_82NJV_ranking'] = int(row['tranco_82NJV_ranking'])
            domain_info_rows.append(row)

            domain = row['domain']

            try:
                conn_info = json.loads(db[domain])
            except KeyError:
                continue
            else:
                conn_info['domain'] = domain

                conn_info['url'] = conn_info.pop('init_url')

                final_url = conn_info.pop('final_url')
                conn_info['redirected_url'] = urlsplit(final_url, allow_fragments=False)._replace(query='').geturl()

                conn_info['domain_has_changed'] = tldextract.extract(final_url).registered_domain != domain

                http_info_rows.append(conn_info)

    con.executemany('''
        INSERT INTO domain_info VALUES
        (:domain, :tranco_82NJV_ranking, :application, :content_categories, :additional_information, :type, :notes)
    ''', domain_info_rows)
    con.commit()
    con.executemany('''
        INSERT INTO http_info VALUES
        (:domain, :ip, :url, :redirected_url, :lang, :domain_has_changed)
    ''', http_info_rows)
    con.commit()
    con.close()


if __name__ == '__main__':
    main()
