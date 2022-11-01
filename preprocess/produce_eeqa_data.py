"""
Transfer json data to eeqa input format.
running evrionment: eeqa-ace-preprocess

"""
from ast import arguments
import spacy
from easydict import EasyDict as edict
import json
import re
from spacy.tokenizer import Tokenizer
import random
import os

def make_nlp():
        '''
        Add a few special cases to spacy tokenizer so it works with ACe mistakes.
        '''
        
        nlp = spacy.load('en')

        # split '-' when tokenize the words
        infixes = list(nlp.Defaults.infixes) + ["-"]  
        infix_regex = spacy.util.compile_infix_regex(infixes)
        nlp.tokenizer.infix_finditer = infix_regex.finditer


        # copy this from EEQA code
        # it is written for ACE corpus.
        # TODO: probably need to adjust for our dataset
        single_tokens = ['sgt.',
                         'sen.',
                         'col.',
                         'brig.',
                         'gen.',
                         'maj.',
                         'sr.',
                         'lt.',
                         'cmdr.',
                         'u.s.',
                         'mr.',
                         'p.o.w.',
                         'u.k.',
                         'u.n.',
                         'ft.',
                         'dr.',
                         'd.c.',
                         'mt.',
                         'st.',
                         'snr.',
                         'rep.',
                         'ms.',
                         'capt.',
                         'sq.',
                         'jr.',
                         'ave.']

        for special_case in single_tokens:
            nlp.tokenizer.add_special_case(special_case, [dict(ORTH=special_case)])
            upped = special_case.upper()
            nlp.tokenizer.add_special_case(upped, [dict(ORTH=upped)])
            capped = special_case.capitalize()
            nlp.tokenizer.add_special_case(capped, [dict(ORTH=capped)])

        return nlp

def find_nearest_span(doc, start, text):
    end = start + len(text) -1

    for token in doc:
        if start >= token.idx and start < token.idx + len(token.text):
            start = token.idx

        if end >= token.idx and end < token.idx + len(token.text):
            end = token.idx + len(token.text)
            break

    text = doc.text[start:end]

    return start, text

def main():
    PARENT_ARGS = ['Subject', "Effect", 'Treatment'] # TODO: discard this Disorder after cleaning the data
    PARENT_TO_CHILD = {
        "Subject": ["Age", "Gender", "Population", "Race", "Disorder"],
        "Treatment": ["Drug", "Dosage", "Freq", "Route", "Duration", "Time_elapsed", "Disorder"],
        "Effect": [],
    }

    splits = ["train", "dev", "test"]
    for split in splits:
        src_file = "../data/json/%s.json"%split
        tgt_file = "../data/eeqa/%s.json"%split

        if not os.path.exists(os.path.dirname(tgt_file)):
            os.makedirs(os.path.dirname(tgt_file))

        output_lines = []
        nlp = make_nlp()

        with open(src_file, "r", encoding='utf-8') as f:
            for line in f.readlines():
                out = {}
                data = json.loads(line)
                data = edict(data)

                annotation = data.annotations[0]
                
                doc = nlp(data.context)
                out['sentence'] = [t.text for t in doc]
                out['s_start'] = 0  # our corpus is sent level, no doc offset is recorded
                out['ner'] = [] # ignore for single event cases
                out['relation'] = [] # ignore for single event cases
                out['event'] = []
                out['id'] = data.id  # add this id for IAA computation, might be removed later
                for event in annotation.events:
                    ev = []  # store this event output
                    
                    # Convert trigger
                    ev_type = event.event_type
                    # we ignore multi span/discontinuous span cases for trigger (usually won't happen actually)
                    # furthermore, EEQA only uses the first token of the trigger (but for this preprocess, we still keep all tokens)
                    trigger_text = event.Trigger.text[0][0]
                    trigger_start = event.Trigger.start[0][0]
                    try:
                        trigger = doc.char_span(trigger_start, trigger_start+len(trigger_text))
                        assert(trigger.text == trigger_text)
                    except:
                        trigger_start, trigger_text = find_nearest_span(doc, trigger_start, trigger_text)
                        trigger = doc.char_span(trigger_start, trigger_start+len(trigger_text))

                    ev.append([trigger.start, trigger.end-1, ev_type])

                    # Convert arguments
                    for role in PARENT_ARGS:
                        if role in event: # not appeared arguments are not stored
                            argument = event[role] # example: {"text": [["the concurrent use of 5-FU and warfarin"]], "start": [[87]], "entity_id": ["T6"], & Sub_Arguments}
                            # extract parent arguments information
                            # we temporally consider each span and each discontinuous part of a span as a independent span
                            for lt, ls in zip(argument.text, argument.start): # for each span in a multi-span argument
                                for t, s in zip(lt, ls): # for each discontinuous part of a argument span
                                    try:
                                        span = doc.char_span(s, s+len(t))
                                        assert(span.text == t)
                                    except:
                                        s, t = find_nearest_span(doc, s, t)
                                        span = doc.char_span(s, s+len(t))
                                    ev.append([span.start, span.end-1, role])

                            # extract sub_arguments information
                            for key in argument.keys():
                                if key in PARENT_TO_CHILD[role]:
                                    sub_arg = argument[key]
                                    for lt, ls in zip(sub_arg.text, sub_arg.start): # for each span in a multi-span argument
                                        for t, s in zip(lt, ls): # for each discontinuous part of a argument span
                                            try:
                                                span = doc.char_span(s, s+len(t))
                                                assert(span.text == t)
                                            except:
                                                s, t = find_nearest_span(doc, s, t)
                                                span = doc.char_span(s, s+len(t))
                                            ev.append([span.start, span.end-1, role+"."+key])

                            # extraction combination.drug information
                            if role == 'Treatment' and 'Combination' in argument:
                                for comb in argument.Combination:
                                    if "Drug" in comb:
                                        for lt, ls in zip(comb.Drug.text, comb.Drug.start):
                                            for t, s in zip(lt, ls):
                                                try:
                                                    span = doc.char_span(s, s+len(t))
                                                    assert(span.text == t)
                                                except:
                                                    s, t = find_nearest_span(doc, s, t)
                                                    span = doc.char_span(s, s+len(t))
                                                ev.append([span.start, span.end-1, "Combination.Drug"])


                    out['event'].append(ev)

                output_lines.append(json.dumps(out))

        with open(tgt_file, "w", encoding='utf-8') as f:
            f.write("\n".join(output_lines))
           

if __name__ == '__main__':
    main()

