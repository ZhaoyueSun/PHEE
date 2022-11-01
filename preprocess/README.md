# data preprocessing

## Brat Format data

  - .txt: sentence text. A file only includes one sentence.
  - .ann: entities(T), attribute_cues(T), triggers(T), relations(R), events(E), attributes(A)


## Step1:  Brat format data to JSON structured data

- scripts: transfer_to_json.py
- Aims to change span-oriented data to event-oriented data, and store them in structured format to fercilitate furture use. 
- Output Files: train.json, dev.json, test.json [Each line is a json dict]
- Output Data Format:

```json
{
    "id": (str) sample id, 
    "context": (str) sentence text, 
    "is_multi_event": (bool), if the case belongs to the mult_event subset. Note that sub-event (Combination) is also considered as an event here, which means that a case with an ADE/PTE and a Combination subevent is labelled as multi_event as well. For cases with duplicated annotation, they are labelled as multi_event as long as either annotator annotated them with multiple events. 
    "annotations":[
        {"events": [
            {
                "event_id": (str) event id,
                "event_type": (str) event type, 
                "Trigger": {
                    // Note: for each entity, a tuple is maintained in case the span has multiple discontinuous parts.
                    // Usually, the length of each tuple is no more than 2.
                    "text": [[(str) trigger text for fragment_1, (str) trigger text for fragment_2, ...] for each entity], 
                    "start":[[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                    },
                "Subject":{
                    "text": [[(str) subject text for fragment_1, (str) subject text for fragment_2, ...] for each entity],
                    "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                    "Age":{
                        "text": [[(str) Sub.Age text for fragment_1, (str) subject text for fragment_2, ...] for each entity],
                        "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                        "entity_id": [(int) entity_id for each entity],
                    },
                    "Gender": structured as Subject.Age,
                    "Population": structured as Subject.Age,
                    "Race": structured as Subject.Age,
                    "Disorder": structured as Subject.Age,
                }
                ,
                "Treatment": {
                    "text": [[(str) Treatment text for fragment_1, (str) Treatment text for fragment_2, ...] for each entity],
                    "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                    "Drug": structured as Subject.Age,
                    "Dosage": structured as Subject.Age,
                    "Freq": structured as Subject.Age,
                    "Route": structured as Subject.Age,
                    "Time_elapsed": structured as Subject.Age, 
                    "Disorder": structured as Subject.Age, 
                    "Combination": [{ //sub-event
                        "event_id": (str) event id,
                        "event_type": (str) event type, 
                        "Trigger": structed as trigger,
                        "Drug": structured as Subject.Age,
                    } for each Combination]
                },
                "Effect":{
                    "text": [[(str) effect text for fragment_1, (str) effect text for fragment_2, ...] for each entity],
                    "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                },
                "Speculation": {
                    "text": [[(str) speculation cue text for fragment_1, (str) speculation cue for fragment_2, ...] for each entity],
                    "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                    "value": true/false (by default false),
                },
                "Negation":{
                    "text": [[(str) negation cue text for fragment_1, (str) negation cue text for fragment_2, ...] for each entity],
                    "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                    "value": true/false (by default false),
                },
                "Severity":{
                    "text": [[(str) severity cue text for fragment_1, (str) severity cue text for fragment_2, ...] for each entity],
                    "start": [[(int) start position for fragment_1, (int) start position for fragment_2, ...] for each entity],
                    "entity_id": [(int) entity_id for each entity],
                    "value": (str) High/Medium/Low (by default Medium), 
                }
            } for each event in the sentence]
        }
    for each annotator's annotation if has duplicated annotation]
    
}
```

## Step2:  JSON structured data to baseline-oriented data

#### EEQA

cite:
```
@inproceedings{du2020event,
title = {Event Extraction by Answering (Almost) Natural Questions},
author={Du, Xinya and Cardie, Claire},
booktitle = "Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing",
year = "2020",
publisher = "Association for Computational Linguistics",
}
```
Scripts:
produce_eeqa_data.py

Data format:
A line is a json dict.

```json
{'sentence': (list(str)) list of tokens,
 's_start': (int)sentence start_pos(token_level) in doc,
 'ner': [[(int) start_pos(token_level), (int) end_pos(token_level), (str) entity_type] for each NE in sentence],
 'relation': [[(int)start_pos of head(token_lv), (int)end_pos of head(token_lv), (int)start_pos of tail(token_lv), (int)end_pos of head(token_lv), (str)relation type] for each relation in sentence],
 'event': [[[(int)start_pos of trigger(first token), str(event type)], [(int) start_pos(token_lv) of argument_i, (int)end_pos(token_lv) of argument_i, str(argument role)] for each argument in event]  for each event in sentence]
 }
```

Example: (ACE05 corpus)

```json
{'sentence': ['Orders', 'went', 'out', 'today', 'to', 'deploy', '17,000', 'U.S.', 'Army', 'soldiers', 'in', 'the', 'Persian', 'Gulf', 'region', '.'], 's_start': 24, 'ner': [[31, 31, 'GPE'], [32, 32, 'ORG'], [33, 33, 'PER'], [36, 37, 'LOC'], [38, 38, 'LOC']], 'relation': [[32, 32, 31, 31, 'PART-WHOLE.Subsidiary'], [33, 33, 32, 32, 'ORG-AFF.Employment'], [33, 33, 38, 38, 'PHYS.Located'], [36, 37, 38, 38, 'PART-WHOLE.Geographical']], 'event': [[[29, 'Movement.Transport'], [33, 33, 'Artifact'], [38, 38, 'Destination']]]}
```

Example: (PHEE stage1)

```json
{"sentence": ["Four", "patients", "in", "whom", "pulmonary", "oedema", "developed", "during", "tocolysis", "with", "hexoprenaline", "are", "described", "and", "the", "aetiological", "factors", "and", "pathogenesis", "of", "this", "potentially", "lethal", "complication", "discussed", "."], "s_start": 0, "ner": [], "relation": [], "event": [[[6, "Adverse_event"], [0, 1, "Subject"], [10, 10, "Treatment"], [4, 5, "Effect"]]]}
```


#### Generative QA baseline

Data format: json

```json
{
"version": dataset_version,
"data": [
    {
        "answers":{
            "text": [argument spans],
            "answer_start": [character start offsets for each argument span]
        },
        "context": text of the sentence to extract the event,
        "id": sentence id,
        "question": question to extract triggers/arguments,
        "question_type": e.g. "Adverse_event|Trigger"/"Potential_therapeutic_event|Subject" ...
    } for each instance
]
}
```

Note that for huggingface SQuAD dataset, items in 'answers' are different possible answers, here for our case, we only annotate one answer, but might include multiple arguments. 


Example: (PHEE stage1)
```json
{"version": "v1.0", 
"data": [{"id": "16507211_1", "context": "Herein, we describe 2 patients who developed unusual CD8+ cutaneous lymphoproliferative disorders after treatment with efalizumab and infliximab.", "question": "Who is the subject?", "question_type": "Adverse_event|Subject", "answers": {"text": ["2 patients"], "answer_start": [20]}},
{"id": "16507211_1", "context": "Herein, we describe 2 patients who developed unusual CD8+ cutaneous lymphoproliferative disorders after treatment with efalizumab and infliximab.", "question": "What is the treatment?", "question_type": "Adverse_event|Treatment", "answers": {"text": ["efalizumab and infliximab"], "answer_start": [119]}}]
}
```

### ACE (sequence labelling baseline)