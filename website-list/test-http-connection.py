from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3
import sqlite3
import argparse
import tldextract
from urllib.parse import urlsplit
from langutil import check_html_language


def test_domain(domain):
    info = {'domain': domain}
    content = None
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept-Language': 'en-us,en;q=0.5',
    }

    for real_domain in domain, "www." + domain:
        try:
            init_url = f"http://{real_domain}"

            with requests.get(init_url, headers=headers, timeout=10, stream=True) as req:
                if req.raw._connection.sock:
                    ip, _ = req.raw._connection.sock.getpeername()
                    info['ip'] = ip
                else:
                    continue

                if not req.headers.get('Content-Type', '').startswith('text/html;'):
                    continue

                req.raise_for_status()
                content = req.content
                redirected_url = req.url

                info['url'] = init_url
                info['redirected_url'] = urlsplit(redirected_url, allow_fragments=False)._replace(query='').geturl()
                info['domain_has_changed'] = tldextract.extract(redirected_url).registered_domain != domain
                info['redirected_url'] = req.url

            break
        except (requests.exceptions.RequestException, urllib3.exceptions.LocationParseError, OSError):
            pass

    if not content:
        return None

    info['lang'] = check_html_language(req.content)

    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", help="SQLite database path")
    args = parser.parse_args()

    con = sqlite3.connect(args.database)
    con.execute('''CREATE TABLE IF NOT EXISTS http_info (
        domain TEXT UNIQUE NOT NULL,
        ip TEXT,
        url TEXT,
        redirected_url TEXT,
        lang TEXT,
        domain_has_changed INTEGER
    ) STRICT''')

    domains_to_check = []

    for domain, in con.execute('''
        SELECT domain
        FROM tranco_list t
        WHERE NOT EXISTS(SELECT NULL FROM http_info h WHERE t.domain = h.domain)
        ORDER BY t.ranking
    '''):
        domains_to_check.append(domain)

    with ThreadPoolExecutor() as executor:
        for domain, info in zip(domains_to_check, executor.map(test_domain, domains_to_check)):
            if info is not None:
                con.execute('''
                    INSERT INTO http_info
                    VALUES (:domain, :ip, :url, :redirected_url, :lang, :domain_has_changed)
                ''', info)
                con.commit()
                print(domain)


if __name__ == '__main__':
    main()
