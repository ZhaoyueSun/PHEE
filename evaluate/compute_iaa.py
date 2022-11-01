
from re import T
import sys
import os
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('.'))
from preprocess.transfer_to_json import run
from phee_metric import compute_metric
import json
from collections import defaultdict

def transfer_to_json(subset):
    src_folder = "../data/raw/"
    output_folder = "./iaa_data/"

    # print(os.path.abspath("./iaa_data"))
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    out_data = run(src_folder, subfolders=[subset])


    with open(os.path.join(output_folder, subset+".json"), 'w') as f:
        for sent_id, data in out_data.items():
            out_str = json.dumps(data)
            f.write(out_str+'\n')

def get_entities(texts):
    output = []
    # flat all entities
    for spans in texts:
        for span in spans:
            output.append(span)

    return output

def get_event_entities(events):
    MAIN_ARGS = ['Subject', 'Treatment', 'Effect']
    MAIN_TO_CHILD = {
        "Subject": ["Age", "Gender", "Population", "Race", "Disorder"],
        "Treatment": ["Drug", "Dosage", "Freq", "Route", "Time_elapsed", "Duration", "Disorder"],
        "Effect": []
    }
    ATTRIBUTES = ['Speculation', 'Negation', 'Severity']

    event_entities = defaultdict(list)
    for event in events:
        event_type = event['event_type']
        # trigger 
        if 'Trigger' in event:
            ent_type = event_type + ".Trigger"
            entities = get_entities(event['Trigger']['text'])
            for ent in entities:
                event_entities[ent_type].append(ent)
        # main args
        for main_arg in MAIN_ARGS:
            if main_arg in event:
                ent_type = event_type + "." + main_arg
                entities = get_entities(event[main_arg]['text'])
                for ent in entities:
                    event_entities[ent_type].append(ent)
                # sub args
                for sub_arg in MAIN_TO_CHILD[main_arg]:
                    if sub_arg in event[main_arg]:
                        ent_type = event_type + "." + main_arg + "." + sub_arg
                        entities = get_entities(event[main_arg][sub_arg]['text'])
                        for ent in entities:
                            event_entities[ent_type].append(ent)
                # Combination
                if main_arg == 'Treatment' and 'Combination' in event[main_arg]:
                    for sub_event in event[main_arg]['Combination']:
                        if 'Trigger' in sub_event:
                            ent_type = event_type + ".Combination.Trigger"
                            entities = get_entities(sub_event['Trigger']['text'])
                            for ent in entities:
                                event_entities[ent_type].append(ent)
                        if 'Drug' in sub_event:
                            ent_type = event_type + ".Combination.Drug"
                            entities = get_entities(sub_event['Drug']['text'])
                            for ent in entities:
                                event_entities[ent_type].append(ent)

        for attr in ATTRIBUTES:
            if attr in event:
                ent_type = event_type + "." + attr
                entities = get_entities(event[attr]['text'])
                for ent in entities:
                    event_entities[ent_type].append(ent)

    return event_entities


                

def compute_iaa():
    
    src_folder = "./iaa_data/"
    dup1_data = []
    with open(os.path.join(src_folder, "duplicate1.json"), "r") as f:
        for line in f.readlines():
            dup1_data.append(json.loads(line))
    dup2_data = []
    with open(os.path.join(src_folder, "duplicate2.json"), "r") as f:
        for line in f.readlines():
            dup2_data.append(json.loads(line))
    
    assert(len(dup1_data) == len(dup2_data))

    instances = []
    for data1, data2 in zip(dup1_data, dup2_data):
        # print(data1)
        sent_id = data1['id']
        event1 = data1['annotations'][0]['events']
        event1_entities = get_event_entities(event1)        
        event2 = data2['annotations'][0]['events']
        event2_entities = get_event_entities(event2)

        type_keys = list(set(list(event1_entities.keys()) + list(event2_entities.keys())))
        for type_key in type_keys:
            instance = {
                'id' : sent_id,
                'type': type_key, 
                'predictions': event1_entities[type_key],
                'golds': event2_entities[type_key] # for fit the format designed for multiple golds
            }
            instances.append(instance)

    scores = compute_metric(instances)
    out_file = os.path.join(src_folder, "iaa_score.json")
    with open(out_file, 'w') as f:
        json.dump(scores, f, indent=4)

    

        






if __name__ == '__main__':
    transfer_to_json(subset='duplicate1')
    transfer_to_json(subset='duplicate2')
    compute_iaa()