import csv
import json
import dbm
import tldextract
from urllib.parse import urlsplit
import re


def main():
    with (open('cloudflare-domain-intel.csv', 'r', newline='') as fin,
          open('domain-database.csv', 'w', newline='') as fout,
          dbm.open('domain-connection-info.db', 'r') as db):
        
        reader = csv.DictReader(fin)
        writer = None

        for row in reader:
            if writer is None:
                writer = csv.DictWriter(fout, fieldnames=reader.fieldnames + ['init_url', 'final_url', 'lang'])

            domain = row['domain']
            conn_info = json.loads(db[domain])
            print(conn_info)

            init_url = conn_info["init_url"]
            final_url = urlsplit(conn_info["final_url"], allow_fragments=False)._replace(query='').geturl()

            row.update({
                'init_url': init_url,
                'final_url': final_url,
                'lang': conn_info["lang"]
            })

            writer.writerow(row)

            # if int(row['tranco_82NJV_ranking']) > 100000:
            #     break

            # if domain.encode() not in db:
            #     continue

            # tld_info = tldextract.extract(conn_info["final_url"])
            # is_english = re.match(r'\b(?:guess:)?eng?(_\w+)?\b', conn_info["lang"]) is not None

            # if tld_info.registered_domain == domain and is_english:
            #     print(domain, conn_info["init_url"])


if __name__ == '__main__':
    main()
