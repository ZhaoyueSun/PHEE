"""
evaluate the event classification F1
"""
import json
import re
import collections

def _parse_entities(text):
        EVENT_TYPES = ['Adverse event', 'Potential therapeutic event']
        MAIN_ARGS = ['Subject', 'Treatment', 'Effect']
        pattern = re.compile(r'\[.*?\][^\[]*')
        entities = collections.defaultdict(list)
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

def main():
    pred_file = "model/stage1/SciFive-base-PMC/predict_outputs.json"
    with open(pred_file, 'r') as f:
        pred_data = json.load(f)

    golds = pred_data['label_ids']
    preds = pred_data['predictions']

    tp = 0
    pred_n = 0
    gold_n = 0

    for gold_instance, pred_instance in zip(golds, preds):
        gold_entities = _parse_entities(gold_instance['answers'])
        pred_entities = _parse_entities(pred_instance['prediction_text'])
        gold_trigs = []
        for k in gold_entities:
            if 'Trigger' in k:
                ev_type = k.split('.')[0]
                trigger_text = gold_entities[k]
                gold_trigs.append([ev_type, trigger_text])
        pred_trigs = []
        for k in pred_entities:
            if 'Trigger' in k:
                ev_type = k.split('.')[0]
                trigger_text = pred_entities[k]
                pred_trigs.append([ev_type, trigger_text])
        
        for gold_ev, gold_trig in gold_trigs:
            for pred_ev, pred_trig in pred_trigs:
                if gold_trig == pred_trigs and gold_ev != pred_ev:
                    print(gold_instance['id'], gold_ev, pred_ev, gold_trig)

        gold_events = [x[0] for x in gold_trigs]
        pred_events = [x[0] for x in pred_trigs]

        common = collections.Counter(gold_events) & collections.Counter(pred_events)
        same_num = sum(common.values())
        tp += same_num
        pred_n += len(pred_events)
        gold_n += len(gold_events)
    
    p = 1.0 * tp/pred_n
    r = 1.0 * tp/gold_n
    f1 = 100.0* 2*p*r/(p+r)

    print("event detection f1:", f1)





if __name__ == '__main__':
    main()