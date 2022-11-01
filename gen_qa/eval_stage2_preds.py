"""
Evaluate GenQA stage2 test set prediction result. (Accumulate Stage1 Prediction)
"""
import sys
import os
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('.'))
from ast import arguments
from tkinter import E
import spacy
from easydict import EasyDict as edict
import json
import re
import random
from collections import defaultdict
from evaluate.phee_metric import compute_metric

def read_pred_result(pred_file):
    
    question_types = {}
    with open(pred_file, 'r') as f:
        pred_rst = json.load(f)
        label_ids = pred_rst['label_ids']
        predictions = pred_rst['predictions']

    for instance in label_ids:
        question_types[instance['id']] = instance['question_type']
    
    output = defaultdict(lambda: defaultdict(list))

    for instance in predictions:
        ins_id = "_".join(instance['id'].split('_')[:-1])
        qtype = question_types[instance['id']]
        pred_text = instance['prediction_text']
        if pred_text:
            pred_ents = pred_text.split(';')
            for ent in pred_ents:
                output[ins_id][qtype].append(ent.strip())

    return output
    
def read_gold_result(gold_file):
    output = defaultdict(lambda: defaultdict(list))

    with open(gold_file, 'r') as f:
        gold_rst = json.load(f)
        data = gold_rst["data"]
        for instance in data:
            ins_id = "_".join(instance['id'].split('_')[:-1])
            qtype = instance["question_type"]
            answer = instance['answers']
            if answer:
                gold_ents = answer.split(';')
                for ent in gold_ents:
                    output[ins_id][qtype].append(ent.strip())

    return output

def main():

    gold_file = "data/stage2_gold/test_7.json"
    pred_file = "model/stage2/SciFive-base-PMC/7/predict_outputs.json"
    rst_file = "model/stage2/SciFive-base-PMC/7/predict_results.json"

    pred_rst = read_pred_result(pred_file)
    gold_rst = read_gold_result(gold_file)

    instances = []
    ins_ids = list(set(list(pred_rst.keys())+list(gold_rst.keys())))

    for instance_id in ins_ids:
        preds = pred_rst[instance_id] if instance_id in pred_rst else {}
        golds = gold_rst[instance_id] if instance_id in gold_rst else {}
        question_types = list(set(list(preds.keys())+list(golds.keys())))
        for qtype in question_types:
            instance = {
                'id': instance_id,
                'type': qtype,
                'predictions':[],
                'golds':[]
            }
            if qtype in preds:
                instance['predictions'] = preds[qtype]
            if qtype in golds:
                instance['golds'] = golds[qtype]
            instances.append(instance)
    
    result = compute_metric(instances=instances)

    with open(rst_file, 'w') as f:
        json.dump(result, f, indent=4)


    
           

if __name__ == '__main__':
    main()

