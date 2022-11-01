# Records of running EEQA on PHEE dataset

## Evaluation Metric

For trigger:

- classification: (prec_c, recall_c, f1_c)
  matched if the offset of a predicted trigger equals to the gold one's, and their event types are same
- identification: (prec_i, recall_i, f1_i)
  only consider the offsets of the triggers

For arguments:

EEQA originally used a similar evaluation approach as on the trigger.
For better analysis, we extend the evaluation metric to include 3 dimensions:

- classification VS identification (same as the trigger) (eg. prec_c vs prec_i)
- overall classification VS arg-specific classification
- span-level evaluation VS token-level evaluation
  - span-level evaluation refers to spans with exact same offsets are considered matched (prec_c, recall_c, f1_c, prec_i,recall_i, f1_i)
  - token-level evaluation refers to only consider whether each token are matched in predicted/gold spans (prec_tc, recall_tc, f1_tc, prec_ti,recall_ti, f1_ti)

## Results

### Stage1 Results

#### Trigger_extraction:

Settings:

```json
    "--train_batch_size", "8",
    "--eval_batch_size", "8",
    "--eval_per_epoch", "20",
    "--num_train_epochs", "3",
    "--learning_rate","4e-5",
    "--warmup_proportion", "0.1",
```

(bert-base-uncased) (test set)


| question_template                  | p_c   | r_c   | f1_c      | p_i   | r_1   | f1_i      |
| ------------------------------------ | ------- | ------- | :---------- | ------- | ------- | ----------- |
| "verb"                             | 67.80 | 58.52 | 62.82     | 69.33 | 59.84 | 64.24     |
| "action"                           | 65.54 | 58.82 | 62.00     | 67.80 | 60.85 | 64.14     |
| "trigger"                          | 66.11 | 60.14 | **62.98** | 67.67 | 61.56 | **64.47** |
| "what happened in the event"       | 67.41 | 58.11 | 62.42     | 68.94 | 59.43 | 63.83     |
| "what is the trigger in the event" | 67.22 | 57.81 | 62.16     | 68.75 | 59.13 | 63.58     |
| NULL                               | 67.53 | 55.68 | 61.03     | 68.88 | 56.80 | 62.26     |

(biovert_v1.1_pubmed) (test set)


| question_template                  | p_c   | r_c   | f1_c      | p_i   | r_1   | f1_i      |
| ------------------------------------ | ------- | ------- | :---------- | ------- | ------- | ----------- |
| "verb"                             | 67.53 | 61.16 | 64.18     | 68.98 | 62.47 | 65.57     |
| "action"                           | 69.71 | 59.53 | **64.22** | 71.50 | 61.05 | **65.86** |
| "trigger"                          | 67.04 | 61.46 | 64.13     | 68.69 | 62.98 | 65.71     |
| "what happened in the event"       | 67.73 | 60.45 | 63.88     | 68.86 | 61.46 | 64.95     |
| "what is the trigger in the event" | 66.74 | 61.46 | 63.99     | 68.17 | 62.78 | 65.36     |
|                                    | 65.75 | 55.48 | 60.18     | 67.31 | 56.80 | 61.61     |

#### Argument Extraction

Settings:

```json
    "--train_batch_size", "8",
    "--eval_batch_size", "8",
    "--eval_per_epoch", "20",
    "--num_train_epochs", "3",
    "--learning_rate","4e-5",
    "--warmup_proportion", "0.1",
    "--max_seq_length", "120",
    "--n_best_size", "20",
    "--max_answer_length", "30",
```

(biovert_v1.1_pubmed) (test set) (gold trigger) (without dynamic threshold: for retaining arguments )

**Classfication Result**


| question_template               | p_c       | r_c       | f1_c      | p_tc      | r_tc      | f1_tc     |
| :-------------------------------- | ----------- | ----------- | :---------- | ----------- | ----------- | ----------- |
| arg_name                        | 43.88     | 72.72     | 54.73     | 64.91     | 85.51     | 73.80     |
| arg_name + in event type        | 43.86     | 73.80     | 55.02     | 65.11     | 85.67     | 73.99     |
| arg_name + in trigger           | 44.00     | 75.45     | 55.59     | 62.79     | **88.96** | 73.62     |
| arg_query                       | 43.57     | 73.28     | 54.65     | 65.48     | 86.44     | 74.51     |
| arg_query + in event type       | 43.74     | 73.68     | 54.89     | 63.95     | 85.70     | 73.24     |
| arg_query + in trigger          | **45.90** | **75.81** | **57.18** | **67.90** | 87.22     | **76.35** |
| arg_description                 | 43.60     | 72.72     | 54.52     | 63.84     | 84.59     | 72.77     |
| arg_description + in event type | 41.76     | 72.72     | 53.05     | 62.40     | 86.35     | 72.45     |
| arg_description + in trigger    | 45.54     | **75.81** | 56.90     | 67.54     | 87.18     | 76.11     |

**Identification Result**


| question_template               | p_i       | r_i       | f1_i      | p_ti      | r_ti      | f1_ti     |
| --------------------------------- | ----------- | ----------- | :---------- | ----------- | ----------- | ----------- |
| arg_name                        | 44.14     | 73.04     | 55.03     | 71.63     | 89.03     | 79.39     |
| arg_name + in event type        | 44.15     | 74.08     | 55.33     | 71.41     | 89.78     | 79.55     |
| arg_name + in trigger           | 44.35     | 75.98     | 56.01     | 70.22     | **92.32** | 79.77     |
| arg_query                       | 43.86     | 73.76     | 55.01     | 71.60     | 90.39     | 79.91     |
| arg_query + in event type       | 44.07     | 73.96     | 55.23     | 70.82     | 89.56     | 79.09     |
| arg_query + in trigger          | **46.10** | **76.02** | **57.39** | **73.31** | 90.30     | **80.92** |
| arg_description                 | 43.92     | 73.08     | 54.86     | 71.15     | 88.74     | 78.98     |
| arg_description + in event type | 42.24     | 73.32     | 53.60     | 70.09     | 90.11     | 78.85     |
| arg_description + in trigger    | 45.83     | **76.02** | 57.18     | 73.03     | 89.80     | 80.55     |

**Classification Result for Each Role (arg_query + trigger template)**


| question_template | p_c   | r_c   | f1_c  | p_tc    | r_tc    | f1_tc |
| ------------------- | ------- | ------- | :------ | --------- | --------- | ------- |
| AE_Subject        | 42.82 | 72.55 | 53.85 | 73.84   | 84.65   | 78.87 |
| AE_Treatment      | 46.56 | 81.56 | 59.28 | *64.17* | *93.43* | 76.08 |
| AE_Effect         | 50.32 | 77.77 | 61.10 | *68.95* | *90.06* | 78.10 |
| PTE_Subject       | 36.11 | 66.10 | 46.71 | 65.82   | 79.13   | 71.87 |
| PTE_Treatment     | 36.90 | 63.09 | 46.57 | 68.63   | 79.62   | 73.72 |
| PTE_Effect        | 20.90 | 23.73 | 22.22 | 50.68   | 46.69   | 48.60 |

**Different strategy for getting inference results (arg_query + trigger template)**


| filter strategy                                      | p_c       | r_c       | f1_c      | p_tc      | r_tc      | f1_tc     |
| :----------------------------------------------------- | ----------- | ----------- | :---------- | ----------- | ----------- | ----------- |
| EEQA Original Constraints                            | 46.10     | **76.02** | 57.39     | 73.31     | **90.30** | **80.92** |
| + get top2 non-overlapped results in all candidates  | 52.35     | 66.40     | 58.54     | 66.86     | 85.37     | 74.99     |
| + get non-overlapped results in top2 candidate pairs | **67.74** | 63.82     | **65.72** | **83.09** | 77.52     | 80.21     |

## Analysis

### Multi-span argument processing

For each role in an event, there might be more than one arguments/spans. (BTW, when preprocessing the data, we also consider those arguments with discontinuous spans as seperate arguments currently.)

As for argument extraction, EEQA predicts the probability of each token to be an argument start/end, that might be problem when dealing with multiple span arguments.

For multi-span argument extraction, EEQA:

- during training, splits multiple spans to multiple instances (with same inputs), which means for the same input, the model might be trained on different expected targets. This probably would:
  - increase the model's ability of generalization
  - decrease the model's performance
- for inference, 1) get top k start token candidates and top k end candidates; 2) for each pair of token candidates, filter those that violate the rules or whose scores are no more than CLS(no answer); 3) for the remaining pairs, sort by "start_score + end_score" and get the first M(=2) results.
  - Is the predicted span with the highest start score and highest end score always belongs to one gold target span? The problem probably won't be so serious if the candidates have obvious priorities, but if we have some parallel candidate spans, this might lead to chaos.
  - Fix the number of selected spans for each argument could reduce the precision [proved by the results].

### Sub-token truncating

EEQA only keeps and uses the first sub-token of each word, which might lose some performance.

### Result Analysis

- given trigger information will increase the performance
- PTE is much harder to learn, especially for PTE Effect.
