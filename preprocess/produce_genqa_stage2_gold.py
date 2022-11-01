"""
Transfer json data to GenQA stage2 input format.
running environment: torch_transformer
"""
from ast import arguments
from tkinter import E
import spacy
from easydict import EasyDict as edict
import json
import re
import random
import os

# instance = {
#             "id": data.id+"_"+str(instance_id),
#             "context": data.context,
#             "question": QUESTION_TEMPLATES[TEMPLATE_ID],
#             "question_type": "Events",
#             "answers": ""
# }

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


def main():

    MAIN_ARGS = ["Subject", "Treatment"]
    MAIN_TO_SUB = {
        "Subject": ["Age", "Gender", "Population", "Race", "Disorder"],
        "Treatment": ["Drug", "Dosage", "Freq", "Route", "Time_elapsed", "Duration", "Disorder"],
    }
    splits = ["train", "dev", "test"]

    src_folder = "../data/json/"
    tgt_folder = "../data/gen_qa/stage2_gold"

    if not os.path.exists(tgt_folder):
        os.makedirs(tgt_folder)

    for TEMPLATE_ID in range(0, len(QUESTION_TEMPLATES)):
        for split in splits:

            src_file = os.path.join(src_folder, "%s.json"%split)
            tgt_file = os.path.join(tgt_folder, "%s_%d.json" % (split, TEMPLATE_ID))

            output = {
                "version": "v2.0",
                "data": []
            }

            instance_id = 0
            with open(src_file, "r", encoding='utf-8') as f:
                for line in f.readlines():

                    data = json.loads(line)
                    data = edict(data)

                    # ann_id = random.randint(0, len(data.annotations)-1)
                    annotation = data.annotations[0]

                    for event in annotation.events:  
                        event_type = event.event_type 
                        event_type = " ".join(event_type.split("_"))
                        trigger_text = event.Trigger.text[0][0]

                        # Convert arguments
                        for main_role in MAIN_ARGS:
                            if main_role in event:
                                main_arg = event[main_role] 
                                main_arg_text = []
                                for ent in main_arg.text:
                                    for span in ent:
                                        main_arg_text.append(span)
                                main_arg_text = "; ".join(main_arg_text)
                                for sub_role in MAIN_TO_SUB[main_role]:
                                    if sub_role in main_arg:
                                        sub_arg = main_arg[sub_role]
                                        answer = []
                                        for ent in sub_arg.text:
                                            for span in ent:
                                                answer.append(span)
                                        answer = "; ".join(answer)
                                    else:
                                        answer = ""
                                    question = QUESTION_TEMPLATES[TEMPLATE_ID]
                                    sub_arg_type = ".".join([main_role, sub_role])
                                    sub_arg_query = QUERIES[sub_arg_type][:-1]
                                    question = question.replace("[EVENT_TYPE]", " ".join(event_type.split('_')).lower())
                                    question = question.replace("[MAIN_ARG_TYPE]", main_role)
                                    question = question.replace("[MAIN_ARG_TEXT]", main_arg_text)
                                    question = question.replace("[SUB_ARG_TYPE]", sub_arg_type)
                                    question = question.replace("[SUB_ARG_QUERY]", sub_arg_query)
                                    question_type = event.event_type +"."+main_role+"."+sub_role
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
                                    if "Combination" in main_arg:
                                        answer = []
                                        for comb in main_arg.Combination:
                                            if "Drug" in comb:
                                                for ent in comb.Drug.text:
                                                    for span in ent:
                                                        answer.append(span)
                                        answer = "; ".join(answer)
                                    else:
                                        answer = ""
                                    question = QUESTION_TEMPLATES[TEMPLATE_ID]
                                    question = question.replace("[EVENT_TYPE]", " ".join(event_type.split('_')).lower())
                                    question = question.replace("[MAIN_ARG_TYPE]", main_role)
                                    question = question.replace("[MAIN_ARG_TEXT]", main_arg_text)
                                    question = question.replace("[SUB_ARG_TYPE]", "Combination.Drug")
                                    question = question.replace("[SUB_ARG_QUERY]", QUERIES["Combination.Drug"][:-1])
                                    question_type = event.event_type +".Combination.Drug"
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

