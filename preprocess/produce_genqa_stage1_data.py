"""
Transfer json data to GenQA stage1 input format.
running environment: torch_transformer
"""
from ast import arguments
from tkinter import E
import spacy
from easydict import EasyDict as edict
import json
import os
import re
import random


QUESTION_TEMPLATES = [
    "What are the events?"
]

def main():
    TEMPLATE_ID = 0
    ROLES = ["Subject", "Treatment", "Effect"]
    splits = ["train", "dev", "test"]

    src_folder = "../data/json/"
    tgt_folder = "../data/gen_qa/stage1"

    if not os.path.exists(tgt_folder):
        os.makedirs(tgt_folder)

    for TEMPLATE_ID in range(0, len(QUESTION_TEMPLATES)):
        for split in splits:

            src_file = os.path.join(src_folder, "%s.json"%split)
            tgt_file = os.path.join(tgt_folder, "%s_%d.json" % (split, TEMPLATE_ID))

            output = {
                "version": "v1.0",
                "data": []
            }

            instance_id = 0
            with open(src_file, "r", encoding='utf-8') as f:
                for line in f.readlines():

                    data = json.loads(line)
                    data = edict(data)
                    instance = {
                                "id": data.id+"_"+str(instance_id),
                                "context": data.context,
                                "question": QUESTION_TEMPLATES[TEMPLATE_ID],
                                "question_type": "Events",
                                "answers": ""
                    }
                    # ann_id = random.randint(0, len(data.annotations)-1)
                    annotation = data.annotations[0]

                    ans_str = ""
                    for event in annotation.events:  
                        event_type = event.event_type 
                        event_type = " ".join(event_type.split("_"))
                        ans_str += "[%s] "%event_type
                        # Convert trigger
                        # we ignore multi span/discontinuous span cases for trigger (usually won't happen actually)
                        # furthermore, EEQA only uses the first token of the trigger
                        trigger_text = event.Trigger.text[0][0]
                        ans_str += "%s "%trigger_text

                        # Convert arguments
                        for role in ROLES:
                            if role in event:
                                argument = event[role] # example: {"text": [["the concurrent use of 5-FU and warfarin"]], "start": [[87]], "entity_id": ["T6"]}
                                # for arguments, we temporally consider each span and each discontinuous part of a span as an independent span
                                text = []
                                for lt in argument.text: # for each span in a multi-span argument
                                    for t in lt: # for each discontinuous part of a argument span
                                        text.append(t)
                                text = "; ".join(text)
                                ans_str += "[%s] %s "%(role, text)
                    ans_str = ans_str.strip()
                    instance['answers'] = ans_str
                    output["data"].append(instance)
                    instance_id += 1

            with open(tgt_file, "w", encoding='utf-8') as f:
                json.dump(output, f)
            

if __name__ == '__main__':
    main()

