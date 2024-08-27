# Understanding Privacy Norms through Web Forms

> Web forms are one of the primary ways to collect personal information (PI) online, yet they are relatively under-studied. Unlike web tracking, data collection through web forms is explicit and contextualized. Users (i) are asked to input specific personal information types, and (ii) know the specific context (i.e., on which website and for what purpose). For web forms to be trusted by users, they must meet the common sense standards of appropriate data collection practices within a particular context (i.e., privacy norms). In this paper, we extract the privacy norms embedded within web forms through a measurement study. First, we build a specialized crawler to discover web forms on websites. We run it on 11,500 popular websites, and we create a dataset of 293K web forms. Second, to process data of this scale, we develop a cost-efficient way to annotate web forms with form types and personal information types, using text classifiers trained with assistance of large language models (LLMs). Third, by analyzing the annotated dataset, we reveal common patterns of data collection practices. We find that (i) these patterns are explained by functional necessities and legal obligations, thus reflecting privacy norms, and that (ii) deviations from the observed norms often signal unnecessary data collection. In addition, we analyze the privacy policies that accompany web forms. We show that, despite their wide adoption and use, there is a disconnect between privacy policy disclosures and the observed privacy norms.

This repository contains the source code for our web form measurement study. If you publish work based on it, please cite our paper as follows:

```bibtex
@inproceedings{cui2025webform,
  title     = {Understanding Privacy Norms through Web Forms},
  author    = {Cui, Hao and Trimananda, Rahmadi and Markopoulou, Athina},
  booktitle = {Proceedings on Privacy Enhancing Technologies (PoPETs)},
  volume    = {2025},
  issue     = {1},
  year      = {2025}
}
```

## System Requirements

We tested the code on a server with the following configuration (reference hardware):

- CPU: Intel Xeon Silver 4316 (2 sockets x 20 cores x 2 threads)
- Memory: 512 GiB
- GPU: 2x NVIDIA RTX A5000 (24 GiB of video memory each)
- OS: Debian GNU/Linux 12 (Bookworm)

For non-machine-learning code, any commodity Linux or Mac computer should suffice. For machine-learning code, we recommend a decent NVIDIA GPU with at least 8 GiB of memory, and CUDA 12.1 support if using our conda environment.

We also ported the code (excluding model training) to macOS. A Mac computer with [MPS](https://developer.apple.com/metal/pytorch/) support can run the code, though we observed a 10x slower model inference performance on the M1 chip compared to the reference hardware.

Processing our datasets requires a large amount of storage space:

- The raw web form dataset (`crawl-merged-core.tar.xz`) requires 284 GiB of uncompressed space.
- The privacy policy dataset (`privacy-policies.tar.xz`) requires 4 GiB of uncompressed space.
- A fast SSD is highly recommended.

## Environment Setup

Most of the code is written in Python, and we use conda to manage Python dependencies. Before proceeding, please install conda by following the instructions [here](https://conda.io/projects/conda/en/latest/user-guide/install/linux.html).

To clone the repository:

```console
$ git clone https://github.com/UCI-Networking-Group/webform.git ~/webform-code
$ cd ~/webform-code
$ git submodule init
$ git submodule update
```

Create a new conda environment named `webform` and install the necessary dependencies:

```console
$ conda env create -n webform -f environment.yml
$ conda activate webform
$ pip install -e privacy-policy/PoliGraph/
```

On macOS arm64, use `environment-macos-arm64.yml` instead to create the conda environment.

The web form crawler (located in `crawler/`) is written in TypeScript and JavaScript. We have included the NodeJS runtime in the conda environment. Set up the JavaScript dependencies and compile the code with the following commands:

```console
$ cd ~/webform-code/crawler/
$ npm install
$ npm run compile
$ npx playwright install
$ npx playwright install-deps
```

## Usage

You can download the associated artifacts [here](https://athinagroup.eng.uci.edu/projects/auditing-and-policy-analysis/webform-artifacts/).

While the code is generally path-independent, the following paths are assumed in the documentation:

- `~/webform-code` -- This repository.
- `~/webform-data` -- Raw web form dataset.
- `~/webform-privacy-policies` -- Privacy policy dataset.
- `~/webform-classifiers/pi-type` -- Model files for the PI type classifier.
- `~/webform-classifiers/form-type` -- Model files for the form type classifier.

Detailed usage instructions for each module can be found in the README files within the corresponding folders. The steps are numbered to reflect their order in the data processing pipeline:

- [Step 1: Website List and Categorization](./website-list/README.md)
- [Step 2: Web Form Crawler](./crawler/README.md)
- [Step 3: Dataset Preprocessing](./preprocessing/README.md)
- [Step 4: PI Type Classification](./pi-type-classification/README.md)
- [Step 5: Form Type Classification](./form-type-classification/README.md)
- [Step 6: Privacy Policy Processing](./privacy-policy/README.md)

These steps generate a SQLite database (`~/webform-data.db`) that stores all dataset annotation results (i.e., _annotated dataset_ in the paper). You can obtain our version of this file by decompressing `webform-data.db.xz` in the released artifacts:

```console
$ xz --decompress --keep webform-data.db.xz
```

After completing all data processing steps, you can reproduce the main results, including the tables and figures from our paper, using the two Jupyter notebooks in the `analysis/` folder:

- [web-form-analysis.ipynb](./analysis/web-form-analysis.ipynb) -- web form analysis results for Sections 4 and 5 in the paper.
- [privacy-policy-analysis.ipynb](./analysis/privacy-policy-analysis.ipynb) -- privacy policy analysis results for Section 6 in the paper.
