## Step 4: PI Type Classification

In Section 4.2 (PI Type Classification) of our paper, we detail our methodology for identifying the types of personal information (PI) requested in each web form field. The relevant code is located in this folder.

### Step 4.1: Generating the List of PI Types

As described in Section 4.2 -- List of PI Types, we use `prelabel-gpt-freeform.py` to obtain a list of PI types present in our dataset:

```console
$ python prelabel-gpt-freeform.py ~/webform-data gpt-pi-types.jsonl
```

The output is saved in `gpt-pi-types.jsonl`:

```console
$ shuf -n1 gpt-pi-types.jsonl
{"domain": "dslreports.com", "job_hash": "b689489d7a532483653a5c72775f2237057974d07421878c4adb0c59d1cefc14", "filename": "form-0.json", "response": ["Username", "Email Address", "Password"]}
```

As outlined in the paper, we manually reviewed these outputs to create the final list of PI type labels.

### Step 4.2: Training the Classifier

#### Step 4.2.1: Feature Extraction

As discussed in Section 4.2 -- Feature Extraction and Labeling, we use `extract-features.py` to convert the HTML code of each web form field into a human-readable YAML string for manual labeling:

```console
$ python extract-features.py ~/webform-data pi-unlabeled.jsonl
```

Each line in `pi-unlabeled.jsonl` is a JSON object containing the extracted YAML string and additional metadata about the web form:

```console
$ shuf -n1 pi-unlabeled.jsonl | jq -r '.text'
phone_number

tagName: INPUT
label: Phone number *
attributes:
  type: text
  id: edit-phone-number
  autocomplete: off
isVisible: true
```

#### Step 4.2.2: Manual Data Labeling using Label Studio

We use [Label Studio](https://labelstud.io/), an open-source data labeling platform, to facilitate manual data labeling. Set up a "Text Classification" project in Label Studio, and use `import-to-ls.py` to import the unlabeled data:

```console
$ python import-to-ls.py -P <API_KEY> <LABEL_STUDIO_URL> <PROJECT_ID> pi-unlabeled.jsonl
```

In this commandline:

- Replace `<LABEL_STUDIO_URL>` with your Label Studio instance URL (e.g., `http://localhost:8080/`).
- `<PROJECT_ID>` is the project number in the URL (e.g., if the URL is `http://localhost:8080/projects/1/data`, then `PROJECT_ID` is `1`).
- `<API_KEY>` can be found in your account settings.

We also provide a helper script, `merge-ls-verified-samples.py`, to merge manual annotations from Label Studio back into the unlabeled `.jsonl` file:

```console
$ python merge-ls-verified-samples.py -P <API_KEY> <LABEL_STUDIO_URL> <PROJECT_ID> pi-unlabeled.jsonl pi-v2.jsonl
```

The output `pi-v2.jsonl` contains both labeled and unlabeled data, which can be re-imported into Label Studio using `import-to-ls.py`. This is useful if the dataset changes and you wish to incorporate new data without discarding previous work.

#### Step 4.2.3: Training the SetFit Model

Once labeling is complete, use `train-setfit-script.py` to train the PI type classifier:

```console
$ python train-setfit-script.py -P <API_KEY> <LABEL_STUDIO_URL> <PROJECT_ID> -o model/
```

The trained model checkpoint will be stored in the `model/latest/` folder. Keep it for future use:

```console
$ cp -rT model/latest ~/webform-classifiers/pi-type
```

#### Artifacts

We have released the trained PI type classifier as `classifier-pi-type.tar.zst` in the released artifacts. To extract the classifier:

```console
$ mkdir -p ~/webform-classifiers/pi-type
$ tar xf classifier-pi-type.tar.zst -C ~/webform-classifiers/pi-type
```

In `extra/label-studio_pi-types-classification.tar.zst`, you can find an export of the annotations from Label Studio, provided primarily for archival purposes.

Note that some PI type names in our code and model differ from those used in the paper:

| Name in the Code/Model          | Name in the Paper   |
| ------------------------------- | ------------------- |
| LocationCityOrCoarser           | Coarse Location     |
| AgeOrAgeGroup                   | Age                 |
| CitizenshipOrImmigrationStatus  | Immigration Status  |
| UsernameOrOtherId               | Online Alias        |

### Step 4.3: Dataset Annotation

#### Step 4.3.1: Feature Extraction

We use the same script as in Step 4.2.1, `extract-features.py`, to convert the HTML code of web form fields into YAML strings for the classifier input:

```console
$ python extract-features.py ~/webform-data pi-unlabeled.jsonl
100%|██████████| 970644/970644 [04:36<00:00, 3506.68it/s]
```

#### Step 4.3.2: Classifier Inference

Use `prelabel-model.py` to process the YAML strings of form fields and classify the PI types:

```console
$ python prelabel-model.py pi-unlabeled.jsonl ~/webform-classifiers/pi-type pi-labeled.jsonl
774477it [40:12, 320.98it/s]
```

#### Step 4.3.3: Importing Classification Results

Finally, use `import-classification.py` to import the PI type classification results back into the main database:

```console
$ python import-classification.py -i pi-labeled.jsonl ~/webform-data
100%|██████████| 970644/970644 [04:37<00:00, 3493.70it/s]
```

The results are saved in the `field_classification` table:

```console
$ sqlite3 -header ~/webform-data.db 'SELECT * FROM field_classification ORDER BY RANDOM() LIMIT 3'
domain|job_hash|form_filename|field_list
primus.ca|24771f1319126c41765064260e83614ae9121b689fc16dd9047a63439f402466|form-0.json|["PhoneNumber", "PhoneNumber", "PostalCode"]
squarespace.com|52b8a1127937903c9223687b3b9a4a9278ade734d45648e1978ddfab32604321|form-0.json|["EmailAddress", "Password"]
arin.net|6c135bee885e61ac64e875577425cad9de2119a2f79bc5d659977292d78766d4|form-0.json|["EmailAddress"]
```

#### Step 4.3.4: Manual Validation

We evaluate the model's performance by creating a separate validation dataset using the same procedure used for the training data. Use `manual-eval.py` to run the classifier on the validation dataset and generate performance metrics (as shown in Table 3 of our paper):

```console
$ python manual-eval.py -P <API_KEY> <LABEL_STUDIO_URL> <PROJECT_ID> model/latest/
[50 50 50 50 50 50 50 50 50 50 50 50 50 50 50 50]
             precision    recall  f1-score   support

    Address      0.920     1.000     0.958        46
DateOfBirth      0.900     0.938     0.918        48
......
  micro avg      0.935     0.952     0.943       786
......
```

#### Artifacts

The dataset annotations of PI types are stored in the `field_classification` table in the released results database (`webform-data.db`).
