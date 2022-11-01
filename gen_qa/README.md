<!---
Copyright 2021 The HuggingFace Team. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Note:
The code is based on Huggingface transformer examples: [`question-answering`](https://github.com/huggingface/transformers/blob/master/examples/pytorch/question-answering)

# Instruction:
Data preprocess:

```
conda activate torch_transformer
cd preprocess
python produce_genqa_stage1_data.py
python produce_genda_stage2_gold.py
cp -r ../data/gen_qa/* ../gen_qa/data/
```

Train stage1 model:

```
conda activate torch_transformer
cd gen_qa
python run_seq2seq_qa.py training_arguments_stage1.json
```

Evaluate stage1 model event (type) classification F1 (optional):

```
python eval_stage1_event.py
```

Transfer stage1 output to stage2 input:
```
python transfer_s1_pred_to_s2_input.py
```

Train stage2 model:
```
python run_seq2seq_qa.py training_arguments_stage2.json
```

Evaluate stage2 on test set:
```
python eval_stage2_preds.py
```
