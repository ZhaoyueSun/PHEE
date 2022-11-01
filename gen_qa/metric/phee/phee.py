# Copyright 2020 The HuggingFace Datasets Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" PHEE metric. """

import datasets
import collections
import re
import string
from evaluate.phee_metric import compute_metric

# from .evaluate import (
#     apply_no_ans_threshold,
#     find_all_best_thresh,
#     get_raw_scores,
#     make_eval_dict,
#     make_qid_to_has_ans,
#     merge_eval,
# )

# TODO: add citation
_CITATION = """\
@inproceedings{Rajpurkar2016SQuAD10,
  title={SQuAD: 100, 000+ Questions for Machine Comprehension of Text},
  author={Pranav Rajpurkar and Jian Zhang and Konstantin Lopyrev and Percy Liang},
  booktitle={EMNLP},
  year={2016}
}
"""


_DESCRIPTION = """
This metric wrap SQuAD v2.0 metric for the PHEE dataset to support:
multi-span argument evaluation; 
argument(role)-specific metrics.
"""

_KWARGS_DESCRIPTION = """
Computes EM_F1 and Micro_F1(Token_F1).
"""


@datasets.utils.file_utils.add_start_docstrings(_DESCRIPTION, _KWARGS_DESCRIPTION)
class PHEE(datasets.Metric):
    def _info(self):
        return datasets.MetricInfo(
            description=_DESCRIPTION,
            citation=_CITATION,
            inputs_description=_KWARGS_DESCRIPTION,
            features=datasets.Features(
                {
                    "predictions": {
                        "id": datasets.Value("string"),
                        "prediction_text": datasets.Value("string"),
                        "no_answer_probability": datasets.Value("float32"),
                    },
                    "references": {
                        "id": datasets.Value("string"),
                        "answers": datasets.Value("string"),
                        "question_type": datasets.Value("string"),
                    },
                }
            ),
            # codebase_urls=["https://rajpurkar.github.io/SQuAD-explorer/"],
            # reference_urls=["https://rajpurkar.github.io/SQuAD-explorer/"],
        )


    def _parse_entities(self, text):
        EVENT_TYPES = ['Adverse event', 'Potential therapeutic event']
        MAIN_ARGS = ['Subject', 'Treatment', 'Effect']
        pattern = re.compile(r'\[.*?\][^\[]*')
        entities = collections.defaultdict(list)
        event = None
        for ent_str in re.findall(pattern, text):
            k, v = ent_str.split(']', 1)
            k = k.replace('[','').strip()
            v = v.strip()
            if k in EVENT_TYPES:
                event = "_".join(k.split(' '))
                k = event+".Trigger"
            elif k in MAIN_ARGS:
                if event:
                    k = event + "." + k
                else:
                    continue
            else:
                continue
            if v:
                spans = v.split(";")
                for span in spans:
                    entities[k].append(span.strip())

        return entities


    def _compute(self, predictions, references):
        
        instances = []
        for pred, refer in zip(predictions, references):
            assert pred['id'] == refer['id']
            instance_id = "_".join(pred['id'].split('_')[:-1])
            question_type = refer['question_type']
            pred_txt = pred['prediction_text']
            ref_txt = refer['answers']
            if question_type == 'Events':
                pred_entities = self._parse_entities(pred_txt)
                ref_entities = self._parse_entities(ref_txt)
                keys = list(set(list(pred_entities.keys())+list(ref_entities.keys())))
                for k in keys:
                    instance = {
                        'id': instance_id,
                        'type': k,
                        'predictions':[],
                        'golds':[]
                    }
                    if k in pred_entities:
                        instance['predictions'] = pred_entities[k]
                    if k in ref_entities:
                        instance['golds'] = ref_entities[k]
                    instances.append(instance)
            else:
                if pred_txt or ref_txt:
                    pred_entities = pred_txt.split("; ")
                    ref_entities = ref_txt.split("; ")
                    instance = {
                            'id': instance_id,
                            'type': question_type,
                            'predictions':pred_entities,
                            'golds':ref_entities
                    }
                    instances.append(instance)

        result = compute_metric(instances)

        return result


