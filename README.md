


# UPDATES

## Data Updates: Version 2.0 of PHEE (PHEE V2.0)
In the original dataset, we observed particularly low levels of annotation inconsistency for the ‘subject.disorder,’ ‘time_elapsed,’ and ‘duration’ arguments. To address this, we implemented an automatic revision for the ‘subject.disorder’ annotation and employed annotators to manually correct the ‘time_elapsed’ and ‘duration’ annotations. For the ‘subject.disorder’ correction, if a ‘treatment.disorder’ was present in the ‘subject’ argument but not annotated as ‘subject.disorder,’ we added it to the annotation. For ‘time_elapsed’ and ‘duration’ corrections, we provided detailed guidelines to the annotators to ensure consistent annotations. We evaluated annotation consistency using the EM_F1 score. The average EM_F1 scores for the ‘time_elapsed’ and ‘duration’ annotations were 75.3%.

The updated data can be downloaded at  [``Leveraging ChatGPT in Pharmacovigilance Event Extraction: An Empirical Study Git Repo``](https://github.com/ZhaoyueSun/phee-with-chatgpt)

## New Paper: [``DrugWatch: A Comprehensive Multi-Source Data Visualisation Platform for Drug Safety Information``](https://aclanthology.org/2024.acl-demos.18/)
The paper introduces “DrugWatch”, an easy-to-use and interactive multi-source information visualisation platform for drug safety study. It allows users to understand common side effects of drugs and their statistical information, flexibly retrieve relevant medical reports, or annotate their own medical texts with our automated annotation tool. Supported by NLP technology and enriched with interactive visual components, we are committed to providing researchers and practitioners with a one-stop information analysis, retrieval, and annotation service. The demo system is online.

## New Paper: [``Leveraging ChatGPT in Pharmacovigilance Event Extraction: An Empirical Study``](https://aclanthology.org/2024.eacl-short.30/)

The paper explores the potential of ChatGPT in pharmacovigilance event extraction. The research involves extensive experiments using various prompts and strategies to assess ChatGPT's performance. The paper also investigates using ChatGPT for data augmentation and filtering strategies to achieve more stable results.

_____________________________________________________________________________________________________________________________

# Introduction

Data and Code for [``PHEE: A Dataset for Pharmacovigilance Event Extraction from Text``](https://arxiv.org/abs/2210.12560/)

## Data

Raw and processed data are under Data folder:
```
- clean: clean raw data
- json: processed structured data
- eeqa: EEQA format data transfered from json data
- gen_qa: GenQA format data transfered from json data
- ace: ACE format data transfered from json data
```

## Compared Methods
### gen_qa

We use a generative QA model to be our baseline method.
The code is based on  [`huggingface example code`](https://github.com/huggingface/transformers/blob/master/examples/pytorch/question-answering/).

We modified the training code of [`seq2seq_qa`](https://github.com/huggingface/transformers/blob/master/examples/pytorch/question-answering/run_seq2seq_qa.py) to fit our data and evaluation setting. More details could be found in the folder README. 

### eeqa

EEQA is one of our comparison method from the paper: [`Event Extraction by Answering (Almost) Natural Questions`](https://arxiv.org/abs/2004.13625).

The code under this folder is from the paper's released [code](https://github.com/xinyadu/eeqa). 
A few places are modified to fit our data.


### ACE

ACE is a sequence labelling method from the paper: [`Automated Concatenation of Embeddings for Structured Prediction`](https://arxiv.org/pdf/2010.05006):
The code under this folder is from the paper's released [code](https://github.com/Alibaba-NLP/ACE).
The configuration we used is under ACE/config

