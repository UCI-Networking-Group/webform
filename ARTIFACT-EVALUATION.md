# Artifact Appendix

Paper title: Understanding Privacy Norms through Web Forms

Artifacts HotCRP Id: 1

Requested Badge: Available, Functional, Reproduced

## Description

Our artifact submission includes the code, datasets, pre-trained machine learning classifiers, and analysis results associated with our web form measurement study.

For artifact evaluation, we provide steps to reproduce our experiments on a small number of websites (_AE experiments_) so it can be done in a reasonable amount of time. The reviewers can verify that our full results were generated through the same process.

If you would like to run the full experiments, as we did in the paper, please refer to [the main README](./README.md).

### Security/Privacy Issues and Ethical Concerns (All badges)

**Web Crawling:** The artifacts include web crawler code. Inappropriate use of crawlers (e.g., without rate limits) can harm the reputation of your IP address. We recommend that reviewers test the functionality on a few websites only.

**Sensitive Content:** We release the raw web form dataset as is. The text files and screenshots in the dataset may contain sensitive content (e.g., adult or fraudulent material) from certain websites. Please keep this in mind if you choose to browse files in the dataset.

## Basic Requirements (Only for Functional and Reproduced badges)

### Hardware Requirements

To run the AE experiments, we recommend using either:

- a Linux computer that has an NVIDIA GPU with at least 8 GiB of memory and CUDA 12.1 support;
- or, a recent Mac computer with Apple silicon and [MPS](https://developer.apple.com/metal/pytorch/) support.

While it is possible to run the experiments without any GPU accelerators, the performance would be significantly lower in certain steps.

### Software Requirements

We tested all the code in the following software environments:

- Linux computer:
  - OS: Debian GNU/Linux 12 (bookworm)
  - NVIDIA driver: version 545.23.08
  - Conda: version 24.5.0
- Mac computer:
  - OS: macOS 14.6
  - Conda: version 24.5.0

### Estimated Time and Storage Consumption

On a 2020 MacBook Pro with M1 chip, the AE experiments take about 15 minutes.

The scaled-down experiments require about 25 GiB of disk space, including:

- about 5 GiB used to store downloaded associated artifacts;
- about 10 GiB used for extracted data and any intermediate results generated;
- about 10 GiB for dependencies installed by conda.

If you would like to run the full experiments, please refer to the main README for details.

## Environment

### Accessibility (All badges)

- Main codebase: <https://github.com/UCI-Networking-Group/webform/tree/PoPETs-AE-v1>
- Associated Artifacts: <https://athinagroup.eng.uci.edu/projects/auditing-and-policy-analysis/webform-artifacts/>

### Setting Up the Environment (Only for Functional and Reproduced badges)

We assume the following paths in this document:

- `~/webform-code` -- This repository
- `~/webform-data` -- Raw web form dataset
- `~/webform-privacy-policies` -- Privacy policy dataset
- `~/webform-classifiers/pi-type` -- Model files for the PI type classifier
- `~/webform-classifiers/form-type` -- Model files for the form type classifier
- `~/webform-db` -- Already generated databases containing data processing results

Our scripts are path-independent. If you use different paths, please adjust the arguments passed to the scripts accordingly.

To populate `~/webform-code`, clone this git repository:

```sh
git clone https://github.com/UCI-Networking-Group/webform.git ~/webform-code
cd ~/webform-code
git submodule init
git submodule update
```

To populate `~/webform-db`, download `domain.db.xz` and `webform-data.db.xz` from the associated artifacts and decompress them:

```sh
mkdir ~/webform-db
xzcat domain.db.xz > ~/webform-db/domain.db
xzcat webform-data.db.xz > ~/webform-db/webform-data.db
```

To populate `~/webform-data`, download `crawl-merged-core.tar.xz`. It contains the full crawled data from 11,500 websites. In the AE experiments, we only use the top 100 websites as shown below:

```sh
mkdir ~/webform-data
sqlite3 ~/webform-db/webform-data.db 'SELECT domain FROM tranco_list ORDER BY ranking LIMIT 100' > domain_list
tar xf crawl-merged-core.tar.xz -C webform-data/ -T domain_list
```

The file `domain_list` contains a list of domains to be extracted from the tarball. You may adjust the list or the SQL query to get a different set of domains to evaluate.

To populate `~/webform-classifiers/pi-type` and `~/webform-classifiers/form-type`, download `classifier-pi-type.tar.xz` and `classifier-form-type.tar.xz` and decompress them:

```sh
mkdir -p ~/webform-classifiers/pi-type
tar xf classifier-pi-type.tar.xz -C ~/webform-classifiers/pi-type
mkdir -p ~/webform-classifiers/form-type
tar xf classifier-form-type.tar.xz -C ~/webform-classifiers/form-type
```

To populate `~/webform-privacy-policies`, download `privacy-policies.tar.xz` and decompress it:

```sh
mkdir ~/webform-privacy-policies
tar xf privacy-policies.tar.xz -C ~/webform-privacy-policies
```

Then, install [conda](https://conda.io/projects/conda/en/latest/user-guide/install/linux.html) and set up the software environment as follows:

```sh
# Set up conda environment
cd ~/webform-code
conda env create -n webform -f environment.yml
conda activate webform
pip install -e privacy-policy/PoliGraph/
# Set up NodeJS environment for the web form crawler
cd crawler/
npm install
npm run compile
npx playwright install
npx playwright install-deps
```

If you use macOS arm64, please use `environment-macos-arm64.yml` to create the conda environment in the second command.

### Testing the Environment (Only for Functional and Reproduced badges)

Run `env-test.sh` to check if all the necessary library dependencies have been installed:

```console
$ bash ~/webform-code/env-test.sh
Checking form-type-classification/al_select.py...
Checking form-type-classification/al_test_check.py...
Checking form-type-classification/al_test_select.py...
......
Done!
```

If you see `Done!` after several `Checking ...` messages, the setup is successful.

## Artifact Evaluation (Only for Functional and Reproduced badges)

### Main Results and Claims

#### Main Result 1: Creation of the Web Form Dataset

In Section 3, we present our web form crawler and the raw web form dataset. We also discuss our methodology for website selection.

We will illustrate how these were done in Experiment 1.

#### Main Result 2: Dataset Annotation Pipeline

In Section 4, we describe our data annotation methodology. In particular, we use NLP classifiers to identify form types (Section 4.1) and PI types (Section 4.2) collected in the web forms.

We will reproduce these steps in Experiment 2.

#### Main Result 3: Web Form Analysis

In Section 5, we discuss the patterns of PI collection revealed in the web form dataset. Main results include:

- Statistics of form types and PI types (Section 4.3 -- Table 4)
- Collection rates of various PI types (Section 5.1 -- Figures 4 and 5)
- Analysis of uncommon cases of PI collection (Section 5.2)

We will reproduce these results in Experiment 3.

#### Main Result 4: Privacy Policy Analysis

In Section 6, we discuss the patterns of disclosed PI collection in privacy policies and compare these patterns with web forms to reveal the disconnect between privacy policies and observed privacy norms. Main results include:

- Statistics of privacy policy availability (Section 6.1 -- Tables 5 and 6)
- Patterns of disclosed PI collection by website category (Section 6.2 -- Figure 6)
- Association between privacy policy disclosures and observed PI collection (Section 6.2 -- Table 7)

We will reproduce these results in Experiment 4.

### Experiments

In this section, we provide step-by-step instructions to evaluate our artifacts, test code functionality, and reproduce our main results.

All scripts should be run in the conda environment that we set up (i.e., `webform`). We also assume that commands are executed in the root folder of this repository (i.e., `~/webform-code`):

```sh
conda activate webform
cd ~/webform-code
# Commands to run...
```

If you would like more details about each experiment, please refer to [the main README](./README.md) and README files in each subfolder.

#### Experiment 1: Web Form Dataset

In this experiment, we illustrate the usage of the web form crawler and how we generated the web form dataset.

**(E1.1 -- Web Form Crawler)** To crawl web pages and forms on a website (e.g., `http://facebook.com/`), run:

```console
$ node crawler/build/crawler.js crawler-test_facebook.com/ http://facebook.com/ --maxJobCount 4
# Run time: < 1 minute (depending on network conditions)
```

Here, `crawler-test_facebook.com/` is the output directory, and `--maxJobCount 4` instructs the crawler to stop after 4 crawl tasks.

The output directory has the following structure (the subfolder names may vary):

```console
$ tree crawler-test_facebook.com/
crawler-test_facebook.com/
├── 084c5e1720078e46743bce3587c8f40eae6f666c16f3e2a70fa60773e323cae8
│   ├── form-0.json
│   ├── job.json
│   ├── page.html
│   └── ......
├── 265fb2b4018ea1fb4a7a8342b9af90fdf5a88783b009cb22e043d70f75e3a445
│   └── ......
├── 381d1b37045743b6cd78a2142b8377c97e9a6ef1a62beb0a6ac321b7409e6d6b
│   └── ......
└── d96a4bb8f2d33a68c55a6f6e7f43464e2ca9036f60fcda3a682699161fcade7d
    └── ......
```

Each hex-named subfolder corresponds to a crawl task. The `job.json` file contains metadata for the crawl task (page title, navigation history, etc.), `form-*.json` files store information about web forms, and `page.html` contains the HTML code of the entire web page. See [crawler/README.md](./crawler/README.md) for details.

It is infeasible to reproduce the crawling process. We released our crawls of 11,500 websites as part of the associated artifacts (`crawl-merged-core.tar.xz`). You can verify that subfolders in `~/webform-data` have the same structure.

**(E1.2 -- Website List and Domain Categorization)** We use scripts under `./website-list` to download the Tranco list and obtain domain categorization data. It is infeasible to reproduce these steps exactly due to the dependency on commercial APIs (see [website-list/README.md](./website-list/README.md) for details). We provide the data in a SQLite3 database (`~/webform-db/domain.db`) in the associated artifacts. You can verify its content as shown below.

To get the Tranco rank of a domain (e.g., `forbes.com`), which was obtained from [Tranco List version 82NJV](https://tranco-list.eu/list/82NJV/full):

```console
$ sqlite3 ~/webform-db/domain.db "SELECT domain, ranking FROM tranco_list WHERE domain = 'forbes.com'"
forbes.com|183
```

To get domain categorization information, which should match the information on [Cloudflare Radar](https://radar.cloudflare.com/domains/domain/forbes.com):

```console
$ sqlite3 ~/webform-db/domain.db "SELECT content_categories FROM domain_info WHERE domain = 'forbes.com'"
[{"id":89,"super_category_id":3,"name":"Economy & Finance"},{"id":3,"name":"Business & Economy"},{"id":116,"super_category_id":7,"name":"Magazines"},{"id":7,"name":"Entertainment"}]
```

To get a list of candidate `<domain, URL>` pairs as input arguments for the crawler:

```console
$ python website-list/filter-websites.py ~/webform-db/domain.db
google.com http://google.com
facebook.com http://facebook.com
microsoft.com http://microsoft.com
......
```

We built the raw web form dataset (`crawl-merged-core.tar.xz`) by running the crawler over this list.

#### Experiment 2: Dataset Annotation Pipeline

In this experiment, we repeat the exact web form dataset annotation pipeline described in the paper.

**(E2.1 -- Validating the Web Form Dataset)** Run the following command:

```console
$ python preprocessing/validate.py ~/webform-db/domain.db ~/webform-data
100%|██████████| 100/100 [00:02<00:00, 39.21it/s]
Total domains: 100
Total forms: 8095
```

This generates `~/webform-data.db`, a SQLite3 database file that will be used by the following steps to store results.

In the AE experiments, we only use 100 websites. We provide the full version in `~/webform-db/webform-data.db`, which contains results from 11,500 websites.

**(E2.2 -- Identifying Web Page Languages)** Run the following command:

```console
$ python preprocessing/check-webpage-language.py ~/webform-data
100%|██████████| 9999/10000 [00:30<00:00, 326.51it/s]
```

See [preprocessing/README.md](./preprocessing/README.md) for more details on E2.1 and E2.2.

**(E2.3 -- PI Type Classification)** Use our pre-trained classifier (`~/webform-classifiers/pi-type`) to identify the PI types collected in each web form. This involves three commands:

```console
$ python pi-type-classification/extract-features.py ~/webform-data pi-unlabeled.jsonl
100%|██████████| 8247/8247 [00:04<00:00, 1828.10it/s]
$ python pi-type-classification/prelabel-model.py pi-unlabeled.jsonl ~/webform-classifiers/pi-type/ pi-labeled.jsonl
13095it [00:53, 245.64it/s]
$ python pi-type-classification/import-classification.py -i pi-labeled.jsonl ~/webform-data
100%|██████████| 8247/8247 [00:05<00:00, 1417.44it/s]
```

The results are saved in the `field_classification` table in `~/webform-data.db`:

```console
$ sqlite3 ~/webform-data.db "SELECT * FROM field_classification WHERE domain = 'forbes.com' ORDER BY job_hash, form_filename"
forbes.com|1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-1.json|["PersonName", "PersonName", "EmailAddress", "PhoneNumber", "Fingerprints"]
forbes.com|1cb4b7c21334fa904cc36112a0cf6c3e6aa1d4d0b7f49ab586560ed8e5b28122|form-0.json|["EmailAddress"]
forbes.com|23c287ae6ef19aba1c0260c90bd095a2a288eff6989ff21b37de8f01cafb4226|form-1.json|["EmailAddress"]
......
```

See [pi-type-classification/README.md](./pi-type-classification/README.md) for more details on classifier training and the usage of each script.

**(E2.4 -- Form Type Classification)** Use our pre-trained classifier (`~/webform-classifiers/form-type`) to identify the form types:

```console
$ python form-type-classification/classify.py ~/webform-classifiers/form-type ~/webform-data
Generating train split: 2465 examples [00:00, 80507.70 examples/s]
Map (num_proc=16): 100%|██████████| 2465/2465 [00:00<00:00, 4395.48 examples/s]
100%|██████████| 2465/2465 [04:43<00:00,  8.69it/s]
```

The results are saved in the `form_classification` table in `~/webform-data.db`:

```console
$ sqlite3 ~/webform-data.db "SELECT job_hash, form_filename, form_type FROM form_classification WHERE domain = 'forbes.com' ORDER BY job_hash, form_filename"
1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-1.json|Contact Form
1cb4b7c21334fa904cc36112a0cf6c3e6aa1d4d0b7f49ab586560ed8e5b28122|form-0.json|Account Login Form
23c287ae6ef19aba1c0260c90bd095a2a288eff6989ff21b37de8f01cafb4226|form-1.json|Account Login Form
......
```

See [form-type-classification/README.md](./form-type-classification/README.md) for more details on classifier training.

At this point, `~/webform-data.db` is the _annotated web form dataset_ described in the paper.

To confirm reproducibility, verify that `~/webform-db/webform-data.db` has exactly the same results:

```console
$ sqlite3 ~/webform-db/webform-data.db "SELECT * FROM field_classification WHERE domain = 'forbes.com' ORDER BY job_hash, form_filename"
forbes.com|1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-1.json|["PersonName", "PersonName", "EmailAddress", "PhoneNumber", "Fingerprints"]
forbes.com|1cb4b7c21334fa904cc36112a0cf6c3e6aa1d4d0b7f49ab586560ed8e5b28122|form-0.json|["EmailAddress"]
forbes.com|23c287ae6ef19aba1c0260c90bd095a2a288eff6989ff21b37de8f01cafb4226|form-1.json|["EmailAddress"]
......
$ sqlite3 ~/webform-db/webform-data.db "SELECT job_hash, form_filename, form_type FROM form_classification WHERE domain = 'forbes.com' ORDER BY job_hash, form_filename"
1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-1.json|Contact Form
1cb4b7c21334fa904cc36112a0cf6c3e6aa1d4d0b7f49ab586560ed8e5b28122|form-0.json|Account Login Form
23c287ae6ef19aba1c0260c90bd095a2a288eff6989ff21b37de8f01cafb4226|form-1.json|Account Login Form
......
```

#### Experiment 3: Web Form Analysis

After completing Experiment 2, use [analysis/web-form-analysis.ipynb](./analysis/web-form-analysis.ipynb), a Jupyter notebook, to generate plots and statistics related to Section 5.

The AE experiments only used 100 websites, which are not sufficient for analysis. Please change the path in Cell 2 from `~/webform-data.db` to `~/webform-db/webform-data.db` to use the full version of the annotated datasets.

#### Experiment 4: Privacy Policy Analysis

**(E4.1 -- Privacy Policy Link Extraction)** Run the following two scripts to extract privacy policy links from the web form dataset:

```console
$ python privacy-policy/extract-links.py ~/webform-data
100%|██████████| 91/91 [03:08<00:00,  2.07s/it]
$ python privacy-policy/normalize_urls.py ~/webform-data
```

The results are saved in the `privacy_policy_link` and `privacy_policy_link_normalized` tables in `~/webform-data.db`:

```console
$ sqlite3 ~/webform-data.db "SELECT job_hash, form_filename, scope, normalized_url FROM privacy_policy_link JOIN privacy_policy_link_normalized USING (url) WHERE domain = 'forbes.com' ORDER BY job_hash, form_filename"
1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-0.json|PAGE|https://councils.forbes.com/privacy-policy
1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-1.json|FORM|https://councils.forbes.com/privacy-policy
1cb4b7c21334fa904cc36112a0cf6c3e6aa1d4d0b7f49ab586560ed8e5b28122|form-0.json|PAGE|https://www.forbes.com/fdc/privacy.html
......
```

**(E4.2 -- Processing Privacy Policies)** The next step is to download privacy policies and run PoliGraph-er to parse them. Due to the infeasibility of repeating the web crawling process, we provided a processed privacy policy dataset (`~/webform-privacy-policies`) as part of the associated artifacts. Please refer to [privacy-policy/README.md](./privacy-policy/README.md) to understand how these files were generated.

After processing the privacy policies, parse the generated PoliGraphs and import disclosures of collected PI types into the database:

```console
$ python privacy-policy/import-poligraph.py ~/webform-data ~/webform-privacy-policies
100%|██████████| 227/227 [00:01<00:00, 196.01it/s]
Domains with privacy policies downloaded: 83
Domains with disclosures: 76
```

```console
$ sqlite3 ~/webform-data.db "SELECT disclosures FROM privacy_policy_disclosures WHERE url = 'https://councils.forbes.com/privacy-policy'"
{"Address":[],"EmailAddress":[],"PersonName":[],"PhoneNumber":[]}
```

To confirm reproducibility, verify that `~/webform-db/webform-data.db` has exactly the same results:

```console
$ sqlite3 ~/webform-db/webform-data.db "SELECT job_hash, form_filename, scope, normalized_url FROM privacy_policy_link JOIN privacy_policy_link_normalized USING (url) WHERE domain = 'forbes.com' ORDER BY job_hash, form_filename"
1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-0.json|PAGE|https://councils.forbes.com/privacy-policy
1750265e61ab242b45235c4ab17679f7968a5f489d9c9f0dc978c758c5006dae|form-1.json|FORM|https://councils.forbes.com/privacy-policy
1cb4b7c21334fa904cc36112a0cf6c3e6aa1d4d0b7f49ab586560ed8e5b28122|form-0.json|PAGE|https://www.forbes.com/fdc/privacy.html
......
$ sqlite3 ~/webform-db/webform-data.db "SELECT disclosures FROM privacy_policy_disclosures WHERE url = 'https://councils.forbes.com/privacy-policy'"
{"Address":[],"EmailAddress":[],"PersonName":[],"PhoneNumber":[]}
```

**(E4.3 -- Privacy Policy Analysis)** Finally, use [analysis/privacy-policy-analysis.ipynb](./analysis/privacy-policy-analysis.ipynb) to generate tables, plots, and other statistics in Section 6 of our paper. Similar to Experiment 3, please change the path in Cell 2 from `~/webform-data.db` to `~/webform-db/webform-data.db` to use the full dataset.

## Limitations (Only for Functional and Reproduced badges)

Due to the prohibitive runtime and the dynamic nature of web pages, it is infeasible to repeat the web crawling process and reproduce the exact dataset. However, we provide the relevant code and artifacts required for reproducibility.

Due to the manual work and long runtime involved, we do not ask reviewers to train the classifiers. We provide the relevant code and pre-trained classifiers.

## Notes on Reusability (Only for Functional and Reproduced badges)

We have strived to make the code modular and generalizable to new data. For example, our web form crawler, pre-trained form type and PI type classifiers, and scripts to extract privacy policy links can be easily reused in new research projects.

We provide [detailed documentation](./README.md) for our artifacts.
