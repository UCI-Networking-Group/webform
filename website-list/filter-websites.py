import argparse
import json
import os
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", help="SQLite database path")
    args = parser.parse_args()

    con = sqlite3.connect(args.database)
    cur = con.execute('''
    SELECT t.domain, application, content_categories, url
    FROM tranco_list t
         JOIN domain_info d ON t.domain = d.domain
         JOIN http_info h ON t.domain = h.domain
    WHERE lang IN ('en', 'guess:en', NULL)
          AND type = 'Apex domain'
          AND additional_information->'suspected_malware_family' IS NULL
          AND domain_has_changed = 0
    ORDER BY ranking;
    ''')

    blocked_categories = {'CIPA', 'Adult Themes', 'Questionable Content', 'Blocked'}
    visited_applications = set()

    for domain, application_json, content_categories_json, url in cur:
        application = json.loads(application_json)
        content_categories = json.loads(content_categories_json)

        if not blocked_categories.isdisjoint(i['name'] for i in content_categories):
            continue

        if application:
            if application['name'] in visited_applications:
                continue

            visited_applications.add(application['name'])

        print(domain, url)

if __name__ == '__main__':
    main()
