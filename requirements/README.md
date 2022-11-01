Conda environments:
eeqa-ace-preprocess: for EEQA data preprocess
eeqa: for run EEQA baseline
torch_transformer: for GenQA baseline
ace: for ace baseline

Note:
for each environment, first build conda environment with:
```
conda create --name <env_name>  --file <env_name>_conda_requirements.txt
```
then activate the conda environment and install pip packages with:
```
pip install -r <env_name>_pip_requirements.txt
```
if dependency conflicts occurs (for the torch_transformer environment), retry with:
```
pip install -r <env_name>_pip_requirements.txt --no-deps
```


for the eeqa-ace-preprocess environment, further run:
```
python -m spacy download en
```