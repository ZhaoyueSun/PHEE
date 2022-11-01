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

The code under this folder is from the paper's released [code](https://github.com/xinyadu/eeqa) 
A few places are modified to fit our data.


### ACE

ACE is a sequence labelling method from the paper: [`Automated Concatenation of Embeddings for Structured Prediction`](https://arxiv.org/pdf/2010.05006):
The code under this folder is from the paper's released [code](https://github.com/Alibaba-NLP/ACE) 
The configuration we used is under ACE/config

