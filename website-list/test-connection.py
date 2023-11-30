import requests
import langdetect
import dbm
import csv
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import urllib3


def test_domain(domain):
    info = {}
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
                content = req.text

                info['init_url'] = init_url
                info['final_url'] = req.url

            break
        except (requests.exceptions.RequestException, urllib3.exceptions.LocationParseError, OSError):
            pass

    if not content:
        return None

    soup = BeautifulSoup(content, 'lxml')
    html_lang = soup.html.get('lang') if soup.html else None

    if html_lang:
        info['lang'] = html_lang.lower()
    else:
        try:
            guess_lang = langdetect.detect(soup.text)
        except langdetect.lang_detect_exception.LangDetectException:
            guess_lang = 'unknown'

        info['lang'] = f'guess:{guess_lang}'

    return info


def main():
    with (open('cloudflare-domain-intel.csv', 'r', newline='') as fin,
          dbm.open('domain-connection-info.db', 'c') as db,
          ThreadPoolExecutor() as executor):
        domains = []

        for row in csv.DictReader(fin):
            if row['domain'].encode() not in db:
                domains.append(row['domain'])

        for domain, info in zip(domains, executor.map(test_domain, domains)):
            if info is not None:
                db[domain] = json.dumps(info)
                print(domain)
                print(info)


if __name__ == '__main__':
    main()
