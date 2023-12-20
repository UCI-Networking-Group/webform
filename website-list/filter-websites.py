import csv
import json
import dbm
import tldextract
import re


def main():
    with (open('cloudflare-domain-intel.csv', 'r', newline='') as fin,
          dbm.open('domain-connection-info.db', 'r') as db):
        for row in csv.DictReader(fin):
            domain = row['domain']

            if int(row['tranco_82NJV_ranking']) > 100000:
                break

            if domain.encode() not in db:
                continue

            conn_info = json.loads(db[domain])
            tld_info = tldextract.extract(conn_info["final_url"])
            is_english = re.match(r'\b(?:guess:)?eng?(_\w+)?\b', conn_info["lang"]) is not None

            if tld_info.registered_domain == domain and is_english:
                print(domain, conn_info["init_url"])


if __name__ == '__main__':
    main()
