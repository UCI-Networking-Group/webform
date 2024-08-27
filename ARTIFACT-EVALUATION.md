# Artifact Appendix

Paper title: Understanding Privacy Norms through Web Forms

Artifacts HotCRP Id: **#Enter your HotCRP Id here** (not your paper Id, but the artifacts id)

Requested Badge: Available, Functional, Reproduced

## Description

Our artifact submission includes the code, datasets, pre-trained machine learning classifiers, and analysis results associated with our web form measurement study.

### Security/Privacy Issues and Ethical Concerns (All badges)

**Web Crawling:** The artifacts include web crawler code. Inappropriate use of crawlers (e.g., without rate limits) can harm the reputation of your IP address. We recommend that reviewers test the functionality on a small number of websites only.

**Sensitive Content:** We release the raw web form dataset as is. The text files and screenshots in the dataset may contain sensitive content (e.g., adult or fraudulent material) from certain websites. Please keep this in mind if you choose to browse files in the dataset.

## Basic Requirements (Only for Functional and Reproduced badges)

### Hardware Requirements

We tested all the code on a server with the following configuration (reference hardware):

- CPU: Intel Xeon Silver 4316 (2 sockets x 20 cores x 2 threads)
- Memory: 512 GiB
- GPU: 2x NVIDIA RTX A5000 (24 GiB of video memory each)
- Storage: SSD RAID arrays, with TBs of free space

Given the significant GPU and storage demands, we will provide reviewers with anonymous SSH access to the reference hardware for artifact evaluation. We will post login details on the HotCRP website.

If you choose to use your own hardware, please refer to [README.md](./README.md) for the minimum system requirements.

### Software Requirements

We tested all the code in the following software environment:

- OS: Debian GNU/Linux 12 (bookworm)
- NVIDIA driver: version 545.23.08
- Conda: version 24.5.0

### Estimated Time and Storage Consumption

On the reference hardware, the evaluation takes 2-3 hours of runtime. We have implemented progress bars and time estimates for commands that may take a long time.

If you choose to use your own hardware, please refer to [README.md](./README.md) for storage requirements.

## Environment

### Accessibility (All badges)

- Codebase: <https://github.com/UCI-Networking-Group/webform/tree/PoPETs-AE-v1>
- Associated Artifacts: <https://athinagroup.eng.uci.edu/projects/auditing-and-policy-analysis/webform-artifacts/>

### Setting Up the Environment (Only for Functional and Reproduced badges)

> **To artifact reviewers:** If you use our hardware, we have already set up the environment, including populating the directories described below. Please proceed to "Artifact Evaluation".

We assume the following directory paths in this document:

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

To populate `~/webform-data`, download `crawl-merged-core.tar.xz` from the associated artifacts and decompress it (~20 minutes runtime):

```sh
mkdir ~/webform-data
tar xf crawl-merged-core.tar.xz -C ~/webform-data
```

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

To populate `~/webform-db`, download `domain.db.xz` and `webform-data.db.xz` and decompress them:

```sh
mkdir ~/webform-db
xzcat domain.db.xz > ~/webform-db/domain.db
xzcat webform-data.db.xz > ~/webform-db/webform-data.db
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

### Testing the Environment (Only for Functional and Reproduced badges)

Run `env-test.sh` to check if all the necessary library dependencies have been installed (~1 minute runtime):

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

If you would like to more details about the steps, please refer to [the main README](./README.md) and README files in each folder.

#### Experiment 1: Web Form Dataset (Verification Only)

In this experiment, we illusrate the usage of the web form crawler and how we generated the web form dataset.

**(E1.1 -- Web Form Crawler)** To crawl web pages and forms on a website (e.g., `http://facebook.com/`), run (~1 minute runtime):

```console
$ node crawler/build/crawler.js crawler-test_facebook.com/ http://facebook.com/ --maxJobCount 4
# Run time: < 1 minute (depending on network conditions)
```

Here, `crawler-test_facebook.com/` is the output directory, and `--maxJobCount 4` instructs the crawler to stop after 4 crawl tasks.

The output directory has the following structure (the names of subfolders may vary):

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

It is infeasible to fully reproduce the crawling process. We released our crawls of 11,500 websites as part of the associated artifacts (`~/webform-data`).

**(E1.2 -- Website List and Domain Categorization)** We use scripts under `./website-list` to download popular website lists and obtain domain categorization data. It is infeasible to reproduce these steps exactly due to the dependency on commercial APIs (see [website-list/README.md](./website-list/README.md) for details). We provide the data in a SQLite3 database (`~/webform-db/domain.db`) in the associated artifacts. You can verify its content as shown below.

To get the Tranco rank of a domain (e.g., `chase.com`), which was obtained from [Tranco List version 82NJV](https://tranco-list.eu/list/82NJV/full):

```console
$ sqlite3 -header ~/webform-db/domain.db "SELECT * FROM tranco_list WHERE domain = 'chase.com'"
ranking|domain
2565|chase.com
```

To get domain categorization information, which should match the information on [Cloudflare Radar](https://radar.cloudflare.com/domains/domain/chase.com):

```console
$ sqlite3 -header ~/webform-db/domain.db "SELECT * FROM domain_info WHERE domain = 'chase.com'"
domain|application|content_categories|additional_information|type|notes
chase.com|{"id":786,"name":"Chase Bank (Do Not Inspect)"}|[{"id":89,"super_category_id":3,"name":"Economy & Finance"},{"id":3,"name":"Business & Economy"}]|{}|Apex domain|Apex domain given.
```

To get a list of candidate `<domain, URL>` pairs as input arguments for the crawler:

```console
$ python website-list/filter-websites.py ~/webform-db/domain.db
google.com http://google.com
facebook.com http://facebook.com
microsoft.com http://microsoft.com
......
```

We built the raw web form dataset (`~/webform-data`) by running the crawler over this list.

#### Experiment 2: Dataset Annotation Pipeline

In this experiment, we repeat the exact web form dataset annotation pipeline in the paper.

**(E2.1 -- Validating the Web Form Dataset)** Run the following command (~3 minutes runtime):

```console
$ python preprocessing/validate.py ~/webform-db/domain.db ~/webform-data
100%|██████████| 11500/11500 [02:34<00:00, 74.35it/s]
Total domains: 11500
Total forms: 938324
```

This generates `~/webform-data.db`, a SQLite3 database file that will be used by the following steps to store results.

**(E2.2 -- Identifying Web Page Languages)** Run the following command (~15 minutes runtime):

```console
$ python preprocessing/check-webpage-language.py ~/webform-data
100%|██████████| 1149999/1150000 [14:41<00:00, 1304.97it/s]
```

See [preprocessing/README.md](./preprocessing/README.md) for more details on E2.1 and E2.2.

**(E2.3 -- PI Type Classification)** Use our pre-trained classifier (`~/webform-classifiers/pi-type`) to identify the PI types collected in each web form. This involves three commands (~50 minutes runtime in total):

```console
$ python pi-type-classification/extract-features.py ~/webform-data pi-unlabeled.jsonl
100%|██████████| 970644/970644 [04:36<00:00, 3506.68it/s]
$ python pi-type-classification/prelabel-model.py pi-unlabeled.jsonl ~/webform-classifiers/pi-type/ pi-labeled.jsonl
774477it [40:12, 320.98it/s]
$ python pi-type-classification/import-classification.py -i pi-labeled.jsonl ~/webform-data
100%|██████████| 970644/970644 [04:37<00:00, 3493.70it/s]
```

The results are saved in the `field_classification` table in `~/webform-data.db`:

```console
$ sqlite3 -header ~/webform-data.db 'SELECT * FROM field_classification ORDER BY RANDOM() LIMIT 3'
domain|job_hash|form_filename|field_list
primus.ca|24771f1319126c41765064260e83614ae9121b689fc16dd9047a63439f402466|form-0.json|["PhoneNumber", "PhoneNumber", "PostalCode"]
squarespace.com|52b8a1127937903c9223687b3b9a4a9278ade734d45648e1978ddfab32604321|form-0.json|["EmailAddress", "Password"]
arin.net|6c135bee885e61ac64e875577425cad9de2119a2f79bc5d659977292d78766d4|form-0.json|["EmailAddress"]
```

See [pi-type-classification/README.md](./pi-type-classification/README.md) for more details on classifier training and the usage of each script.

**(E2.4 -- Form Type Classification)** Use our pre-trained classifier (`~/webform-classifiers/form-type`) to identify the form types (~40 minutes runtime):

```console
$ python form-type-classification/classify.py ~/webform-classifiers/form-type ~/webform-data
Generating train split: 292655 examples [00:00, 460072.68 examples/s]
Map (num_proc=32): 100%|██████████| 292655/292655 [00:47<00:00, 6185.46 examples/s]
100%|██████████| 292655/292655 [35:46<00:00, 136.33it/s]
```

The results are saved in the `form_classification` table in `~/webform-data.db`:

```console
$ sqlite3 -header ~/webform-data.db 'SELECT * FROM form_classification ORDER BY RANDOM() LIMIT 1'
domain|job_hash|form_filename|form_type|scores
tolstoycomments.com|461510895ba486d821dd280b5bfe5999fe2f076f9ee72320b48e167f928b9187|form-0.json|Account Registration Form|...
```

See [form-type-classification/README.md](./form-type-classification/README.md) for more details on classifier training.

At this point, `~/webform-data.db` is the _annotated web form dataset_ described in the paper.

#### Experiment 3: Web Form Analysis

After completing Experiment 2, use [analysis/web-form-analysis.ipynb](./analysis/web-form-analysis.ipynb), a Jupyter notebook, to generate plots and statistics related to Section 5.

The only input required is the annotated dataset `~/webform-data.db`. If the database is in a different path, please adjust the path in Cell 2 accordingly.

> **To artifact reviewers:** If you are using our machine so far, there are two options to run the notebook. See below.

**(E3a)** To run the notebook directly on our machine, you can enable SSH port forward and start Jupyter Lab on it.

On your local machine, enable SSH port forwarding. If you use OpenSSH client, use the `-L` option when you log in:

```console
$ ssh -L 8888:localhost:8888 <username>@<hostname>
```

You can change `8888` to any available port. In the SSH session, start Jupyter Lab with the same port:

```console
$ conda activate webform
$ cd ~/webform-code
# Make a copy of the notebooks to avoid conflicts with other reviewers
$ cp -r analysis analysis-reviewer1
$ jupyter lab --no-browser --port=8888 analysis-reviewer1
```

Then, open the URL printed in the console in your local browser.

**(E3b)** Alternatively, you can copy the notebook and `~/webform-data.db` to your local machine and run it locally. Only a few Python dependencies are required:

```console
$ pip install scipy pandas seaborn matplotlib matplotlib-inline  # or conda install
$ jupyter lab
```

#### Experiment 4: Privacy Policy Analysis

**(E4.1 -- Privacy Policy Link Extraction)** Run the following two scripts to extract privacy policy links from the web form dataset (~25 minutes runtime in total):

```console
$ python privacy-policy/extract-links.py ~/webform-data --n_cpu 40 --n_gpu 4
100%|██████████| 10143/10143 [25:11<00:00,  6.71it/s]
$ python privacy-policy/normalize_urls.py ~/webform-data
```

If you use your own machine, please adjust `--n_cpu` (number of parallel CPU workers) and `--n_gpu` (number of GPU workers) according to your available CPU cores and GPU memory size.

**(E4.2 -- Processing Privacy Policies)** The next step is to download privacy policies and run PoliGraph-er to parse them. Due to the infeasibility of repeating the web crawling process, we provided a processed privacy policy dataset (`~/webform-privacy-policies`) as part of the associated artifacts. Please refer to [privacy-policy/README.md](./privacy-policy/README.md) to understand how these files were generated.

After processing the privacy policies, parse the generated PoliGraphs and import disclosures of collected PI types into the database (~1 minute runtime):

```console
$ python privacy-policy/import-poligraph.py ~/webform-data ~/webform-privacy-policies
100%|██████████| 19031/19031 [01:16<00:00, 248.24it/s]
Domains with privacy policies downloaded: 9013
Domains with disclosures: 7553
```

**(E4.3 -- Privacy Policy Analysis)** Finally, use [analysis/privacy-policy-analysis.ipynb](./analysis/privacy-policy-analysis.ipynb) to generate tables, plots, and other statistics in Section 6 of our paper. Follow the same instructions as in Experiment 3 to run the Jupyter notebook.

## Limitations (Only for Functional and Reproduced badges)

Due to the prohibitive runtime and the dynamic nature of web pages, it is infeasible to repeat the web crawling process and reproduce the exact dataset. However, we provide the relevant code and artifacts required for reproducibility.

Due to the manual work and long runtime involved, we do not ask reviewers to train the classifiers. We provide the relevant code and pre-trained classifiers.

## Notes on Reusability (Only for Functional and Reproduced badges)

We have strived to make the code modular and generalizable to new data. For example, our web form crawler, pre-trained form type and PI type classifiers, and scripts to extract privacy policy links can be easily reused in new research projects.

We provide [detailed documentation](./README.md) for our artifacts.
