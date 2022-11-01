# Records of running Generative QA on PHEE dataset

## Basic Setting

- Encoder-Decoder QA model based on T5.
- Regard both multi-span and discontinuous span as multiple span arguments.
- Use "; " to connect the answer of multiple span.
- Use "question:" + question + "context:" as prompt

## Evaluation Metric

For trigger:

- classification: (prec_c, recall_c, f1_c)
  matched if the offset of a predicted trigger equals to the gold one's, and their event types are same
- ~~identification: (prec_i, recall_i, f1_i)~~
  For generative QA model, we do not evaluate identification result.

For arguments:

- ~~classification VS identification (same as the trigger) (eg. prec_c vs prec_i)~~
- overall classification VS arg-specific classification
- span-level evaluation VS token-level evaluation
  - span-level evaluation refers to spans with exact same offsets are considered matched (prec_c, recall_c, f1_c)
  - token-level evaluation refers to only consider whether each token are matched in predicted/gold spans (prec_tc, recall_tc, f1_tc)
    - Here we compute token-level precision over predicted argument tokens of all examples
    - and token-level recall over gold argument tokens of all examples
    - then compute the F-score over the precision and recall, which is usually called micro-F1.
    - **This metric is not the same as the F1 score used by SQuAD official metric, which is computed on each example and then averaged and usually called macro-F1.**

## Pre-train Model

[T5](https://arxiv.org/pdf/1910.10683.pdf) : Pre-trained on C4 Corpus
[SciFive](https://arxiv.org/pdf/2106.03598.pdf): Pre-trained on C4 and:

- **PubMed Abstract (Pubmed)**: "The PubMed database contains more than 32 millions citations and abstracts of biomedical literature. For the purpose of model pre-training, we use only the abstracts."
- **PubMed Central (PMC)**: "PMC is a corpus of free full-text articles in the domain of biomedical and life sciences."

## Results

### Stage1 Results

#### Argument Extraction

Settings:

(test set) (gold trigger)

**Classfication Result for Different Pre-trained Model (arg_name as template)**


| question_template        | p_c   | r_c   | f1_c  | p_tc  | r_tc  | f1_tc |
| :------------------------- | ------- | ------- | :------ | ------- | ------- | ------- |
| t5_base                  | 51.05 | 61.49 | 55.79 | 74.86 | 81.36 | 77.97 |
| SciFive-base-PMC         | 52.96 | 63.74 | 57.85 | 78.90 | 80.08 | 79.49 |
| SciFive-base-Pubmed      | 51.96 | 62.37 | 56.69 | 76.55 | 77.54 | 77.04 |
| SciFive-base-Pubmed_PMC  | 52.07 | 62.74 | 56.91 | 74.84 | 81.37 | 77.97 |
| t5_large                 |       |       |       |       |       |       |
| SciFive-large-PMC        |       |       |       |       |       |       |
| SciFive-large-Pubmed     |       |       |       |       |       |       |
| SciFive-large-Pubmed_PMC |       |       |       |       |       |       |

**Classfication Result for Different Question Template (SciFive-base-PMC)**


| question_template               | p_c       | r_c       | f1_c      | p_tc      | r_tc      | f1_tc     |
| :-------------------------------- | ----------- | ----------- | :---------- | ----------- | ----------- | ----------- |
| arg_name                        | 52.96     | 63.74     | 57.85     | **78.90** | 80.08     | 79.49     |
| arg_name + in event type        | 53.15     | 64.10     | 58.12     | 76.71     | 82.63     | 79.56     |
| arg_name + in trigger           | **54.40** | **65.71** | **59.52** | 77.67     | 83.85     | **80.64** |
| arg_query                       | 51.86     | 62.37     | 56.63     | 74.94     | 77.57     | 76.23     |
| arg_query + in event type       | 52.69     | 63.46     | 57.58     | 74.17     | 83.15     | 78.40     |
| arg_query + in trigger          | 52.73     | 63.42     | 57.58     | 76.42     | 81.86     | 79.05     |
| arg_description                 | 52.66     | 63.26     | 57.48     | 77.69     | 78.25     | 77.97     |
| arg_description + in event type | 50.97     | 61.41     | 55.70     | 76.01     | 77.85     | 76.92     |
| arg_description + in trigger    | 53.83     | 65.47     | 59.09     | 76.11     | **85.22** | 80.41     |

**Classification Result for Each Role (arg_name + in trigger, SciFive-base-PMC)**


| question_template | p_c   | r_c   | f1_c  | p_tc  | r_tc  | f1_tc |
| ------------------- | ------- | ------- | :------ | ------- | ------- | ------- |
| AE_Subject        | 31.86 | 65.16 | 42.79 | 70.82 | 84.00 | 76.85 |
| AE_Treatment      | 69.38 | 67.60 | 68.48 | 79.16 | 85.92 | 82.40 |
| AE_Effect         | 72.15 | 69.91 | 71.01 | 85.19 | 87.33 | 86.24 |
| PTE_Subject       | 24.43 | 54.24 | 33.68 | 79.45 | 81.72 | 80.57 |
| PTE_Treatment     | 54.07 | 48.99 | 51.41 | 84.23 | 69.71 | 76.28 |
| PTE_Effect        | 13.74 | 30.51 | 18.95 | 34.37 | 65.0  | 44.96 |

## Analysis
