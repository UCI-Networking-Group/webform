## Step 3: Dataset Preprocessing

This folder contains scripts for preprocessing the dataset.

### Step 3.1: Validating Crawled Data

In [Step 1](../website-list/README.md), we generated `domain.db`, and in [Step 2](../crawler/README.md), we obtained the raw web form dataset and described its format. Assuming the dataset is stored in `~/webform-data`, use `validate.py` to ensure the crawled dataset is free of errors:

```console
$ python validate.py domain.db ~/webform-data
Total domains: 11500
Total forms: 938324
```

If you are using our released dataset, it should already be error-free. If, however, you encounter lines such as `ERROR:root:xx.com: not found in the database` or notice unexpected statistics, please check the dataset's layout for discrepancies.

The script also creates `~/webform-data.db` (or dataset path + `.db`) with the necessary information for dataset processing. Many of the following steps will process the dataset and store the results in this database.

### Step 3.2: Identifying Web Page Languages

In Section 4.3 (Annotated Dataset) -- Dataset Cleaning, we mention that non-English web pages were discarded. Use `check-webpage-language.py` in the root folder to identify the language of each web page:

```console
$ python check-webpage-language.py ~/webform-data
100%|██████████| 1149999/1150000 [14:41<00:00, 1304.97it/s]
```

The results are saved in the `page_language` table in the database:

```console
$ sqlite3 -header ~/webform-data.db 'SELECT * FROM page_language ORDER BY RANDOM() LIMIT 4'
incompetech.com|dc0c256d4bb8760f00a13ad681d2752a0657ac0374f6f56b7da246d521dce285|en
supermicro.com|f1510b6d88fae62e5982216136562c63f2e2a7cf71d8735aac892085ea792f45|guess:en
duetdisplay.com|daadaf81f25a5bb77059f34dbd121500840aec8d7a09578df958cced88680747|fr
modcombo.com|0ce6ef50ae49924a485e8cc71e30ff1cb631ba6acf356c55848789e8d50f5dc3|en
```

### Artifacts

The dataset's web page language annotations can be found in the `page_language` table in the released results database (`webform-data.db`).
