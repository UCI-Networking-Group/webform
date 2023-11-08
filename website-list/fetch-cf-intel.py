import CloudFlare
import os
import csv
import dbm
import json

account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
batch_size = 8

with (CloudFlare.CloudFlare() as cf,
      open("top-1m.csv", "r") as fin,
      dbm.open('cf-intel.db', 'c') as db):

    csv_reader = csv.reader(fin)

    while True:
        domain_batch = []

        for _, domain in csv_reader:
            if domain.encode() not in db:
                domain_batch.append(domain)

                if len(domain_batch) == batch_size:
                    break

        if not domain_batch:
            break

        print("Batch:", ", ".join(domain_batch))

        params = [("domain", d) for d in domain_batch]
        answers = cf.accounts.intel.domain.bulk.get(account_id, params=params)

        for answer in answers:
            domain = answer["domain"]
            db[domain] = json.dumps(answer)

        print("Progress:", len(db))

print("Done!")