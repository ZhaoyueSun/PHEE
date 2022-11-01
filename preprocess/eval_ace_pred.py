import collections
import sys
import os
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('.'))
from easydict import EasyDict as edict
from collections import OrderedDict, defaultdict
import json
import random
from evaluate.phee_metric import compute_metric

def read_gold_result(gold_file):
    PARENT_ARGS = ['Subject', "Effect", 'Treatment'] # TODO: discard this Disorder after cleaning the data
    PARENT_TO_CHILD = {
        "Subject": ["Race", "Age", "Gender", "Population", "Disorder"],
        "Treatment": ["Duration", "Time_elapsed","Route","Freq","Dosage", "Disorder", "Drug"],
        "Effect": [],
    }
    outputs = []
    with open(gold_file, 'r') as f:
        for line in f.readlines():

            data = json.loads(line)
            data = edict(data)

            annotation = data.annotations[0]

            instance = defaultdict(list)
            instance['id'].append(data.id)

            for event in annotation.events:
                # Convert trigger
                ev_type = event.event_type
                trigger_text = event.Trigger.text[0][0]
                instance[ev_type+".Trigger"].append(trigger_text)

                # Convert arguments
                for role in PARENT_ARGS:
                    if role in event: # not appeared arguments are not stored
                        argument = event[role]
                        for entities in argument.text: # for each span in a multi-span argument
                            for t in entities: # for each discontinuous part of a argument span
                                instance[ev_type+"."+role].append(t)
                        # extract sub_arguments information
                        for key in argument.keys():
                            if key in PARENT_TO_CHILD[role]:
                                sub_arg = argument[key]
                                for entities in sub_arg.text: # for each span in a multi-span argument
                                    for t in entities: # for each discontinuous part of a argument span
                                        instance[ev_type+"."+role+"."+key].append(t)

                        # extraction combination.drug information
                        if role == 'Treatment' and 'Combination' in argument:
                            for comb in argument.Combination:
                                if "Drug" in comb:
                                    for entities in comb.Drug.text:
                                        for t in entities:
                                            instance[ev_type+".Combination.Drug"].append(t)


            outputs.append(instance)
    return outputs

def read_pred_results(pred_file):
    PARENT_ARGS = ['Subject', "Effect", 'Treatment'] 
    PARENT_TO_CHILD = {
        "Subject": ["Race", "Age", "Gender", "Population", "Sub_Disorder"],
        "Treatment": ["Duration", "Time_elapsed","Route","Freq","Dosage", "Treat_Disorder", "Drug"],
    }
    SUB_TO_MAIN = {}
    for main_arg in PARENT_TO_CHILD:
        for sub_arg in PARENT_TO_CHILD[main_arg]:
            SUB_TO_MAIN[sub_arg] = main_arg
    
    

    with open(pred_file, 'r') as f:
        docs = f.read().strip().split('\n\n')

    outputs = []
    no_event = 0
    for sentences in docs:
        instance = defaultdict(list)
        tokens = sentences.split('\n')
        main_entities = []
        cur_entity = ''
        cur_entity_type = 'O'
        for token in tokens:
            txt, _, pred, _ = token.split(' ')
            if pred != 'O':
                pred = pred.split('-',1)[1]
                if 'Trigger' not in pred:
                    pred = pred.split('.')[0]
                    if pred not in PARENT_ARGS:
                        pred = 'O'
            if pred == cur_entity_type:
                cur_entity = cur_entity + ' ' + txt
            else:
                if cur_entity_type != 'O':
                    main_entities.append([cur_entity, cur_entity_type])
                cur_entity = txt
                cur_entity_type = pred
        if cur_entity and cur_entity_type != 'O':
            main_entities.append([cur_entity, cur_entity_type])

        sub_entities = []
        cur_entity = ''
        cur_entity_type = 'O'
        for token in tokens:
            txt, _, pred, _ = token.split(' ')
            if pred != 'O':
                pred = pred.split('-',1)[1]
                if 'Trigger' in pred:
                    pred = 'O'
                elif pred in PARENT_ARGS:
                    pred = 'O'
                elif pred == 'Treatment.Combination.Drug':
                        pred = 'Combination.Drug'
                elif pred in SUB_TO_MAIN:
                    pred = SUB_TO_MAIN[pred]+"."+pred

            pred = pred.replace('Sub_Disorder', 'Disorder')
            pred = pred.replace('Treat_Disorder', 'Disorder')
            if pred == cur_entity_type:
                cur_entity = cur_entity + ' ' + txt
            else:
                if cur_entity_type != 'O':
                    sub_entities.append([cur_entity, cur_entity_type])
                cur_entity = txt
                cur_entity_type = pred
        if cur_entity and cur_entity_type != 'O':
            sub_entities.append([cur_entity, cur_entity_type])

        # find event_type
        event_type = None
        for entity, entity_type in main_entities:
            if 'Trigger' in entity_type:
                event_type = entity_type.split('.')[0]
        
        if event_type == None:
            event_type = 'UNK'
            no_event += 1

        for entity, entity_type in main_entities + sub_entities:
            if 'Trigger' in entity_type:
                instance[entity_type].append(entity)
            else:
                instance[event_type + "." + entity_type].append(entity)
                if entity_type == 'Combination.Drug':
                    instance[event_type + ".Treatment.Drug"].append(entity)

        outputs.append(instance)
    
    print("no events num:", no_event)
    return outputs


def main():
    gold_file = '../data/json/test.json'
    test_file = '../ACE/resources/taggers/phee_ace/test.tsv'
    rst_file = '../ACE/resources/taggers/phee_ace/test_result.json'

    gold_instances = read_gold_result(gold_file)
    pred_instances = read_pred_results(test_file)
    assert(len(gold_instances) == len(pred_instances))

    instances = []
    ev_tp = 0
    ev_pred_n = 0
    ev_gold_n = 0

    for preds, golds in zip(pred_instances, gold_instances):
        instance_id = golds['id'][0]
        question_types = list(set(list(preds.keys())+list(golds.keys())))
        for qtype in question_types:
            if qtype == 'id': continue
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

        # for event classification evaluation
        pred_evs = []
        gold_evs = []
        for k in preds:
            if 'Trigger' in k:
                ev_type = k.split('.')[0]
                pred_evs.append(ev_type)

        for k in golds:
            if 'Trigger' in k:
                ev_type = k.split('.')[0]
                for _ in golds[k]:
                    gold_evs.append(ev_type)

        common = collections.Counter(pred_evs) & collections.Counter(gold_evs)
        num_same = sum(common.values())
        ev_tp += num_same
        ev_pred_n += len(pred_evs)
        ev_gold_n += len(gold_evs)

    ev_p = 1.0 * ev_tp / ev_pred_n
    ev_r = 1.0 * ev_tp / ev_gold_n
    if ev_p == 0 or ev_r == 0: ev_f1 = 0
    else:
        ev_f1 = 2*ev_p*ev_r/(ev_p+ev_r)

    print("event detection f1: ", ev_f1)

    result = compute_metric(instances=instances)
    result['EVENT_F1'] = ev_f1

    with open(rst_file, 'w') as f:
        json.dump(result, f, indent=4)



if __name__ == '__main__':
    main()