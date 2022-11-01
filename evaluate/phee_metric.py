import collections
import re
import string
from collections import defaultdict
from typing import OrderedDict
import warnings
import copy

# def _normalize_answer(s):
#     """Lower text and remove punctuation, articles and extra whitespace."""

#     def remove_articles(text):
#         regex = re.compile(r"\b(a|an|the)\b", re.UNICODE)
#         return re.sub(regex, " ", text)

#     def white_space_fix(text):
#         return " ".join(text.split())

#     def remove_punc(text):
#         exclude = set(string.punctuation)
#         return "".join(ch for ch in text if ch not in exclude)

#     def lower(text):
#         return text.lower()

#     return white_space_fix(remove_articles(remove_punc(lower(s))))

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


def _get_tokens(s):
    if not s:
        return []
    return s.split()


def _compute_instance_token_stat(pred, gold):
    """
    @return:
        num_same, pred_n, gold_n
    """
    gold_tokens = []
    pred_tokens = []
    for span in gold:
        gold_tokens += _get_tokens(span)
    for span in pred:
        pred_tokens += _get_tokens(span)

    gold_n = len(gold_tokens)
    pred_n = len(pred_tokens)

    common = collections.Counter(gold_tokens) & collections.Counter(pred_tokens)
    num_same = sum(common.values())

    return num_same, pred_n, gold_n

def _merge_cls_stats(cls_stats):
    # merge cls_stats
    merge_cls_stats = defaultdict(lambda: defaultdict(int))
    main_args = ['Subject', 'Treatment', 'Effect']
    attr_args = ['Speculation', 'Negation', 'Severity']

    for arg_type in cls_stats:
        for stat_name in cls_stats[arg_type]:
            arg_type_items  = arg_type.split('.')
            if 'Trigger' in arg_type: # trigger
                merge_cls_stats['Trigger'][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats['Overall'][stat_name] += cls_stats[arg_type][stat_name]
            elif len(arg_type_items) == 2 and arg_type_items[1] in main_args: # main arg
                merge_cls_stats['MainArgs'][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats['Arguments'][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats[arg_type_items[1]][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats['Overall'][stat_name] += cls_stats[arg_type][stat_name]
            elif len(arg_type_items) == 3: # sub arg
                merge_cls_stats['SubArgs'][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats['Arguments'][stat_name] += cls_stats[arg_type][stat_name]
                sub_type = ".".join(arg_type_items[1:])
                merge_cls_stats[sub_type][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats['Overall'][stat_name] += cls_stats[arg_type][stat_name]
            elif len(arg_type_items) == 2 and arg_type_items[1] in attr_args: # attribute
                merge_cls_stats['Attributes'][stat_name] += cls_stats[arg_type][stat_name]
                merge_cls_stats['Overall'][stat_name] += cls_stats[arg_type][stat_name]
            else:
                warnings.warn("Unknown arg type %:"%arg_type)

    cls_stats.update(merge_cls_stats)
    return cls_stats

def _get_stats(instances):
    stats = defaultdict(lambda: defaultdict(int))

    # get classification results
    for instance in instances:
        ent_type = instance['type']
        preds = instance['predictions']
        golds = instance['golds']

        preds = [_normalize_answer(x) for x in preds]
        golds = [_normalize_answer(x) for x in golds]

        # compute token-F1
        ins_tp_n, ins_pred_n, ins_gold_n = _compute_instance_token_stat(preds, golds)
        stats[ent_type]["token_tp_n"] += ins_tp_n
        stats[ent_type]["pred_token_n"] += ins_pred_n
        stats[ent_type]["gold_token_n"] += ins_gold_n

        # compute EM-F1
        # pred_arg_n
        stats[ent_type]["pred_arg_n"] += len(preds)
        # gold_arg_n
        stats[ent_type]["gold_arg_n"] += len(golds)
        # tp_n
        common = collections.Counter(preds) & collections.Counter(golds)
        stats[ent_type]["arg_tp_n"] += sum(common.values())

    return stats

def _merge_idt_instances(instances):
    main_args = ['Subject', 'Treatment', 'Effect']
    attr_args = ['Speculation', 'Negation', 'Severity']
    pred_dict =  defaultdict(lambda: defaultdict(list))
    golds_dict = defaultdict(lambda: defaultdict(list))
    for instance in instances:
        id = instance['id']
        arg_type = instance['type']
        preds = instance['predictions']
        golds = instance['golds']
        arg_type_items = arg_type.split('.')
        if 'Trigger' in arg_type: # trigger
            mtype = arg_type.split('.')[0]+".Trigger"
        elif len(arg_type_items) == 2 and arg_type_items[1] in main_args: # main arg
            mtype = arg_type.split('.')[0]+".MainArg"
        elif len(arg_type_items) == 3: # sub arg
            mtype = arg_type.split('.')[0] + ".SubArg"
        elif len(arg_type_items) == 2 and arg_type_items[1] in attr_args: # attribute
            mtype = arg_type.split('.')[0] + ".Attribute"
        else:
            warnings.warn("Unknown arg type %:"%arg_type)
        pred_dict[id][mtype].append(preds)
        golds_dict[id][mtype].append(golds)

    merge_instances = []
    for id in pred_dict:
        ins_pred = pred_dict[id]
        ins_golds = golds_dict[id]
        mtypes = list(set(list(ins_pred.keys()) + list(ins_golds.keys())))
        for mtype in mtypes:
            ins = {
                'id': id,
                'type': mtype,
                'predictions': [],
                'golds':[]
            }
            if mtype in ins_pred:
                for spans in ins_pred[mtype]:
                    for span in spans:
                        ins['predictions'].append(span)
            if mtype in ins_golds:
                for spans in ins_golds[mtype]:
                    for span in spans:
                        ins['golds'].append(span)
            merge_instances.append(ins)
    
    return merge_instances

def _merge_idt_stats(idt_stats):
    merge_idt_stats = defaultdict(lambda: defaultdict(int))

    for arg_type in idt_stats:
        for stat_name in idt_stats[arg_type]:
            mtype  = arg_type.split('.')[-1]
            merge_idt_stats['Overall'][stat_name] += idt_stats[arg_type][stat_name]
            merge_idt_stats[mtype][stat_name] += idt_stats[arg_type][stat_name]


    idt_stats.update(merge_idt_stats)
    return idt_stats

def compute_metric(instances):
    """
    instances = [{
        'id': (str)instance_id, 
        'type': (str) entity type,
        'predictions': (list) spans,
        'golds': (list) spans
    }]
    """
    results = collections.OrderedDict()
    
    # get classification results
    cls_stats = _get_stats(instances)
    cls_stats = _merge_cls_stats(cls_stats)
    cls_keys = list(cls_stats.keys())
    cls_keys.sort(key=lambda x:len(x.split('.')))
    
    for arg_type in cls_keys:
        em_p, em_r, em_f1, micro_p, micro_r, micro_f1 = 0, 0, 0, 0, 0, 0

        if cls_stats[arg_type]["pred_arg_n"] != 0: 
            em_p = 100.0 * cls_stats[arg_type]["arg_tp_n"] / cls_stats[arg_type]["pred_arg_n"]
        else: 
            em_p = 0
        if cls_stats[arg_type]["pred_token_n"] != 0: 
            micro_p = 100.0 * cls_stats[arg_type]["token_tp_n"] / cls_stats[arg_type]["pred_token_n"]
        else: 
            micro_p = 0

        if cls_stats[arg_type]["gold_arg_n"] != 0: 
            em_r = 100.0 * cls_stats[arg_type]["arg_tp_n"] / cls_stats[arg_type]["gold_arg_n"]
        else: 
            em_r = 0
        if cls_stats[arg_type]["gold_token_n"] != 0: 
            micro_r = 100.0 * cls_stats[arg_type]["token_tp_n"] / cls_stats[arg_type]["gold_token_n"]
        else: 
            micro_r = 0

        if em_p or em_r: em_f1 = 2 * em_p * em_r / (em_p + em_r)
        else: em_f1 = 0
        if micro_p or micro_r: micro_f1 = 2 * micro_p * micro_r/ (micro_p + micro_r)
        else: micro_f1 = 0

        for t in ["em_p", "em_r", "em_f1", "micro_p", "micro_r", "micro_f1"]:
            rst_title = "_".join(['CLS', arg_type, t.upper()])
            results[rst_title] = eval(t)

    # get identification results
    idt_instances = _merge_idt_instances(instances)
    idt_stats = _get_stats(idt_instances)
    idt_stats = _merge_idt_stats(idt_stats)
    idt_keys = list(idt_stats.keys())
    idt_keys.sort(key=lambda x:len(x.split('.')))
    
    for arg_type in idt_keys:
        em_p, em_r, em_f1, micro_p, micro_r, micro_f1 = 0, 0, 0, 0, 0, 0

        if idt_stats[arg_type]["pred_arg_n"] != 0: 
            em_p = 100.0 * idt_stats[arg_type]["arg_tp_n"] / idt_stats[arg_type]["pred_arg_n"]
        else: 
            em_p = 0
        if idt_stats[arg_type]["pred_token_n"] != 0: 
            micro_p = 100.0 * idt_stats[arg_type]["token_tp_n"] / idt_stats[arg_type]["pred_token_n"]
        else: 
            micro_p = 0

        if idt_stats[arg_type]["gold_arg_n"] != 0: 
            em_r = 100.0 * idt_stats[arg_type]["arg_tp_n"] / idt_stats[arg_type]["gold_arg_n"]
        else: 
            em_r = 0
        if idt_stats[arg_type]["gold_token_n"] != 0: 
            micro_r = 100.0 * idt_stats[arg_type]["token_tp_n"] / idt_stats[arg_type]["gold_token_n"]
        else: 
            micro_r = 0

        if em_p or em_r: em_f1 = 2 * em_p * em_r / (em_p + em_r)
        else: em_f1 = 0
        if micro_p or micro_r: micro_f1 = 2 * micro_p * micro_r/ (micro_p + micro_r)
        else: micro_f1 = 0

        for t in ["em_p", "em_r", "em_f1", "micro_p", "micro_r", "micro_f1"]:
            rst_title = "_".join(['IDT', arg_type, t.upper()])
            results[rst_title] = eval(t)

    return results
    
    

