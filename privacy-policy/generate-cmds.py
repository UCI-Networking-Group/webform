import argparse
import hashlib
import os
import shlex
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rootdir")
    parser.add_argument("outdir")
    args = parser.parse_args()

    con = sqlite3.connect(args.rootdir.rstrip('/') + '.db')

    cur = con.execute('SELECT DISTINCT normalized_url FROM privacy_policy_link_normalized')
    all_urls = set(d for d, in cur)

    con.close()

    for privacy_policy_url in all_urls:
        url_black2s = hashlib.blake2s(privacy_policy_url.encode()).hexdigest()
        out_dir = os.path.join(args.outdir, url_black2s)
        cmd1 = shlex.join(["test", "-e", out_dir])
        cmd2 = shlex.join(["python3", "html_crawler.py", privacy_policy_url, out_dir, "--no-readability-js"])
        print(cmd1 + " || " + cmd2)

if __name__ == '__main__':
    main()
