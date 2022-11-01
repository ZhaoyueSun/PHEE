"""Run QA model to extract arguments."""

from __future__ import absolute_import, division, print_function

import argparse
import collections
import json
import logging
import math
import os
import random
import time
import re
import string
import sys
from io import open
import copy
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('.'))
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

from evaluate.phee_metric import compute_metric
from easydict import EasyDict as edict 
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
from pytorch_pretrained_bert.file_utils import PYTORCH_PRETRAINED_BERT_CACHE, WEIGHTS_NAME, CONFIG_NAME
from pytorch_pretrained_bert.modeling import BertForQuestionAnswering, BertForQuestionAnswering_withIfTriggerEmbedding
from pytorch_pretrained_bert.optimization import BertAdam, warmup_linear
from pytorch_pretrained_bert.tokenization import BertTokenizer

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

max_seq_length = 220

class AceExample(object):
    """
    A single training/test example for the ace dataset.
    """

    def __init__(self, sentence, events, s_start, instance_id):
        self.sentence = sentence
        self.events = events
        self.s_start = s_start
        self.instance_id = instance_id

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        s = ""
        s += "event sentence: %s" % (" ".join(self.sentence))
        event_triggers = []
        for event in self.events:
            if event:
                event_triggers.append(self.sentence[event[0][0] - self.s_start])
                event_triggers.append(event[0][-1])
                event_triggers.append(str(event[0][0] - self.s_start))
                event_triggers.append("|")
        s += " ||| event triggers: %s" % (" ".join(event_triggers))
        return s


class InputFeatures(object):
    """A single set of features of data."""

    def __init__(self, example_id, tokens, token_to_orig_map, input_ids, input_mask, segment_ids, if_trigger_ids,
                 #
                 event_type, argument_type, fea_trigger_offset,
                 #
                 start_position=None, end_position=None):

        self.example_id = example_id
        self.tokens = tokens
        self.token_to_orig_map = token_to_orig_map
        self.input_ids = input_ids
        self.input_mask = input_mask
        self.segment_ids = segment_ids
        self.if_trigger_ids = if_trigger_ids

        self.event_type = event_type
        self.argument_type = argument_type
        self.fea_trigger_offset = fea_trigger_offset

        self.start_position = start_position
        self.end_position = end_position


def read_ace_examples(input_file, is_training):
    """Read a ACE json file into a list of AceExample."""
    examples = []
    with open(input_file, "r", encoding='utf-8') as f:
        for line in f:
            example = json.loads(line)
            sentence, events, s_start, instance_id = example["sentence"], example["event"], example["s_start"], example["id"]
            example = AceExample(sentence=sentence, events=events, s_start=s_start, instance_id=instance_id)
            examples.append(example)

    return examples

def get_main_arguments(arguments, sentence):
    main_args = {
        'Subject': [],
        'Treatment': [],
        'Effect': [],
    }
    arguments.sort(key=lambda x:(x[0],x[1]))
    for argument in arguments:
        st, ed, tp = argument
        if tp in main_args:
            txt = " ".join(sentence[st:ed+1])
            main_args[tp].append(txt)

    for marg in main_args:
        main_args[marg] = "; ".join(main_args[marg])

    return main_args

def get_main_arg_type(sub_arg_type):
    main_arg = sub_arg_type.split('.')[0]
    if main_arg == 'Combination':
        main_arg = 'Treatment'
    return main_arg

def convert_examples_to_features(examples, tokenizer, query_templates, nth_query, is_training):
    """Loads a data file into a list of `InputBatch`s."""

    features = []
    for (example_id, example) in enumerate(examples):
        for event in example.events:
            trigger_offset = event[0][0] - example.s_start
            event_type = event[0][-1]
            event_type_str = " ".join(event_type.split("_")).lower()
            trigger_token = example.sentence[trigger_offset]
            arguments = event[1:]
            main_args = get_main_arguments(arguments, example.sentence)

            for argument_type in query_templates:
                main_arg_type = get_main_arg_type(argument_type)
                main_arg_text = main_args[main_arg_type]

                query = query_templates[argument_type][nth_query]
                query = query.replace("[trigger]", trigger_token)
                query = query.replace("[event_type]", event_type_str)
                query = query.replace("[main_arg_type]", main_arg_type)
                query = query.replace("[main_arg_text]", main_arg_text)

                # prepare [CLS] query [SEP] sentence [SEP]
                tokens = []
                segment_ids = []
                token_to_orig_map = {}
                # add [CLS]
                tokens.append("[CLS]")
                segment_ids.append(0)
                # add query
                query_tokens = tokenizer.tokenize(query)
                for token in query_tokens:
                    tokens.append(token)
                    segment_ids.append(0)
                # add [SEP]
                tokens.append("[SEP]")
                segment_ids.append(0)
                # add sentence
                for (i, token) in enumerate(example.sentence):
                    token_to_orig_map[len(tokens)] = i
                    sub_tokens = tokenizer.tokenize(token)
                    if sub_tokens:
                        tokens.append(sub_tokens[0])
                    else:
                        tokens.append("[UNK]")
                    segment_ids.append(1)
                # add [SEP]
                tokens.append("[SEP]")
                segment_ids.append(1)
                # transform to input_ids ...
                input_ids = tokenizer.convert_tokens_to_ids(tokens)
                input_mask = [1] * len(input_ids)
                while len(input_ids) < max_seq_length:
                    input_ids.append(0)
                    input_mask.append(0)
                    segment_ids.append(0)

                # start & end position
                start_position, end_position = None, None
                
                sentence_start = example.s_start
                sentence_offset = len(query_tokens) + 2
                fea_trigger_offset = trigger_offset + sentence_offset

                if_trigger_ids = [0] * len(segment_ids)
                if_trigger_ids[fea_trigger_offset] = 1

                if is_training:
                    no_answer = True
                    for argument in arguments:
                        gold_argument_type = argument[2]
                        if gold_argument_type == argument_type:
                            no_answer = False
                            answer_start, answer_end = argument[0], argument[1]
                
                            start_position = answer_start - sentence_start + sentence_offset
                            end_position = answer_end - sentence_start + sentence_offset
                            features.append(InputFeatures(example_id=example_id, tokens=tokens, token_to_orig_map=token_to_orig_map, input_ids=input_ids, input_mask=input_mask, segment_ids=segment_ids, if_trigger_ids=if_trigger_ids,
                                                          event_type=event_type, argument_type=argument_type, fea_trigger_offset=fea_trigger_offset,
                                                          start_position=start_position, end_position=end_position))
                    if no_answer:
                        start_position, end_position = 0, 0
                        features.append(InputFeatures(example_id=example_id, tokens=tokens, token_to_orig_map=token_to_orig_map, input_ids=input_ids, input_mask=input_mask, segment_ids=segment_ids, if_trigger_ids=if_trigger_ids,
                                                      event_type=event_type, argument_type=argument_type, fea_trigger_offset=fea_trigger_offset,
                                                      start_position=start_position, end_position=end_position))
                else:
                    features.append(InputFeatures(example_id=example_id, tokens=tokens, token_to_orig_map=token_to_orig_map, input_ids=input_ids, input_mask=input_mask, segment_ids=segment_ids, if_trigger_ids=if_trigger_ids,
                                                  event_type=event_type, argument_type=argument_type, fea_trigger_offset=fea_trigger_offset,
                                                  start_position=start_position, end_position=end_position))
    return features


def read_query_templates(normal_file):
    """Load query templates"""
    query_templates = collections.defaultdict(list)
    with open(normal_file, "r") as f:
        for line in f.readlines():
            arg_name, query = line.strip().split(",") 

            # 0 template arg_name
            query_templates[arg_name].append(arg_name)
            # 1 template arg_name + in event type
            query_templates[arg_name].append(arg_name + " in [event_type]")
            # 2 template arg_name + in main_arg_text
            query_templates[arg_name].append(arg_name + " in [main_arg_text]")
            # 3 template event_type. main_arg_type, main_arg_text. sub_arg_type?
            query_templates[arg_name].append("[event_type]. [main_arg_type], [main_arg_text]. %s?"%arg_name)
            # 4 template arg_query 
            query_templates[arg_name].append(query)
            # 5 arg_query + in event type
            query_templates[arg_name].append(query[:-1] + " in [event_type]?")
            # 6 arg_query + in main_arg_text
            query_templates[arg_name].append(query[:-1] + " in [main_arg_text]?")
            # 7 event_type. main_arg_type, main_arg_text. sub_arg_query?
            query_templates[arg_name].append("[event_type]. [main_arg_type], [main_arg_text]. %s"%query)


    return query_templates

RawResult = collections.namedtuple("RawResult",
                                   ["example_id", "event_type_offset_argument_type", "start_logits", "end_logits"])

def make_predictions(all_examples, all_features, all_results, n_best_size,
                     max_answer_length, larger_than_cls):
    example_id_to_features = collections.defaultdict(list)
    for feature in all_features:
        example_id_to_features[feature.example_id].append(feature)
    example_id_to_results = collections.defaultdict(list)
    for result in all_results:
        example_id_to_results[result.example_id].append(result)
    _PrelimPrediction = collections.namedtuple("PrelimPrediction",
                                               ["start_index", "end_index", "start_logit", "end_logit"])

    all_predictions = collections.OrderedDict()
    final_all_predictions = collections.OrderedDict()
    # all_nbest_json = collections.OrderedDict()
    # scores_diff_json = collections.OrderedDict()

    for (example_id, example) in enumerate(all_examples):
        features = example_id_to_features[example_id]
        results = example_id_to_results[example_id]
        all_predictions[example_id] = collections.OrderedDict()
        final_all_predictions[example_id] = []
        for (feature_index, feature) in enumerate(features):
            event_type_argument_type = ".".join([feature.event_type, feature.argument_type])
            event_type_offset_argument_type = ".".join([feature.event_type, str(feature.token_to_orig_map[feature.fea_trigger_offset]), feature.argument_type])

            start_indexes, end_indexes = None, None
            prelim_predictions = []
            for result in results:
                if result.event_type_offset_argument_type == event_type_offset_argument_type:
                    start_indexes = _get_best_indexes(result.start_logits, n_best_size, larger_than_cls, result.start_logits[0])
                    end_indexes = _get_best_indexes(result.end_logits, n_best_size, larger_than_cls, result.end_logits[0])
                    # add span preds
                    for start_index in start_indexes:
                        for end_index in end_indexes:
                            if start_index >= len(feature.tokens) or end_index >= len(feature.tokens):
                                continue
                            if start_index not in feature.token_to_orig_map or end_index not in feature.token_to_orig_map:
                                continue
                            if end_index < start_index:
                                continue
                            length = end_index - start_index + 1
                            if length > max_answer_length:
                                continue
                            prelim_predictions.append(
                                _PrelimPrediction(start_index=start_index, end_index=end_index,
                                                  start_logit=result.start_logits[start_index], end_logit=result.end_logits[end_index]))

                    ## add null pred
                    if not larger_than_cls:
                        feature_null_score = result.start_logits[0] + result.end_logits[0]
                        prelim_predictions.append(
                            _PrelimPrediction(start_index=0, end_index=0,
                                              start_logit=result.start_logits[0], end_logit=result.end_logits[0]))

                    ## sort
                    prelim_predictions = sorted(prelim_predictions, key=lambda x: (x.start_logit + x.end_logit), reverse=True)

                    # all_predictions[example_id][event_type_offset_argument_type] = prelim_predictions

                    ## get final pred in format: [event_type_offset_argument_type, [start_offset, end_offset]]
                    max_num_pred_per_arg = 2
                    idx = 0
                    for pred in prelim_predictions:
                        if (idx + 1) > max_num_pred_per_arg: break
                        if pred.start_index == 0 and pred.end_index == 0: break
                        orig_sent_start, orig_sent_end = feature.token_to_orig_map[pred.start_index], feature.token_to_orig_map[pred.end_index]
                        overlap = False
                        for k_type, k_offset in final_all_predictions[example_id]:
                            if k_type == event_type_argument_type:
                                if (orig_sent_start >= k_offset[0] and orig_sent_start <= k_offset[1]) or \
                                    (orig_sent_end >= k_offset[0] and orig_sent_end <= k_offset[1]):
                                    overlap = True
                                    break
                        idx += 1
                        if not overlap:
                            final_all_predictions[example_id].append([event_type_argument_type, [orig_sent_start, orig_sent_end]])
                            # idx += 1

    return final_all_predictions



def _get_best_indexes(logits, n_best_size=1, larger_than_cls=False, cls_logit=None):
    """Get the n-best logits from a list."""
    index_and_score = sorted(enumerate(logits), key=lambda x: x[1], reverse=True)

    best_indexes = []
    for i in range(len(index_and_score)):
        if i >= n_best_size:
            break
        if larger_than_cls:
            if index_and_score[i][1] < cls_logit:
                break
        best_indexes.append(index_and_score[i][0])
    return best_indexes

def _check_overlap(key, values):
    """
    key: [arg_type, [start_off, end_off]]
    values: [[arg_type, [start_off, end_off]]]

    Return:
    True if exist overlapped key-value pair
    """
    for value in values:
        if (key[1][1] >= value[1][0] and key[1][1] <= value[1][1])\
             or (value[1][1] >= key[1][0] and value[1][1] <= key[1][1]):
            return True
    return False
    
def _token_overlap(key, values):
    """
    key: [arg_type, [start_off, end_off]]
    values: [[arg_type, [start_off, end_off]]]

    Return:
    the number of key tokens appeared in value tokens
    """
    match_tokens = 0
    for k in range(key[1][0], key[1][1]+1):
        for v in values:
            if k >= v[1][0] and k <= v[1][1] and key[0] == v[0]:
                match_tokens += 1
                break

    return match_tokens

def _compute_instance_f1(a_gold, a_pred):
    """
    a_gold: [[arg_type, [start_off, end_off]]]
    a_pred: [[arg_type, [start_off, end_off]]]
    """
    gold_toks = []
    for arg_type, offsets in a_gold:
        for i in range(offsets[0], offsets[1]+1):
            gold_toks.append((i, arg_type))

    pred_toks = []
    for arg_type, offsets in a_pred:
        for i in range(offsets[0], offsets[1]+1):
            pred_toks.append((i, arg_type))

    common = collections.Counter(gold_toks) & collections.Counter(pred_toks)
    num_same = sum(common.values())
    if len(gold_toks) == 0 or len(pred_toks) == 0:
        # If either is no-answer, then p,r,F1 is 1 if they agree, 0 otherwise
        v = int(gold_toks == pred_toks)
        return v, v, v
    if num_same == 0:
        return 0, 0, 0
    precision = 1.0 * num_same / len(pred_toks)
    recall = 1.0 * num_same / len(gold_toks)
    f1 = (2 * precision * recall) / (precision + recall)
    return precision, recall, f1   

def evaluate(args, model, device, eval_dataloader, eval_examples, gold_examples, eval_features, argument_types, pred_only=False):
    all_results = []
    model.eval()
    for idx, (input_ids, input_mask, segment_ids, if_trigger_ids, example_indices) in enumerate(eval_dataloader):
        if pred_only and idx % 10 == 0:
            logger.info("Running test: %d / %d" % (idx, len(eval_dataloader)))
        input_ids = input_ids.to(device)
        input_mask = input_mask.to(device)
        segment_ids = segment_ids.to(device)
        if_trigger_ids = if_trigger_ids.to(device)
        with torch.no_grad():
            if not args.add_if_trigger_embedding:
                batch_start_logits, batch_end_logits = model(input_ids, segment_ids, input_mask)
            else:
                batch_start_logits, batch_end_logits = model(input_ids, segment_ids, if_trigger_ids, input_mask)
        for i, example_index in enumerate(example_indices):
            start_logits = batch_start_logits[i].detach().cpu().tolist()
            end_logits = batch_end_logits[i].detach().cpu().tolist()
            eval_feature = eval_features[example_index.item()]
            example_id = eval_feature.example_id
            event_type_offset_argument_type = ".".join([eval_feature.event_type, str(eval_feature.token_to_orig_map[eval_feature.fea_trigger_offset]), eval_feature.argument_type])
            all_results.append(RawResult(example_id=example_id, event_type_offset_argument_type=event_type_offset_argument_type,
                                         start_logits=start_logits, end_logits=end_logits))
        
    # preds, nbest_preds, na_probs = \
    preds = make_predictions(eval_examples, eval_features, all_results,
                         args.n_best_size, args.max_answer_length, args.larger_than_cls)
    
    preds_init = copy.deepcopy(preds)

    # get pred rsult
    pred_rst = collections.defaultdict(lambda: collections.defaultdict(list))
    for (example_id, example) in enumerate(eval_examples):
        instance_id = example.instance_id
        sentence = example.sentence
        pred_args = preds[example_id]
        for argument in pred_args:
            event_arg_type = argument[0]
            argument_start, argument_end = argument[1]
            argument_text = " ".join(sentence[argument_start:argument_end+1])
            pred_rst[instance_id][event_arg_type].append(argument_text)

    # get gold result
    # format: {instance_id: {event_type.argument_type:[entities]}}
    gold_rst = collections.defaultdict(lambda: collections.defaultdict(list))
    for (example_id, example) in enumerate(gold_examples):
        instance_id = example.instance_id
        sentence = example.sentence
        for event in example.events:
            event_type = event[0][-1]
            for argument in event[1:]:
                argument_start, argument_end, argument_type = argument[0] - example.s_start, argument[1] - example.s_start, argument[2]
                argument_text = " ".join(sentence[argument_start:argument_end+1])
                if argument_type in argument_types:
                    gold_rst[instance_id][event_type+"."+argument_type].append(argument_text)

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

    return result, preds_init, all_results


def main(args):
    device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
    n_gpu = torch.cuda.device_count()
    logger.info("device: {}, n_gpu: {}, 16-bits training: {}".format(device, n_gpu, args.fp16))
    train_best_model_dir = None

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if n_gpu > 0:
        torch.cuda.manual_seed_all(args.seed)

    if args.gradient_accumulation_steps < 1:
        raise ValueError("Invalid gradient_accumulation_steps parameter: {}, should be >= 1".format(args.gradient_accumulation_steps))
    args.train_batch_size = args.train_batch_size // args.gradient_accumulation_steps

    if not args.do_train and not args.do_eval:
        raise ValueError("At least one of `do_train` or `do_eval` must be True.")

    if args.do_train:
        assert (args.train_file is not None) and (args.dev_file is not None)

    if args.eval_test:
        assert args.test_file is not None
    else:
        assert args.dev_file is not None

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    if args.do_train:
        logger.addHandler(logging.FileHandler(os.path.join(args.output_dir, "train.log"), 'w'))
    else:
        logger.addHandler(logging.FileHandler(os.path.join(args.output_dir, "eval.log"), 'w'))
    logger.info(args)

    tokenizer = BertTokenizer.from_pretrained(args.model, do_lower_case=args.do_lower_case)

    # read query templates
    query_templates = read_query_templates(normal_file = args.normal_file)

    if args.do_train or (not args.eval_test) or args.eval_dev:
        eval_examples = read_ace_examples(input_file=args.dev_file, is_training=False)
        # gold_examples = read_ace_examples(input_file=args.gold_file, is_training=False)
        eval_features = convert_examples_to_features(
            examples=eval_examples,
            tokenizer=tokenizer,
            query_templates=query_templates,
            nth_query=args.nth_query,
            is_training=False)
        logger.info("***** Dev *****")
        logger.info("  Num orig examples = %d", len(eval_examples))
        logger.info("  Num split examples = %d", len(eval_features))
        logger.info("  Batch size = %d", args.eval_batch_size)
        all_input_ids = torch.tensor([f.input_ids for f in eval_features], dtype=torch.long)
        all_input_mask = torch.tensor([f.input_mask for f in eval_features], dtype=torch.long)
        all_segment_ids = torch.tensor([f.segment_ids for f in eval_features], dtype=torch.long)
        all_if_trigger_ids = torch.tensor([f.if_trigger_ids for f in eval_features], dtype=torch.long)
        all_example_index = torch.arange(all_input_ids.size(0), dtype=torch.long)
        eval_data = TensorDataset(all_input_ids, all_input_mask, all_segment_ids, all_if_trigger_ids, all_example_index)
        eval_dataloader = DataLoader(eval_data, batch_size=args.eval_batch_size)

    if args.do_train:
        train_examples = read_ace_examples(input_file=args.train_file, is_training=True)
        train_features = convert_examples_to_features(
            examples=train_examples,
            tokenizer=tokenizer,
            query_templates=query_templates,
            nth_query=args.nth_query,
            is_training=True)

        if args.train_mode == 'sorted' or args.train_mode == 'random_sorted':
            train_features = sorted(train_features, key=lambda f: np.sum(f.input_mask))
        else:
            random.shuffle(train_features)
        all_input_ids = torch.tensor([f.input_ids for f in train_features], dtype=torch.long)
        all_input_mask = torch.tensor([f.input_mask for f in train_features], dtype=torch.long)
        all_segment_ids = torch.tensor([f.segment_ids for f in train_features], dtype=torch.long)
        all_if_trigger_ids = torch.tensor([f.if_trigger_ids for f in train_features], dtype=torch.long)
        all_start_positions = torch.tensor([f.start_position for f in train_features], dtype=torch.long)
        all_end_positions = torch.tensor([f.end_position for f in train_features], dtype=torch.long)
        train_data = TensorDataset(all_input_ids, all_input_mask, all_segment_ids, all_if_trigger_ids,
                                   all_start_positions, all_end_positions)
        train_dataloader = DataLoader(train_data, batch_size=args.train_batch_size)
        train_batches = [batch for batch in train_dataloader]

        num_train_optimization_steps = \
            len(train_dataloader) // args.gradient_accumulation_steps * args.num_train_epochs

        logger.info("***** Train *****")
        logger.info("  Num orig examples = %d", len(train_examples))
        logger.info("  Num split examples = %d", len(train_features))
        logger.info("  Batch size = %d", args.train_batch_size)
        logger.info("  Num steps = %d", num_train_optimization_steps)

        eval_step = max(1, len(train_batches) // args.eval_per_epoch)
        best_result = None
        lrs = [args.learning_rate] if args.learning_rate else \
            [1e-6, 2e-6, 3e-6, 5e-6, 1e-5, 2e-5, 3e-5, 5e-5]
        for lr in lrs:
            if not args.add_if_trigger_embedding:
                model = BertForQuestionAnswering.from_pretrained(args.model, cache_dir=PYTORCH_PRETRAINED_BERT_CACHE)
            else:
                model = BertForQuestionAnswering_withIfTriggerEmbedding.from_pretrained(args.model, cache_dir=PYTORCH_PRETRAINED_BERT_CACHE)
            if args.fp16:
                model.half()
            model.to(device)
            if n_gpu > 1:
                model = torch.nn.DataParallel(model)
            param_optimizer = list(model.named_parameters())
            param_optimizer = [n for n in param_optimizer if 'pooler' not in n[0]]
            no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
            optimizer_grouped_parameters = [
                {'params': [p for n, p in param_optimizer
                            if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
                {'params': [p for n, p in param_optimizer
                            if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
            ]

            optimizer = BertAdam(optimizer_grouped_parameters,
                                 lr=lr,
                                 warmup=args.warmup_proportion,
                                 t_total=num_train_optimization_steps)
            tr_loss = 0
            nb_tr_examples = 0
            nb_tr_steps = 0
            global_step = 0
            start_time = time.time()
            for epoch in range(int(args.num_train_epochs)):
                model.train()
                logger.info("Start epoch #{} (lr = {})...".format(epoch, lr))
                if args.train_mode == 'random' or args.train_mode == 'random_sorted':
                    random.shuffle(train_batches)
                for step, batch in enumerate(train_batches):
                    if n_gpu == 1:
                        batch = tuple(t.to(device) for t in batch)
                    input_ids, input_mask, segment_ids, if_trigger_ids, start_positions, end_positions = batch
                    if not args.add_if_trigger_embedding:
                        loss = model(input_ids, segment_ids, input_mask, start_positions, end_positions)
                    else:
                        loss = model(input_ids, segment_ids, if_trigger_ids, input_mask, start_positions, end_positions)
                    if n_gpu > 1:
                        loss = loss.mean()
                    if args.gradient_accumulation_steps > 1:
                        loss = loss / args.gradient_accumulation_steps

                    tr_loss += loss.item()
                    nb_tr_examples += input_ids.size(0)
                    nb_tr_steps += 1

                    loss.backward()
                    if (step + 1) % args.gradient_accumulation_steps == 0:
                        optimizer.step()
                        optimizer.zero_grad()
                        global_step += 1

                    if (step + 1) % eval_step == 0 or step == 0:
                        save_model = False
                        if args.do_eval:
                            # result, _, _ = evaluate(args, model, device, eval_dataset, eval_dataloader, eval_examples, eval_features)
                            result, preds, _ = evaluate(args, model, device, eval_dataloader, eval_examples, eval_examples, eval_features, argument_types=list(query_templates.keys()))
                            # import ipdb; ipdb.set_trace()
                            model.train()
                            result['global_step'] = global_step
                            result['epoch'] = epoch     
                            result['learning_rate'] = lr
                            result['batch_size'] = args.train_batch_size
                            if (best_result is None) or (result[args.eval_metric] > best_result[args.eval_metric]):
                                train_best_model_dir = os.path.join(args.output_dir, "epoch{epoch}-step{step}".format(epoch=epoch, step=step))
                                best_result = result
                                save_model = True
                                logger.info('Epoch: {}, Step: {} / {}, used_time = {:.2f}s, loss = {:.6f}'.format(
                                    epoch, step + 1, len(train_batches), time.time() - start_time, tr_loss / nb_tr_steps))
                                # logger.info("!!! Best dev %s (lr=%s, epoch=%d): p_c: %.2f, r_c: %.2f, f1_c: %.2f" %
                                            # (args.eval_metric, str(lr), epoch, result["prec_c"], result["recall_c"], result["f1_c"]))
                                logger.info("!!! Best dev %s (lr=%s, epoch=%d): CLS_EM_F1: %.2f, CLS_EM_P: %.2f, CLS_EM_R: %.2f, CLS_Micro_F1: %.2f, CLS_Micro_P: %.2f, CLS_Micro_R: %.2f" %
                                            (args.eval_metric, str(lr), epoch, result["CLS_Arguments_EM_F1"], result["CLS_Arguments_EM_P"], result["CLS_Arguments_EM_R"], result["CLS_Arguments_MICRO_F1"], result["CLS_Arguments_MICRO_P"], result["CLS_Arguments_MICRO_R"],))
                                
                        else:        
                            save_model = True
                        # if (int(args.num_train_epochs)-epoch<3 and (step+1)/len(train_batches)>0.7) or step == 0:
                        #     save_model = True
                        # else:
                        #     save_model = False
                        if save_model:
                            model_to_save = model.module if hasattr(model, 'module') else model
                            subdir = os.path.join(args.output_dir, "epoch{epoch}-step{step}".format(epoch=epoch, step=step))
                            if not os.path.exists(subdir):
                                os.makedirs(subdir)
                            output_model_file = os.path.join(subdir, WEIGHTS_NAME)
                            output_config_file = os.path.join(subdir, CONFIG_NAME)
                            torch.save(model_to_save.state_dict(), output_model_file)
                            model_to_save.config.to_json_file(output_config_file)
                            tokenizer.save_vocabulary(subdir)
                            if best_result:
                                
                                with open(os.path.join(subdir, "eval_results.txt"), "w") as writer:
                                    for key in sorted(best_result.keys()):
                                        writer.write("%s : %s\n" % (key, json.dumps(best_result[key])))

                                output_lines = []
                                with open(args.dev_file, "r") as f:
                                    for lid, line in enumerate(f.readlines()):
                                        dat = json.loads(line)
                                        dat['arg_pred'] = []
                                        pred_rst = preds[lid]
                                        for p in pred_rst:
                                            # role = p[0].split('_')[-1]
                                            dat['arg_pred'].append([p[1][0], p[1][1], p[0]])
                                        output_lines.append(json.dumps(dat))

                                output_file = os.path.join(subdir, "eval_outputs.json")
                                with open(output_file, "w") as f:
                                    f.write("\n".join(output_lines))                            

    if args.do_eval:
        if train_best_model_dir: # for training
            model_dir = train_best_model_dir
        else: # for only prediction
            model_dir = args.model_dir
        logger.info("Test model dir = %s", model_dir)
        if not args.add_if_trigger_embedding:
            model = BertForQuestionAnswering.from_pretrained(model_dir)
        else:
            model = BertForQuestionAnswering_withIfTriggerEmbedding.from_pretrained(model_dir)
        if args.fp16:
            model.half()
        model.to(device)

        if args.eval_dev:
            dev_result, dev_preds, _ = evaluate(args, model, device, eval_dataloader, eval_examples, eval_examples, eval_features, argument_types=list(query_templates.keys()))
            with open(os.path.join(model_dir, "eval_results.txt"), "w") as writer:
                                    for key in sorted(dev_result.keys()):
                                        writer.write("%s : %s\n" % (key, json.dumps(dev_result[key])))          

        if args.eval_test:
            eval_examples = read_ace_examples(input_file=args.test_file, is_training=False)
            gold_examples = read_ace_examples(input_file=args.gold_file, is_training=False)
            eval_features = convert_examples_to_features(
                examples=eval_examples,
                tokenizer=tokenizer,
                query_templates=query_templates,
                nth_query=args.nth_query,
                is_training=False)
            logger.info("***** Test *****")
            logger.info("  Num orig examples = %d", len(eval_examples))
            logger.info("  Num split examples = %d", len(eval_features))
            logger.info("  Batch size = %d", args.eval_batch_size)
            all_input_ids = torch.tensor([f.input_ids for f in eval_features], dtype=torch.long)
            all_input_mask = torch.tensor([f.input_mask for f in eval_features], dtype=torch.long)
            all_segment_ids = torch.tensor([f.segment_ids for f in eval_features], dtype=torch.long)
            all_if_trigger_ids = torch.tensor([f.if_trigger_ids for f in eval_features], dtype=torch.long)
            all_example_index = torch.arange(all_input_ids.size(0), dtype=torch.long)
            eval_data = TensorDataset(all_input_ids, all_input_mask, all_segment_ids, all_if_trigger_ids, all_example_index)
            eval_dataloader = DataLoader(eval_data, batch_size=args.eval_batch_size)


            result, preds, _ = evaluate(args, model, device, eval_dataloader, eval_examples, gold_examples, eval_features,argument_types=list(query_templates.keys()))

            with open(os.path.join(model_dir, "test_results.txt"), "w") as writer:
                for key in result:
                    writer.write("%s : %s\n" % (key, json.dumps(result[key])))
            
            output_lines = []
            with open(args.test_file, "r") as f:
                for lid, line in enumerate(f.readlines()):
                    dat = json.loads(line)
                    dat['arg_pred'] = []
                    pred_rst = preds[lid]
                    for p in pred_rst:
                        # role = p[0].split('_')[-1]
                        dat['arg_pred'].append([p[1][0], p[1][1], p[0]])
                    output_lines.append(json.dumps(dat))

            output_file = os.path.join(model_dir, "pred_outputs.json")
            with open(output_file, "w") as f:
                f.write("\n".join(output_lines))     
        
        ### old

        # na_prob_thresh = 1.0
        # if args.version_2_with_negative:
        #     eval_result_file = os.path.join(args.output_dir, "eval_results.txt")
        #     if os.path.isfile(eval_result_file):
        #         with open(eval_result_file) as f:
        #             for line in f.readlines():
        #                 if line.startswith('best_f1_thresh'):
        #                     na_prob_thresh = float(line.strip().split()[-1])
        #                     logger.info("na_prob_thresh = %.6f" % na_prob_thresh)

        # result, preds, _ = \
        #     evaluate(args, model, device, eval_dataset,
        #              eval_dataloader, eval_examples, eval_features,
        #              na_prob_thresh=na_prob_thresh,
        #              pred_only=args.eval_test)
        # with open(os.path.join(args.output_dir, "predictions.json"), "w") as writer:
        #     writer.write(json.dumps(preds, indent=4) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        args = {
            "model": None,
            "output_dir": None,
            "model_dir": None,
            "train_file": None,
            "dev_file": None,
            "test_file": None,
            "gold_file": None,
            "max_seq_length": 180,
            "eval_per_epoch": 10,
            "do_train": False,
            "do_eval": False,
            "do_lower_case": False,
            "eval_test": False,
            "train_batch_size": 32,
            "eval_batch_size": 8,
            "learning_rate": None,
            "num_train_epochs": 3.0,
            "eval_metric": "f1_c",
            "train_mode": "random_sorted",
            "warmup_proportion": 0.1,
            "n_best_size": 20,
            "max_answer_length": 30,
            "verbose_logging": False,
            "no_cuda": False,
            "seed": 42,
            "gradient_accumulation_steps": 1,
            "fp16": False,
            "loss_scale": 0,
            "version_2_with_negative": False,
            "add_lstm": False,
            "lstm_lr": None,
            "nth_query": 0,
            "normal_file": None,
            "des_file": None,
            "larger_than_cls": False,
            "add_if_trigger_embedding": False
        }
        args = edict(args)
        arg_file = sys.argv[1]
        with open(arg_file, 'r') as f:
            nargs = json.load(f)
            args.update(nargs)
                
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--model", default=None, type=str, required=True)
        parser.add_argument("--output_dir", default=None, type=str, required=True,
                            help="The output directory where the model checkpoints and predictions will be written.")
        parser.add_argument("--model_dir", default="args_qa_output/epoch0-step0", type=str, required=True, help="eval/test model")
        parser.add_argument("--train_file", default=None, type=str)
        parser.add_argument("--dev_file", default=None, type=str)
        parser.add_argument("--test_file", default=None, type=str)
        parser.add_argument("--gold_file", default=None, type=str)
        parser.add_argument("--eval_per_epoch", default=10, type=int,
                            help="How many times it evaluates on dev set per epoch")
        parser.add_argument("--max_seq_length", default=180, type=int,
                            help="The maximum total input sequence length after WordPiece tokenization. Sequences "
                            "longer than this will be truncated, and sequences shorter than this will be padded.")
        parser.add_argument("--do_train", action='store_true', help="Whether to run training.")
        parser.add_argument("--do_eval", action='store_true', help="Whether to run eval on the dev set.")
        parser.add_argument("--do_lower_case", action='store_true', help="Set this flag if you are using an uncased model.")
        parser.add_argument("--eval_test", action='store_true', help='Wehther to run eval on the test set.')
        parser.add_argument("--train_batch_size", default=32, type=int, help="Total batch size for training.")
        parser.add_argument("--eval_batch_size", default=8, type=int, help="Total batch size for predictions.")
        parser.add_argument("--learning_rate", default=None, type=float, help="The initial learning rate for Adam.")
        parser.add_argument("--num_train_epochs", default=3.0, type=float,
                            help="Total number of training epochs to perform.")
        parser.add_argument("--eval_metric", default='f1_c', type=str)
        parser.add_argument("--train_mode", type=str, default='random_sorted', choices=['random', 'sorted', 'random_sorted'])
        parser.add_argument("--warmup_proportion", default=0.1, type=float,
                            help="Proportion of training to perform linear learning rate warmup for. E.g., 0.1 = 10%% "
                                 "of training.")
        parser.add_argument("--n_best_size", default=20, type=int,
                            help="The total number of n-best predictions to generate in the nbest_predictions.json "
                                 "output file.")
        parser.add_argument("--max_answer_length", default=30, type=int,
                            help="The maximum length of an answer that can be generated. "
                                 "This is needed because the start "
                                 "and end predictions are not conditioned on one another.")
        parser.add_argument("--no_cuda", action='store_true',
                            help="Whether not to use CUDA when available")
        parser.add_argument('--seed', type=int, default=42,
                            help="random seed for initialization")
        parser.add_argument('--gradient_accumulation_steps', type=int, default=1,
                            help="Number of updates steps to accumulate before performing a backward/update pass.")
        parser.add_argument('--fp16', action='store_true',
                            help="Whether to use 16-bit float precision instead of 32-bit")
        parser.add_argument('--loss_scale', type=float, default=0,
                            help="Loss scaling to improve fp16 numeric stability. Only used when fp16 set to True.\n"
                                 "0 (default value): dynamic loss scaling.\n"
                                 "Positive power of 2: static loss scaling value.\n")
        parser.add_argument('--version_2_with_negative', action='store_true',
                            help='If true, the SQuAD examples contain some that do not have an answer.')
        parser.add_argument("--nth_query", default=0, type=int, help="use n-th template query")
        parser.add_argument("--normal_file", default=None, type=str)
        parser.add_argument("--des_file", default=None, type=str)
        parser.add_argument("--larger_than_cls", action='store_true', help="when indexing s and e")
        parser.add_argument("--add_if_trigger_embedding", action='store_true', help="add the if_trigger_embedding")
        args = parser.parse_args()

        if max_seq_length != args.max_seq_length: max_seq_length = args.max_seq_length

    main(args)
