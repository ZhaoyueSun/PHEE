"""
Sample cases and get baseline outputs for case study. 
"""
import sys
import os
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('.'))
from ast import arg, arguments
from tkinter import E
import spacy
from easydict import EasyDict as edict
import json
import re
import random
from collections import defaultdict, OrderedDict
from evaluate.phee_metric import compute_metric
import string

def get_gold_instances(gold_file):
    PARENT_ARGS = ['Subject', "Effect", 'Treatment'] # TODO: discard this Disorder after cleaning the data
    PARENT_TO_CHILD = {
        "Subject": ["Race", "Age", "Gender", "Population", "Disorder"],
        "Treatment": ["Duration", "Time_elapsed","Route","Freq","Dosage", "Disorder", "Drug"],
        "Effect": [],
    }

    instances = {}
    with open(gold_file, 'r') as f:
        for line in f.readlines():

            data = json.loads(line)
            data = edict(data)

            annotation = data.annotations[0]

            instance = defaultdict(list)
            instance['context'] = [data.context]

            for ev_id, event in enumerate(annotation.events):
                # Convert trigger
                ev_type = event.event_type
                trigger_text = event.Trigger.text[0][0]
                instance[ev_type + str(ev_id)+".Trigger"].append(trigger_text)

                # Convert arguments
                for role in PARENT_ARGS:
                    if role in event: # not appeared arguments are not stored
                        argument = event[role]
                        for entities in argument.text: # for each span in a multi-span argument
                            for t in entities: # for each discontinuous part of a argument span
                                instance[ev_type + str(ev_id)+"."+role].append(t)
                        # extract sub_arguments information
                        for key in argument.keys():
                            if key in PARENT_TO_CHILD[role]:
                                sub_arg = argument[key]
                                for entities in sub_arg.text: # for each span in a multi-span argument
                                    for t in entities: # for each discontinuous part of a argument span
                                        instance[ev_type + str(ev_id) + "."+role+"."+key].append(t)

                        # extraction combination.drug information
                        if role == 'Treatment' and 'Combination' in argument:
                            for comb in argument.Combination:
                                if "Drug" in comb:
                                    for entities in comb.Drug.text:
                                        for t in entities:
                                            instance[ev_type + str(ev_id) +".Combination.Drug"].append(t)

            instances[data.id] = instance

    return instances

def get_eeqa_preds(pred_file):
    instances = {}
    with open(pred_file, 'r') as f:
        for line in f.readlines():
            data = json.loads(line)

            sentence = data['sentence']
            instance_id = data['id']
            instance = defaultdict(list)
            for entities in data['event']:
                event_type = entities[0][2]
                for eid, entity in enumerate(entities):
                    if eid == 0:
                        entity_type = event_type+".Trigger"
                    else:
                        entity_type = event_type+"."+entity[2]

                    entity_text = " ".join(sentence[entity[0]:entity[1]+1])
                    instance[entity_type].append(entity_text)
            for entity in data['arg_pred']:
                entity_type = entity[2]
                entity_text = " ".join(sentence[entity[0]:entity[1]+1])
                instance[entity_type].append(entity_text)
                
            instances[instance_id] = instance
    return instances

def get_seqlb_preds(pred_file, gold_file):
    instance_ids = []
    with open(gold_file, 'r') as f:
        for line in f.readlines():

            data = json.loads(line)
            data = edict(data)
            instance_ids.append(data.id)
            
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

    assert(len(docs) == len(instance_ids))
    instances = {}
    no_event = 0
    for sid, sentences in enumerate(docs):
        instance_id = instance_ids[sid]
        instance = defaultdict(list)
        tokens = sentences.split('\n')
        main_entities = []
        labels = []
        cur_entity = ''
        cur_entity_type = 'O'
        for token in tokens:
            txt, gold, pred, _ = token.split(' ')
            labels.append((txt, pred, gold))
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
        instance['labels'] = labels

        instances[instance_id] = instance
            
    return instances


def _parse_entities(text):
        EVENT_TYPES = ['Adverse event', 'Potential therapeutic event']
        MAIN_ARGS = ['Subject', 'Treatment', 'Effect']
        pattern = re.compile(r'\[.*?\][^\[]*')
        entities = defaultdict(list)
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

def get_genqa_preds(stage1_file, stage2_file):
    instances = defaultdict(dict)
    with open(stage1_file, "r") as f:
        s1_data = json.load(f)
        preds = s1_data['predictions']
        for pred in preds:
            instance_id = "_".join(pred['id'].split('_')[:-1])
            ents = _parse_entities(pred['prediction_text'])
            for k, v in ents.items():
                instances[instance_id][k] = v
    
    with open(stage2_file, "r") as f:
        s2_data = json.load(f)
        labels = s2_data['label_ids']
        preds = s2_data['predictions']
        for label, pred in zip(labels, preds):
            instance_id = "_".join(pred['id'].split('_')[:-1])
            pred_txt = pred['prediction_text']
            pred_type = label['question_type']
            if pred_txt: 
                instances[instance_id][pred_type] = [pred_txt]
            
    return instances
    
def _normalize_answer(s):
    """Lower text and remove punctuation, articles and extra whitespace."""

    def remove_articles(text):
        regex = re.compile(r"\b(a|an|the)\b", re.UNICODE)
        return re.sub(regex, " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        tks = text.split()
        tokens = []
        for tk in tks:
            tmp = ""
            for ch in tk:
                if ch not in exclude:
                    tmp += ch
                else:
                    if tmp:
                        tokens.append(tmp)
                        tmp = ""
            if tmp:
                tokens.append(tmp)
                    
        return " ".join(tokens)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))

def check_argument(arg_key, gold_instances, seqlb_preds, eeqa_preds, genqa_preds, query_id=None):

    find = False
    while not find:
        ids = list(gold_instances.keys())
        if not query_id:
            select_id = ids[random.randint(0, len(ids)-1)]
        else:
            select_id = query_id
        # select_id = '16317298_5'

        gold_rst = gold_instances[select_id]
        eeqa_rst = eeqa_preds[select_id]
        seqlb_rst = seqlb_preds[select_id]
        genqa_rst = genqa_preds[select_id]
        
        gold_span = ""
        seq_span = ""
        eeqa_span = ""
        genqa_span = ""
        
        
        for k in gold_rst:
            if k.split('.',1)[-1] == arg_key:
                gold_span = "; ".join(gold_rst[k])
                
        for k in seqlb_rst:
            if k.split('.',1)[-1] == arg_key:
                seq_span = "; ".join(seqlb_rst[k])
                
        for k, v in eeqa_rst:
            if k.split('.',1)[-1] == arg_key:
                eeqa_span = v
                
        for k in genqa_rst:
            if k.split('.',1)[-1] == arg_key:
                genqa_span = "; ".join(genqa_rst[k])
                
        if gold_span and (_normalize_answer(gold_span) != _normalize_answer(seq_span) or \
            _normalize_answer(gold_span) != _normalize_answer(eeqa_span) or \
            _normalize_answer(gold_span) != _normalize_answer(genqa_span)):
            find = True

    if find:
        print("id: %s"%select_id)
        print("sentence:")
        print(gold_rst['context'][0])
        print("\ngold:")
        for k in gold_rst:
            if k.split('.',1)[-1] == arg_key:
                print(k, ":", "; ".join(gold_rst[k]))
                
        print("\nseq labelling: ")
        for k in seqlb_rst:
            if k.split('.',1)[-1] == arg_key:
                print(k, ":", "; ".join(seqlb_rst[k]))

        print("\neeqa:")
        for k, v in eeqa_rst:
            if k.split('.',1)[-1] == arg_key:
                print(k, ":", v)
                
        print("\ngenqa:")
        for k in genqa_rst:
            if k.split('.',1)[-1] == arg_key:
                print(k, ":", "; ".join(genqa_rst[k]))
                
def get_arg_str(ann_dict, qtype):
    arg_str = ""
    for arg_type in ann_dict:
        if arg_type == 'context': continue
        # if arg_type == 'labels': continue
        etype, atype = arg_type.split('.', 1)
        if atype == qtype:
            arg_str = "; ".join(ann_dict[arg_type])
            arg_str = _normalize_answer(arg_str)
            arg_str = ''.join([i for i in etype if not i.isdigit()])+": "+arg_str
            return arg_str
    return arg_str

def check_mult_case(gold_ann):
    for arg_type in gold_ann:
        if '1' in arg_type:
            return True
    return False


def main():
    gold_file = "../data/json/test.json"
    gold_instances = get_gold_instances(gold_file)

    seqlb_preds = get_seqlb_preds('../ACE/resources/taggers/phee_ace/test.tsv',  "../data/json/test.json")

    eeqa_pred_file = "../eeqa/model/biobert_rst/stage2/4/pred_outputs.json"
    eeqa_preds = get_eeqa_preds(eeqa_pred_file)

    genqa_preds = get_genqa_preds("../gen_qa/model/stage1/SciFive-base-PMC/predict_outputs.json",
            "../gen_qa/model/stage2/SciFive-base-PMC/7/predict_outputs.json")


    single_folder = "../data/case_study/single"
    multi_folder = "../data/case_study/multiple"
    if not os.path.exists(single_folder):
        os.makedirs(single_folder)
    if not os.path.exists(multi_folder):
        os.makedirs(multi_folder)
    
    SAMPLE_NUM = 10
    # CAND_TYPES = ['Trigger', 'Subject', "Effect", 'Treatment', 'Subject.Race', 'Subject.Age', 'Subject.Gender', 'Subject.Population', 'Subject.Disorder', 'Treatment.Duration', 'Treatment.Time_elapsed', 'Treatment.Route', 'Treatment.Freq', 'Treatment.Dosage', 'Treatment.Disorder', 'Combination.Drug'] 
    CAND_TYPES = ['Treatment.Disorder']
    TYPE_CASES = defaultdict(int)
    MULT_CASE = 0


    # MUST_INCLUDE_IDS = ['16317298_5', '8589490_1', '12022905_2', '7761316_1', '18277922_1',
    # '11147747_2', '12659609_3', '11109149_3', '10646879_3', '10592946_3', '18262450_7', '11105373_1', '19131789_1', '17619811_1', '10332990_1', '23970584_4']
    # sample_ids = list(gold_instances.keys())
    # for mid in MUST_INCLUDE_IDS:
    #     sample_ids.remove(mid)
    # random.shuffle(sample_ids)
    # sample_ids = MUST_INCLUDE_IDS + sample_ids

    sample_ids = ['15811174_1']

    for sample_id in sample_ids:
        outdict = OrderedDict()
        outdict['instance_id'] = sample_id
        outdict['check_types'] = []

        gold_ann = gold_instances[sample_id]
        gold_ann = OrderedDict(sorted(gold_ann.items(), key=lambda x: x[0]))
        ADD_MULT = check_mult_case(gold_ann)
        ace_ann = seqlb_preds[sample_id]
        ace_ann.pop('labels')
        ace_ann = OrderedDict(sorted(ace_ann.items(), key=lambda x: x[0]))
        eeqa_ann = eeqa_preds[sample_id]
        eeqa_ann = OrderedDict(sorted(eeqa_ann.items(), key=lambda x: x[0]))
        genqa_ann = genqa_preds[sample_id]
        genqa_ann = OrderedDict(sorted(genqa_ann.items(), key=lambda x: x[0]))

        if ADD_MULT:
            if MULT_CASE < SAMPLE_NUM:
                MULT_CASE += 1
                outdict['ACE'] = ace_ann
                outdict['EEQA'] = eeqa_ann
                outdict['GENQA'] = genqa_ann
                outdict['GOLD'] = gold_ann
                outpath = os.path.join(multi_folder, "%s.json"%sample_id)
                # with open(outpath, 'w') as f:
                #     json.dump(outdict, f, indent=4)
            continue
    
        ADD_SINGLE = False
        for arg_type in CAND_TYPES.copy():
            gold_str = get_arg_str(gold_ann, arg_type)
            ace_str = get_arg_str(ace_ann, arg_type)
            eeqa_str = get_arg_str(eeqa_ann, arg_type)
            genqa_str = get_arg_str(genqa_ann, arg_type)

            if gold_str!=ace_str or gold_str!=eeqa_str or gold_str!=genqa_str:
                ADD_SINGLE = True
                outdict['check_types'].append(arg_type)
                TYPE_CASES[arg_type] += 1
                if TYPE_CASES[arg_type] >= SAMPLE_NUM:
                    CAND_TYPES.remove(arg_type)

        if ADD_SINGLE:
            outdict['ACE'] = ace_ann
            outdict['EEQA'] = eeqa_ann
            outdict['GENQA'] = genqa_ann
            outdict['GOLD'] = gold_ann
            outpath = os.path.join(single_folder, "%s.json"%sample_id)
            # with open(outpath, 'w') as f:
            #     json.dump(outdict, f, indent=4)

    print(TYPE_CASES)





            





    






if __name__ == '__main__':
    main()
