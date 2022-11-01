"""
    This script is used to process BioNLP Shared Task format data to structured json data.
    Each line in the output file is a json dict. 
"""
import os
import glob
import warnings
from collections import defaultdict
import json
import unicodedata
import random

def parse_entity_line(line, context):
    items = line.split('\t')
    entity_id = items[0]
    entity_type, pos_spans = items[1].split(' ', 1)
    entity_text = items[2]
    pos_spans = pos_spans.split(';')
    start = []
    text = []
    for pos_span in pos_spans:
        # for discontinuous spans, brat splits the offsets, but not the text
        # e.g, T18	Drug 158 169;182 198	recombinant interferon alpha
        # we want to store the start position as (158,182) and text as (recombinant, interferon alpha)
        # to benefit some methods like seq-labelling based ones.
        pos_start, pos_end = pos_span.split(' ')
        pos_start = int(pos_start)
        pos_end = int(pos_end)
        start.append(pos_start)
        if not text:
            s = entity_text[:pos_end-pos_start]
        else:
            s = entity_text[len(" ".join(text))+1:len(" ".join(text))+1+pos_end-pos_start]
        text.append(s)
        assert(context[pos_start:pos_end]==s), "discontinous span dismatch%s, %s, %s"%(s, context[pos_start:pos_end], context)


    return {
            "id": entity_id,
            "type": entity_type,
            "text":text,
            "start":start,
        }
    
def parse_event_line(line):
    items = line.strip().split('\t')
    event_id = items[0]
    arg_items = items[1].split(' ')
    event_type, trigger_id = arg_items[0].split(':')
    args = []
    for arg_item in arg_items[1:]:
        arg_type, arg_id = arg_item.split(':')
        args.append((arg_type, arg_id))

    return {
            "id":event_id,
            "type":event_type,
            "trigger_id":trigger_id,
            "args": args
        }
    
def parse_attribute_line(line):
    items = line.strip().split('\t')
    attr_id = items[0]
    attr_items = items[1].split(' ')
    attr_type = attr_items[0]
    event_id = attr_items[1]
    attr_value = True
    if len(attr_items) == 3:
        attr_value = attr_items[2]

    return {
            "id":attr_id,
            "type":attr_type,
            "event_id":event_id,
            "value": attr_value,
            "text": [],
            "start": [],
            "entity_id":[]
        }

def parse_relation_line(line):
    items = line.strip().split('\t')
    rel_id = items[0]
    rel_type, arg1, arg2 = items[1].split(' ')
    arg1 = arg1.split(':')[1]
    arg2 = arg2.split(':')[1]

    return {
            "id":rel_id,
            "type":rel_type,
            "arg1": arg1,
            "arg2": arg2
    }

def get_default_event(events):
    count = 0
    default_ev = None
    for event_info in events.values():
        if len(event_info["args"]) == 0:
            default_ev = event_info["id"]
            count += 1

    if count > 1:
        warnings.warn("More than one event has no arguments! Can't allocate arguments by default!")
        default_ev = None

    return default_ev

def is_span_overlap(info1, info2):
    text1 = info1['text']
    start1 = info1['start']
    end1 = []
    for t,s in zip(text1, start1):
        end1.append(s + len(t))

    text2 = info2['text']
    start2 = info2['start']
    end2 = []
    for t,s in zip(text2, start2):
        end2.append(s + len(t))

    overlap = False
    for ks, ke in zip(start1, end1):
        for vs, ve in zip(start2, end2):
            if (ks >= vs and ks < ve) or (ke > vs and ke <= ve):
                overlap = True
                break

    return overlap

def construct_event(ann_path, context):
    error_cases = []

    PARENT_EVENTS = ["Adverse_event", "Potential_therapeutic_event"]
    PARENT_ARGS = ["Subject",  "Effect", 'Treatment']
    PARENT_TO_CHILD = {
        "Subject": ["Age", "Gender", "Population", "Race", "Sub-Disorder"],
        "Treatment": ["Drug", "Dosage", "Freq", "Route", "Time_elapsed", "Duration", "Treat-Disorder"]
    }
    CHILD_TO_PARENT = {}
    for p, c_list in PARENT_TO_CHILD.items():
        for c in c_list:
            CHILD_TO_PARENT[c] = p

    RENAME_CHILD = { # Used to rename the xx-Disorder to Disorder
        "Treat-Disorder": "Disorder",
        "Sub-Disorder": "Disorder"
    }

    CUE_TO_ATTR = {
        "Negation_cue": "Negated",
        "Speculation_cue": "Speculated",
        "Severity_cue": "Severity"
    }

    DEFAULT_CUE = {
        "Negation_cue": True,
        "Speculation_cue": True,
        "Severity_cue": "Medium"
    }


    entities = {}
    events = {} # {event_id: event_info}
    attributes = defaultdict(list) # {event_id: [attr_info]}
    relations = {} # {relation_id: relation_info}
    arg_to_event = {}  # {entity_id: event_id}
    doc_id = os.path.basename(ann_path).split('.')[0]

    # parse .ann file
    # store all entities into dict {"entity_id":str, "text":tuple, "start":tuple, "type":str}}
    with open(ann_path, "r", encoding="utf-8") as f:
        for line in f.readlines():
            if line.startswith('T'): # entity or trigger
                entity_info = parse_entity_line(line, context)
                entities[entity_info['id']] = entity_info  
            elif line.startswith('E'): # event
                ev_info = parse_event_line(line)
                events[ev_info['id']] = ev_info
                for _, arg_id in ev_info["args"]:
                    arg_to_event[arg_id] = ev_info["id"]
            elif line.startswith('A'): # attribute
                attr_info = parse_attribute_line(line)
                attributes[attr_info['event_id']].append(attr_info)
            elif line.startswith('R'): # relations
                rel_info = parse_relation_line(line)
                relations[rel_info['id']] = rel_info
            else:
                warnings.warn("unknown anntation types.%s"%line)
                error_cases.append("unknown anntation types: %s "%ann_path) 

    # get default event and check the number of no arg events
    default_event = get_default_event(events)

    # construct relations
    cue_to_event = {}
    main_to_events = defaultdict(list) # main arguments to events
    sub_to_main = {}
    cev_to_pev = {} # child event to parent event
    # explicitly linked binary relations
    for rel_id, rel_info in relations.items():
        if rel_info['type'] == 'has': 
            sub_to_main[rel_info['arg2']] = rel_info['arg1']
        elif rel_info['type'] == 'has_child':
            cev_to_pev[rel_info['arg2']] = rel_info['arg1']
        elif rel_info['type'] == 'has_cue':
            cue_to_event[rel_info['arg2']] = rel_info['arg1']

    # explicitly linked main arguments to events
    for event_id, event_info in events.items():
        args = event_info['args']
        for arg_id, ent_id in args:
            main_to_events[ent_id].append(event_id)
    
    # relations by default
    # child event to parent event
    for ev_id, ev_info in events.items():
        if ev_id not in cev_to_pev and ev_info['type'] == 'Combination':
            cand_prts = []
            for pev_id, pev_info in events.items():
                if pev_info['type'] in PARENT_EVENTS:
                    cand_prts.append(pev_id)
            if len(cand_prts) == 1:
                cev_to_pev[ev_id] = cand_prts[0]
            else:
                warnings.warn("unlinked child event %s in %s"%(ev_info['type'], doc_id))
                error_cases.append("unlinked child event %s: %s "%(ev_info['type'], ann_path))

    # link entities
    for ent_id, ent_info in entities.items():
        ent_type = ent_info['type']
        
        if ent_type in PARENT_ARGS: # main to event
            if ent_id not in main_to_events:
                if default_event:
                    main_to_events[ent_id].append(default_event)
                else:
                    warnings.warn("unlinked argument %s in %s"%(ent_type, doc_id))
                    error_cases.append("unlinked argument %s: %s "%(ent_type, ann_path))
        
        if ent_type in CHILD_TO_PARENT: # sub argument to main argument
            if ent_id not in sub_to_main:
                parent_type = CHILD_TO_PARENT[ent_type]
                # find overlaped parent
                found = False
                cand_prt = []
                for peid, pe_info in entities.items():
                    if pe_info['type'] == parent_type:
                        cand_prt.append(peid)
                        overlap = is_span_overlap(ent_info, pe_info)
                        if overlap:
                            sub_to_main[ent_id] = peid
                            found = True
                            break
                if not found and len(cand_prt) == 1:
                    sub_to_main[ent_id] = cand_prt[0]
                    found = True
                if not found:
                    # ignore those cases
                    # if ent_type != 'Sub-Disorder':
                    warnings.warn("unlinked subargument %s in %s"%(ent_type, doc_id))
                    error_cases.append("unlinked subargument %s: %s "%(ent_type, ann_path))
    

        if ent_type in CUE_TO_ATTR: # cue to event
            if ent_id not in cue_to_event:
                found = False
                cand_evs = []
                attr_type = CUE_TO_ATTR[ent_type]
                for ev_id in attributes:
                    ev_attrs = attributes[ev_id]
                    for attr_info in ev_attrs:
                        if attr_type == attr_info['type']:
                            cand_evs.append(ev_id)

                if len(cand_evs) == 1:
                    cue_to_event[ent_id] = cand_evs[0]
                    found = True
                elif len(cand_evs) == 0:
                    prt_evs = []
                    for ev_id, ev_info in events.items():
                        if ev_info['type'] not in ['Combination']:
                            prt_evs.append(ev_id)
                    if len(prt_evs) == 1:
                        cue_to_event[ent_id] = prt_evs[0]
                        found = True
                if not found:
                    # ignore those cases
                    warnings.warn("unlinked attribute %s in %s"%(ent_type, doc_id))
                    error_cases.append("unlinked attribute %s: %s "%(ent_type, ann_path))


    # build event structure
    outputs = []
    for event_id, ev_info in events.items():
        if ev_info['type'] not in PARENT_EVENTS:
            continue  # ensemble 'Combination' in parent event's 'Treatment'

        e = {}  # used to store event information and append to doc.event
        e["event_id"] = event_id
        e["event_type"] = ev_info['type']
        # add trigger
        trigger_id = ev_info['trigger_id']
        trigger_info = entities[trigger_id]
        e["Trigger"]= {
            "text": [trigger_info['text']],
            "start": [trigger_info['start']],
            "entity_id": [trigger_id]  # an event could only have one trigger
        }
        # add arguments
        # main arguments 
        for main_id, ev_ids in main_to_events.items():
            if event_id in ev_ids:
                main_info = entities[main_id]
                mtype = main_info['type']
                mtext = main_info['text']
                mstart = main_info['start']
                if mtype not in e:
                        e[mtype] = {
                            'text': [],
                            'start': [],
                            'entity_id': []
                        }
                e[mtype]['text'].append(mtext)
                e[mtype]['start'].append(mstart)
                e[mtype]['entity_id'].append(main_id)
                # sub arguments
                for sid, mid in sub_to_main.items():
                    if main_id == mid:
                        sub_info = entities[sid]
                        stype = sub_info['type']
                        stext = sub_info['text']
                        sstart = sub_info['start']
                        if stype in RENAME_CHILD:
                            stype = RENAME_CHILD[stype]
                        if stype not in e[mtype]:
                            e[mtype][stype] = {
                                'text': [],
                                'start': [],
                                'entity_id': []
                            }
                        e[mtype][stype]['text'].append(stext)
                        e[mtype][stype]['start'].append(sstart)
                        e[mtype][stype]['entity_id'].append(sid)
        
        # add sub-event: Combination
        for cev_id, pev_id in cev_to_pev.items():
            if pev_id == event_id:
                if 'Treatment' not in e:
                    e['Treatment'] = {
                        'text': [],
                        'start': [],
                        'entity_id': []
                    }
                if 'Combination' not in e['Treatment']:
                    e['Treatment']['Combination'] = []
                    # warnings.warn("A combination subevent has already existed! %s"%doc_id)
                    # error_cases.append("A combination subevent has already existed!: %s "%(a1_path))
                    # continue
                
                cev_info = events[cev_id]
                trigger_id = cev_info['trigger_id']
                trigger_info = entities[trigger_id]
                comb_event = {
                    'event_id': cev_info['id'],
                    'event_type': cev_info['type'],
                    'Trigger':{
                        "text": [trigger_info['text']],
                        "start": [trigger_info['start']],
                        "entity_id": [trigger_id] 
                    },
                    'Drug':{
                        'text': [],
                        'start': [],
                        'entity_id': []
                    }
                }
                # add Drug span
                for _, arg_id in cev_info['args']:
                    drug_info = entities[arg_id]
                    comb_event['Drug']['text'].append(drug_info['text'])
                    comb_event['Drug']['start'].append(drug_info['start'])
                    comb_event['Drug']['entity_id'].append(arg_id)

                e['Treatment']['Combination'].append(comb_event)
               

        # add attributes value
        # we only keep attribute value if related cue is annotated
        for cue_id, ev_id in cue_to_event.items():
            if ev_id == event_id:
                cue_info = entities[cue_id]
                attr_type = CUE_TO_ATTR[cue_info['type']]
                if attr_type not in e:
                    # find value
                    attr_value = None
                    for attr_info in attributes[event_id]:
                        if attr_info['type'] == attr_type:
                            attr_value = attr_info['value']
                    if not attr_value:
                        attr_value = DEFAULT_CUE[cue_info['type']]
                    e[attr_type] = {
                        'text': [],
                        'start': [],
                        'entity_id': [],
                        'value': attr_value
                    }
                e[attr_type]['text'].append(cue_info['text'])
                e[attr_type]['start'].append(cue_info['start'])
                e[attr_type]['entity_id'].append(cue_id)

        # append the event to the instance
        outputs.append(e)
    
    # with open("../data/json/error_cases.txt", 'a') as f:
    #     if error_cases:
    #         f.write('\n'.join(error_cases))
    #         f.write('\n')
    
    return outputs


def check_mult_event(events):
    """Multiple ADE/PTE, or ADE/PTE with Combination are considered multi events"""
    if len(events) > 1:
        return True
    elif len(events) == 1:
        for event_info in events:
            if 'Treatment' in event_info and 'Combination' in event_info['Treatment']:
                return True
    return False



def run(src_folder, subfolders):
    out_data = {}    
    
    for subfolder in subfolders:
        # print(subfolder)
        for txt_path in glob.glob(os.path.join(src_folder, subfolder, "*.txt")):
            # if '11144696_12' not in txt_path: continue

            ann_path = txt_path.replace(".txt", ".ann")

            sent_id = os.path.basename(txt_path).split('.')[0]
            with open(txt_path, "r") as f:
                context = f.read().rstrip()
                clean_txt = context.encode().decode('ascii', 'ignore')
                if clean_txt != context:
                    print("skip irregular text:%s in %s", (context, txt_path))  # skip non-ascii text
                    continue

            events = construct_event(ann_path, context)
            is_mult_event = check_mult_event(events)

            if sent_id not in out_data:
                out_data[sent_id] = {
                    "id": sent_id,
                    "context": context,
                    "is_mult_event": is_mult_event,
                    "annotations": [
                        {"events": events}
                    ]
                }
            else:
                out_data[sent_id]["is_mult_event"] = is_mult_event or out_data[sent_id]["is_mult_event"]
                out_data[sent_id]["annotations"].append({
                    "events": events
                })
    
    return out_data
                

    
def main():
    src_folder = "../data/clean"
    output_folder = "../data/json"
    subfolders = ['train', 'dev', 'test']

    for split in subfolders:
        out_data = run(src_folder, [split])
        with open(os.path.join(output_folder, split+".json"), 'w') as fout:
            for sent_id, data in out_data.items():
                out_str = json.dumps(data)
                fout.write(out_str+'\n')

        

    
    
    # train_list = []
    # dev_list = []
    # test_list = []
    # for subset in ['train_list', 'dev_list', 'test_list']:
    #     list_file = os.path.join("../data/clean/", subset+".txt")
    #     with open(list_file, "r") as f:
    #         outlist = eval(subset)
    #         outlist += "".join(f.readlines()).split('\n')

    # if not os.path.exists(output_folder):
    #     os.makedirs(output_folder)
    # with open(os.path.join(output_folder, "train.json"), 'w') as f_train:
    #     with open(os.path.join(output_folder, "dev.json"), 'w') as f_dev:
    #         with open(os.path.join(output_folder, "test.json"), 'w') as f_test:
    #             for sent_id, data in out_data.items():
    #                 if sent_id in train_list:
    #                     f_out = f_train
    #                 elif sent_id in dev_list:
    #                     f_out = f_dev
    #                 elif sent_id in test_list:
    #                     f_out = f_test
    #                 else:
    #                     raise Exception("Not find the file in either train/dev/test!")

    #                 if len(data['annotations']) > 1: # randomly shuffle duplicated annotations
    #                     random.shuffle(data['annotations'])
    #                 out_str = json.dumps(data)
    #                 f_out.write(out_str+'\n')

if __name__ == '__main__':
    main()
