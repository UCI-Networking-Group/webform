import argparse
import json
import logging
import sqlite3
from pathlib import Path

import tqdm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", help="Path to the domain database")
    parser.add_argument("rootdir", help="Root directory of the crawled dataset")
    parser.add_argument("--target_jobs_per_domain", type=int, default=100,
                        help="Number of jobs expected per domain")
    args = parser.parse_args()

    domain_db_uri = Path(args.database).absolute().as_uri() + '?mode=ro'
    rootdir = Path(args.rootdir)

    con = sqlite3.connect(domain_db_uri, uri=True)
    cur = con.execute('''
        SELECT domain, ranking FROM tranco_list
        JOIN domain_info USING (domain)
        JOIN http_info USING (domain)
    ''')

    domain_ranking = dict(cur)

    form_count = 0
    domain_list = set()

    for domain_dir in tqdm.tqdm(list(rootdir.iterdir())):
        domain = domain_dir.name

        if domain not in domain_ranking:
            logging.error("%s: not found in the database", domain)
            continue

        job_dir_list = list(domain_dir.iterdir())

        if len(job_dir_list) < args.target_jobs_per_domain:
            # Crawl job finished prematurely
            logging.error("%s: has only %d jobs", domain, len(job_dir_list))
            continue

        for job_dir in job_dir_list:
            form_file_list = list(job_dir.glob("form-*.json"))

            if form_file_list:
                with open(job_dir / "job.json", "r", encoding="utf-8") as fin:
                    json.loads(fin.read())

                (job_dir / "page.html").stat()

            for form_file in form_file_list:
                form_count += 1

                with form_file.open("r", encoding="utf-8") as fin:
                    json.loads(fin.read())

        domain_list.add(domain)

    print("Total domains:", len(domain_list))
    print("Total forms:", form_count)

    # Copy the database to rootdir + ".db" for convenience
    target_db_path = args.rootdir.rstrip('/') + '.db'

    con2 = sqlite3.connect(target_db_path)

    for table in 'tranco_list', 'domain_info':
        cur = con.execute('SELECT sql FROM sqlite_master WHERE type = "table" AND name = ?', (table,))
        con2.execute(f'DROP TABLE IF EXISTS {table}')
        con2.execute(cur.fetchone()[0])

    con2.commit()
    con2.close()

    con.execute('ATTACH ? AS new_db', (target_db_path,))

    args = [(d,) for d in domain_list]
    con.executemany('INSERT INTO new_db.tranco_list SELECT * FROM tranco_list WHERE domain = ?', args)
    con.executemany('INSERT INTO new_db.domain_info SELECT * FROM domain_info WHERE domain = ?', args)

    con.commit()
    con.close()


if __name__ == '__main__':
    main()
