"""
Transfer stage1 output to stage2 input.
"""
from ast import arguments
from tkinter import E
import spacy
from easydict import EasyDict as edict
import json
import re
import random
from collections import defaultdict
import os

QUESTION_TEMPLATES = [
    "[SUB_ARG_TYPE]",
    "[SUB_ARG_TYPE] in [EVENT_TYPE]",
    "[SUB_ARG_TYPE] in [MAIN_ARG_TEXT]",
    "[EVENT_TYPE]. [MAIN_ARG_TYPE], [MAIN_ARG_TEXT]. [SUB_ARG_TYPE]?",
    "[SUB_ARG_QUERY]?",
    "[SUB_ARG_QUERY] in [EVENT_TYPE]?",
    "[SUB_ARG_QUERY] in [MAIN_ARG_TEXT]?",
    "[EVENT_TYPE]. [MAIN_ARG_TYPE], [MAIN_ARG_TEXT]. [SUB_ARG_QUERY]?"
]

QUERIES = {
    "Subject.Disorder": "What is the disorder of the subject?",
    "Subject.Age": "What is the age of the subject?",
    "Subject.Gender": "What is the gender of the subject?",
    "Subject.Population":"What is the number of subjects?",
    "Subject.Race":"What is the race of the subject?",
    "Treatment.Drug":"What are the drugs used in the treatment?",
    "Treatment.Disorder":"What is the disorder targeted by the treatment?",
    "Treatment.Route":"What is the route of the treatment?",
    "Treatment.Dosage":"What is the dosage of the treatment?",
    "Treatment.Time_elapsed":"How long has elapsed from the treatment to the occurence of the event?",
    "Treatment.Duration":"How long did the treatment last?",
    "Treatment.Freq":"What is the frequency of the treatment?",
    "Combination.Drug":"What are the drugs used in combination?"
}

def parse_entities(text):
        EVENT_TYPES = ['Adverse event', 'Potential therapeutic event']
        MAIN_ARGS = ['Subject', 'Treatment', 'Effect']
        pattern = re.compile(r'\[.*?\][^\[]*')
        entities = defaultdict(list)
        events = []
        event = None
        for ent_str in re.findall(pattern, text):
            k, v = ent_str.split(']', 1)
            k = k.replace('[','').strip()
            v = v.strip()
            if k in EVENT_TYPES:
                if event is not None:
                    events.append(event)
                event = {
                    'type': "_".join(k.split(' ')),
                    'Trigger': v,
                }
            elif event and k in MAIN_ARGS:
                if k not in event:
                    event[k] = []
                if v:
                    spans = v.split(";")
                for span in spans:
                    event[k].append(span.strip())
            else:
                continue
        if event is not None:
            events.append(event)

        return events

def read_pred_result(pred_file):
    output = {}
    with open(pred_file, 'r') as f:
        pred_rst = json.load(f)
        predictions = pred_rst['predictions']
        for instance in predictions:
            ins_id = "_".join(instance['id'].split('_')[:-1])
            pred_text = instance['prediction_text']
            pred_events = parse_entities(pred_text)
            output[ins_id] = pred_events
    return output
    

def main():

    MAIN_ARGS = ["Subject", "Treatment"]
    MAIN_TO_SUB = {
        "Subject": ["Age", "Gender", "Population", "Race", "Disorder"],
        "Treatment": ["Drug", "Dosage", "Freq", "Route", "Time_elapsed", "Duration", "Disorder"],
    }
    model = "SciFive-base-PMC"
    

    

    for TEMPLATE_ID in range(0, len(QUESTION_TEMPLATES)):
        
        src_file = "../data/json/test.json"
        pred_file = "model/stage1/%s/predict_outputs.json"%model
        tgt_folder = "data/stage2_pred/%s/"%model
        if not os.path.exists(tgt_folder):
            os.makedirs(tgt_folder)
        tgt_file = os.path.join(tgt_folder, "pred_test_%d.json"%TEMPLATE_ID)

        pred_rst = read_pred_result(pred_file)

        output = {
            "version": "v2.0",
            "data": []
        }

        instance_id = 0
        with open(src_file, "r", encoding='utf-8') as f:
            for line in f.readlines():

                data = json.loads(line)
                data = edict(data)

                pred_events = pred_rst[data.id]

                for event in pred_events:
                    # Convert arguments
                    event_type = event['type']
                    for main_role in MAIN_ARGS:
                        if main_role in event:
                            main_arg = event[main_role] 
                            main_arg_text = "; ".join(main_arg)
                            for sub_role in MAIN_TO_SUB[main_role]:
                                answer = ""
                                question = QUESTION_TEMPLATES[TEMPLATE_ID]
                                sub_arg_type = ".".join([main_role, sub_role])
                                sub_arg_query = QUERIES[sub_arg_type][:-1]
                                question = question.replace("[EVENT_TYPE]", " ".join(event_type.split('_')).lower())
                                question = question.replace("[MAIN_ARG_TYPE]", main_role)
                                question = question.replace("[MAIN_ARG_TEXT]", main_arg_text)
                                question = question.replace("[SUB_ARG_TYPE]", sub_arg_type)
                                question = question.replace("[SUB_ARG_QUERY]", sub_arg_query)
                                question_type = event_type +"."+main_role+"."+sub_role
                                instance = {
                                    "id": data.id+"_"+str(instance_id),
                                    "context": data.context,
                                    "question": question,
                                    "question_type": question_type,
                                    "answers": answer
                                }
                                output["data"].append(instance)
                                instance_id += 1
                            # for combination
                            if main_role == 'Treatment':
                                answer = ""
                                question = QUESTION_TEMPLATES[TEMPLATE_ID]
                                question = question.replace("[EVENT_TYPE]", " ".join(event_type.split('_')).lower())
                                question = question.replace("[MAIN_ARG_TYPE]", main_role)
                                question = question.replace("[MAIN_ARG_TEXT]", main_arg_text)
                                question = question.replace("[SUB_ARG_TYPE]", "Combination.Drug")
                                question = question.replace("[SUB_ARG_QUERY]", QUERIES["Combination.Drug"][:-1])
                                question_type = event_type +".Combination.Drug"
                                instance = {
                                    "id": data.id+"_"+str(instance_id),
                                    "context": data.context,
                                    "question": question,
                                    "question_type": question_type,
                                    "answers": answer
                                }
                                output["data"].append(instance)
                                instance_id += 1

            with open(tgt_file, "w", encoding='utf-8') as f:
                json.dump(output, f)
           

if __name__ == '__main__':
    main()

