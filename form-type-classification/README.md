## Step 5: Form Type Classification

In Section 4.1 (Form Type Classification) of our paper, we describe our methodology for classifying web forms according to their functionality. The relevant code can be found in this folder.

### Step 5.1: Creating the Web Form Taxonomy

As explained in Section 4.1 -- Web Form Taxonomy, we use `prelabel-gpt-freeform.py` to get an initial understanding of the types of web forms present in the dataset, which helps us build the web form taxonomy:

```console
$ python prelabel-gpt-freeform.py ~/webform-data gpt-form-types.jsonl
```

The results are saved to `gpt-form-types.jsonl`:

```console
$ shuf -n1 gpt.jsonl | jq
{
  "domain": "neocities.org",
  "job_hash": "eb447eccdf6567792c72f0839018c172e5cdbf5f60ae7f2299d909d3d5cd02b6",
  "form_filename": "form-0.json",
  "form_type": "User Registration Form"
}
```

### Step 5.2: Classifier Training (Active Learning Loop)

#### Step 5.2.1: GPT Labeling

Use `prelabel-gpt.py` to utilize the GPT API to label new training samples (random sampling):

```console
$ python prelabel-gpt.py ~/webform-data
```

After the initial round, we have the list of active learning samples from Step 5.2.5. Use it instead of random sampling:

```console
$ python prelabel-gpt.py ~/webform-data --list al_list.csv
```

#### Step 5.2.2: MarkupLM Model Training

Use `train-markuplm.py` to fine-tune the MarkupLM model using all the training samples labeled so far:

```console
$ mkdir active-learning
$ python train-markuplm.py ~/webform-data -o active-learning/<ROUND> --batch-size 16 --base-model microsoft/markuplm-base
```

Here, `<ROUND>` is a placeholder for distinguishing each round of active learning (e.g., `r0`, `r1`, `r2`...). The trained model weights can be found at `active-learning/<ROUND>/best/`.

#### Step 5.2.3: Inference

Use `classify.py` to run the current classifier on all the samples in the dataset:

```console
$ python classify.py active-learning/<ROUND>/best/ ~/webform-data --bf16
```

The results are saved in the `form_classification` table in the database. The `--bf16` argument is optional and enables half-precision computation to accelerate the process.

#### Step 5.2.4: Model Evaluation (Against GPT Results)

To assess how the model performs thus far, use `al_test_select.py` to select random samples not included in the training data, run `prelabel-gpt.py` again to label them, and then call `al_test_check.py` to obtain performance metrics:

```console
$ python al_test_select.py ~/webform-data active-learning/<ROUND>-test.csv
$ python prelabel-gpt.py ~/webform-data --list active-learning/<ROUND>-test.csv
$ python al_test_check.py ~/webform-data active-learning/<ROUND>-test.csv -o active-learning/<ROUND>-test.json
```

The results are saved in `<ROUND>-test.json`:

```console
$ head -n5 active-learning/r2-test.json
{
  "accuracy": 0.8153846153846154,
  "Account Registration Form/precision": 1.0,
  "Account Registration Form/recall": 0.7916666666666666,
  "Account Registration Form/f1-score": 0.8837209302325582,
```

These extra samples (20 per form type, by default) labeled by the GPT will be included in the training data for the next round of training.

#### Step 5.2.5: Active Learning Sampling

As explained in Section 4.1 -- Active Learning, we use a combination of uncertainty-based and random sampling to select new samples for labeling in the next round. This is implemented in `al_select.py`:

```console
$ python al_select.py ~/webform-data al_list.csv
```

For the first few rounds, you may need to manually enforce dataset balance by giving preference to minority labels. This functionality isn't fully integrated into the code, so you'll need to manually adjust the sampling weights. Replace the line for calculating sampling weights as shown below, and manually adjust `al_list.csv`:

```patch
--- a/al_select.py
+++ b/al_select.py
@@ -30,7 +30,7 @@
     for domain, job_hash, form_filename, scores_json in cur:
         scores = json.loads(scores_json)
         descriptors.append((domain, job_hash, form_filename))
-        sample_score.append(min(scores.values(), key=lambda v: abs(v - 0.5)))
+        sample_score.append(scores['Content Submission Form'])
 
     bin_edges = np.linspace(0.0, 1.0, N_BINS, endpoint=False)
     bin_indices = np.digitize(sample_score, bin_edges)
```

After this step, return to Step 5.2.1 and continue with the next round of active learning.

#### Step 5.2.6: Final Model

After classifier performance stabilizes (based on metrics from Step 5.2.4), train the final version of the model. To maximize performance, use the `markuplm-large` variant:

```console
$ python train-markuplm.py ~/webform-data -o active-learning/final --batch-size 10 --base-model 'microsoft/markuplm-large'
$ cp -rT active-learning/final/best/ ~/webform-classifiers/form-type/
```

#### Artifacts

We have released `classifier-form-type.tar.zst`, the trained form type classifier. To extract the classifier:

```console
$ mkdir -p ~/webform-classifiers/form-type/
$ tar xf classifier-form-type.tar.zst -C ~/webform-classifiers/form-type/
```

### Step 5.3: Dataset Annotation

After training the form type classifier, use `classify.py` to annotate the dataset:

```console
$ python classify.py ~/webform-classifiers/form-type ~/webform-data
Generating train split: 292655 examples [00:00, 460072.68 examples/s]
Map (num_proc=32): 100%|██████████| 292655/292655 [00:47<00:00, 6185.46 examples/s]
100%|██████████| 292655/292655 [35:46<00:00, 136.33it/s]
```

The results are saved in the `form_classification` table:

```console
$ sqlite3 -header ~/webform-data.db 'SELECT * FROM form_classification ORDER BY RANDOM() LIMIT 1'
domain|job_hash|form_filename|form_type|scores
tolstoycomments.com|461510895ba486d821dd280b5bfe5999fe2f076f9ee72320b48e167f928b9187|form-0.json|Account Registration Form|{"Account Registration Form":0.9035722017288208,"Account Login Form":0.07047338038682938,"Account Recovery Form":0.008954057469964027,"Payment Form":0.0076364376582205296,"Role Application Form":0.006356534082442522,"Financial Application Form":0.0056204707361757755,"Subscription Form":0.014919036068022251,"Reservation Form":0.005597282666712999,"Contact Form":0.007529920432716608,"Content Submission Form":0.005537017714232206}
```

#### Artifacts

The dataset annotations of form types are stored in the `form_classification` table in the released results database (`webform-data.db`).
