from importlib.resources import path
import json
from collections import defaultdict
from operator import mul
import os
import glob
import random
import shutil
from xml.etree.ElementInclude import include
import string
import re

def get_event_distrib():
    """
    count the number of events of each type in different datasets.
    """
    counts = {
        "sentence": defaultdict(int),
        "Adverse_event": defaultdict(int),
        "Potential_therapeutic_event": defaultdict(int),
        "multi_event": defaultdict(int)
    }

    folder = "../data/json/"
    splits = ["train.json", "dev.json", "test.json"]

    for split in splits:
        file_path = os.path.join(folder, split)
        with open(file_path, "r") as f:
            for line in f.readlines():
                data = json.loads(line)
                events = data['annotations'][0]['events']
                if len(events) > 1:
                    counts['multi_event'][split] += 1
                counts['sentence'][split] += 1
                for event in events:
                    counts[event['event_type']][split] += 1
    print(counts)


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

def get_tokens(s):
    return _normalize_answer(s).split()

def get_arguments_num():
    PARENT_ARGS = ['Subject', "Effect", 'Treatment'] 
    PARENT_TO_CHILD = {
        "Subject": ["Race", "Age", "Gender", "Population", "Sub_Disorder"],
        "Treatment": ["Duration", "Time_elapsed","Route","Freq","Dosage", "Treat_Disorder", "Drug"],
    }
    in_sent = defaultdict(int)
    spans = defaultdict(int)
    tokens = defaultdict(int)


    folder = "../data/json/"
    splits = ["train.json", "dev.json", "test.json"]

    for split in splits:
        file_path = os.path.join(folder, split)
        with open(file_path, "r") as f:
            for line in f.readlines():
                data = json.loads(line)
                events = data['annotations'][0]['events']
                for event in events:
                    for main_arg in PARENT_ARGS:
                        if main_arg in event:
                            in_sent[main_arg] += 1
                            spans[main_arg] += sum([len(x) for x in event[main_arg]['text']])
                            tokens[main_arg] += sum([len(get_tokens(y)) for x in event[main_arg]['text'] for y in x])

                    
    print(in_sent)
    print(spans)
    print(tokens)


def get_subargs_num():
     
    PARENT_TO_CHILD = {
        "Subject": ["Race", "Age", "Gender", "Population", "Disorder"],
        "Treatment": ["Duration", "Time_elapsed","Route","Freq","Dosage", "Disorder", "Drug"],
    }
    
    counts = {
        'Subject': defaultdict(int),
        'Treatment': defaultdict(int)
    }

    folder = "../data/json/"
    splits = ["train.json", "dev.json", "test.json"]

    for split in splits:
        file_path = os.path.join(folder, split)
        with open(file_path, "r") as f:
            for line in f.readlines():
                data = json.loads(line)
                events = data['annotations'][0]['events']
                for event in events:
                    for main_arg in PARENT_TO_CHILD:
                        if main_arg in event:
                            for sub_arg in PARENT_TO_CHILD[main_arg]:
                                if sub_arg in event[main_arg]:
                                    counts[main_arg][sub_arg] += len(event[main_arg][sub_arg]['text'])

                    
    print(counts)

def get_attributes_num():

    ATTRIBUTES = ["Speculated", "Negated", "Severity"]
    counts = defaultdict(int)
    folder = "../data/json/"
    splits = ["train.json", "dev.json", "test.json"]

    for split in splits:
        file_path = os.path.join(folder, split)
        with open(file_path, "r") as f:
            for line in f.readlines():
                data = json.loads(line)
                events = data['annotations'][0]['events']
                for event in events:
                    for attr in ATTRIBUTES:
                        if attr in event:
                            counts[attr] += 1

                    
    print(counts)


def get_inconsistent_samples(query_main, query_sub):
    PARENT_TO_CHILD = {
        "Subject": ["Race", "Age", "Gender", "Population", "Disorder"],
        "Treatment": ["Duration", "Time_elapsed","Route","Freq","Dosage", "Disorder", "Drug"],
    }

    dup1_file = "../evaluate/iaa_data/duplicate1.json"
    dup2_file = "../evaluate/iaa_data/duplicate2.json"

    compare_dict = defaultdict(dict)

    with open(dup1_file, "r") as f:
        for line in f.readlines():
            data = json.loads(line)
            id = data['id']
            events = data['annotations'][0]['events']
            for event in events:
                if query_main in event:
                        if query_sub in event[query_main]:
                                compare_dict[id]["ann1"] = event[query_main][query_sub]['text']
                                break
    
    with open(dup2_file, "r") as f:
        for line in f.readlines():
            data = json.loads(line)
            id = data['id']
            events = data['annotations'][0]['events']
            for event in events:
                if query_main in event:
                        if query_sub in event[query_main]:
                                compare_dict[id]["ann2"] = event[query_main][query_sub]['text']
                                break

    dif_ids = list(compare_dict.keys())
    # random.shuffle(dif_ids)
    dif_num = 0

    for id in dif_ids:
        a1_text = compare_dict[id]["ann1"] if "ann1" in compare_dict[id] else ""
        a2_text = compare_dict[id]["ann2"] if "ann2" in compare_dict[id] else ""
        if a1_text != a2_text:
            print("%s: %s; %s"%(id, a1_text, a2_text))
            dif_num += 1

        # if dif_num > 10:
        #     break



if __name__ == '__main__':
    # get_event_distrib()
    # get_arguments_num()
    # get_subargs_num()
    # get_attributes_num()
    get_inconsistent_samples("Subject", "Disorder")
