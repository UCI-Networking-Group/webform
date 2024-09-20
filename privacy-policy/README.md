## Step 6: Privacy Policy Processing

### Step 6.1: Privacy Policy Link Extraction

Use `extract-links.py` to extract privacy policy links from web pages and forms in the web form dataset:

```console
$ python extract-links.py ~/webform-data --n_cpu 40 --n_gpu 8
100%|██████████| 10143/10143 [25:11<00:00, 6.71it/s]
```

Adjust the `--n_cpu` (number of parallel CPU workers) and `--n_gpu` (number of GPU workers) flags according to your available CPU cores and GPU memory size. Based on our estimates, each GPU worker requires about 1.2 GiB of GPU memory.

The results are saved in the `privacy_policy_link` table:

```console
$ sqlite3 -header ~/webform-data.db "SELECT * FROM privacy_policy_link ORDER BY RANDOM() LIMIT 1"
domain|job_hash|form_filename|scope|text|url
bestlifeonline.com|4b9e7de0f432c1cd725f21cf89ee5d89924f40d4bb05e3ae6088ce8d1120cb89|form-0.json|PAGE|Privacy Policy|https://bestlifeonline.com/privacy-policy/
```

Next, use `normalize_urls.py` to group URLs that likely point to the same page (e.g., URLs differing only by query strings, fragments, HTTP vs. HTTPs, etc.) and normalize them into a consistent format:

```console
$ python normalize_urls.py ~/webform-data
```

The results are saved in the `privacy_policy_link_normalized` table:

```console
$ sqlite3 -header ~/webform-data.db "SELECT * FROM privacy_policy_link JOIN privacy_policy_link_normalized USING (url) WHERE url != normalized_url ORDER BY RANDOM() LIMIT 1"
domain|job_hash|form_filename|scope|text|url|normalized_url
mention-me.com|ec42ac34dd1d96a5211013127cac97d31bbbb5da638b5dd0c084279765cf88eb|form-1.json|PAGE|Cookies|https://mention-me.com/help/privacy_policy_s#cookies|https://mention-me.com/help/privacy_policy_s
```

### Step 6.2: Downloading Privacy Policies

Use `html_crawler.py` to download a privacy policy and save it into a folder that can be processed by [PoliGraph-er](https://github.com/UCI-Networking-Group/PoliGraph):

```console
$ python html_crawler.py <URL> <OUTPUT_DIR>
```

Next, use `generate-crawler-cmds.py` to generate the crawler commands for all URLs in our database, and execute them to prepare the privacy policy dataset:

```console
$ python generate-crawler-cmds.py ~/webform-data ~/webform-privacy-policies > crawl.sh
$ bash crawl.sh
```

The prepared dataset in `~/webform-privacy-policies` will be ready for processing with PoliGraph-er:

```text
~/webform-privacy-policies
├── 0003b51906d92cfa16c21546a1f79bc440ed9e806e19b003e1c3d14b41dddb7d
│   ├── accessibility_tree.json
│   ├── cleaned.html
│   └── readability.json
└── ......
```

### Step 6.3: PoliGraph Generation

Follow [PoliGraph-er's documentation](https://github.com/UCI-Networking-Group/PoliGraph/blob/USENIX-AE-v1/README.md) to parse the privacy policies. The key steps are outlined below:

```console
$ cd PoliGraph
# To avoid dependency conflicts, run PoliGraph-er in its own environment
$ conda env create -n poligraph -f environment.yml
$ conda activate poligraph
$ tar xf /path/to/poligrapher-extra-data.tar.gz -C poligrapher/extra-data
$ pip install --editable .
# Run PoliGraph-er
$ python -m poligrapher.scripts.init_document ~/webform-privacy-policies/*
$ python -m poligrapher.scripts.run_annotators ~/webform-privacy-policies/*
$ python -m poligrapher.scripts.build_graph --variant extended ~/webform-privacy-policies/*
# Ensure you are in the webform environment before proceeding to the next steps
$ conda activate webform
```

### Step 6.4: Importing PoliGraph Results

Finally, read the PoliGraph results and import the necessary information (e.g., PI types disclosed to be collected) back into our database:

```console
$ python import-poligraph.py ~/webform-data ~/webform-privacy-policies
100%|██████████| 19031/19031 [01:16<00:00, 248.24it/s]
Domains with privacy policies downloaded: 9013
Domains with disclosures: 7553
```

The results are saved in the `privacy_policy_disclosures` table:

```console
$ sqlite3 -header ~/webform-data.db "SELECT * FROM privacy_policy_disclosures ORDER BY RANDOM() LIMIT 1"
url|disclosures
https://www.speedtest.net/about/privacy|{"Address":["advertising","services"],"BankAccountNumber":[],"EmailAddress":[],"Ethnicity":[],"PersonName":["advertising","services"],"PhoneNumber":["advertising","services"]}
```

### Artifacts

The processed privacy policy dataset (following Step 6.3) is provided in `privacy-policies.tar.zst` in the released artifacts. To restore the dataset:

```console
$ mkdir ~/webform-privacy-policies
$ tar xf privacy-policies.tar.zst -C ~/webform-privacy-policies
```

Our processing results, including the `privacy_policy_link`, `privacy_policy_link_normalized`, and `privacy_policy_disclosures` tables, can be found in the released results database (`webform-data.db`).
