# Note

The code under this folder is from: git@github.com:xinyadu/eeqa.git
It's the implementation of the paper: Question answering for event extraction (trigger detection and argument extraction with various questioning strategies). [Paper link](https://arxiv.org/abs/2004.13625)

The code here is used for comparison with our results.
The following is its orginal README.

# Instructions

## data preprocessing

```
conda activate eeqa-ace-preprocess
cd preprocess
python produce_eeqa_data.py
cp -r ../data/eeqa/* ../eeqa/data/
```

## train/run model

```
conda activate eeqa
cd eeqa
```

for trigger extraction:
```
python run_trigger.py training_args_trigger.json
```

for main argument extraction:
```
python run_stage1.py training_args_stage1.json
```

for sub-argument extraction:
```
python run_stage2.py training_args_stage2.json
```