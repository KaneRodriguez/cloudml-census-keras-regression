### Modified Open Source Keras version of the Census sample

The sample runs both as a standalone Keras code and on Cloud ML Engine.

## Assign the data

The following will assign the global training and evaluation files.

```
TRAIN_FILE=$(pwd)/data/output_train.csv
EVAL_FILE=$(pwd)/data/output_test.csv

# TODO: follow tutorial and upload train and eval file to a bucket. CHANGE
GCS_TRAIN_FILE=gs://cloud-samples-data/ml-engine/census/data/adult.data.csv
GCS_EVAL_FILE=gs://cloud-samples-data/ml-engine/census/data/adult.test.csv

gsutil cp $GCS_TRAIN_FILE $TRAIN_FILE
gsutil cp $GCS_EVAL_FILE $EVAL_FILE
```

Note: Development was done on MacOS Mojave 10.14.2

## Virtual environment

Virtual environments are strongly suggested, but not required. Installing this
sample's dependencies in a new virtual environmentcl allows you to run the sample
without changing global python packages on your system.

There are two options for the virtual environments:

 * Install [Virtual](https://virtualenv.pypa.io/en/stable/) env
   * Create virtual environment `virtualenv --python=/usr/bin/python2.7 custom_keras`
   * Activate env `source custom_keras/bin/activate`
 * Install [Miniconda](https://conda.io/miniconda.html)
   * Create conda environment `conda create --name custom_keras python=2.7`
   * Activate env `source activate custom_keras`

## Install dependencies

 * Install [gcloud](https://cloud.google.com/sdk/gcloud/)
 * Install the python dependencies. `pip install --upgrade -r requirements.txt`

## Using local python

You can run the Keras code locally

```
JOB_DIR=census_keras
TRAIN_STEPS=2000
python -m trainer.task --train-files $TRAIN_FILE \
                       --eval-files $EVAL_FILE \
                       --job-dir $JOB_DIR \
                       --train-steps $TRAIN_STEPS
```

## Training using gcloud local

You can run Keras training using gcloud locally

```
JOB_DIR=census_keras
TRAIN_STEPS=200
gcloud ml-engine local train --package-path trainer \
                             --module-name trainer.task \
                             -- \
                             --train-files $TRAIN_FILE \
                             --eval-files $EVAL_FILE \
                             --job-dir $JOB_DIR \
                             --train-steps $TRAIN_STEPS
```

## Distributed Training using gcloud local

You can run Keras distributed training using gcloud locally

```
JOB_DIR=census_keras_dist
TRAIN_STEPS=200
gcloud ml-engine local train --package-path trainer \
                             --module-name trainer.task \
                             --distributed
                             -- \
                             --train-files $TRAIN_FILE \
                             --eval-files $EVAL_FILE \
                             --job-dir $JOB_DIR \
                             --train-steps $TRAIN_STEPS
```

## Prediction using gcloud local

You can run prediction on the SavedModel created from Keras HDF5 model

```
python preprocess.py sample.json
```

```
gcloud ml-engine local predict --model-dir=$JOB_DIR/export \
                               --json-instances sample.json
```

## Training using Cloud ML Engine

You can train the model on Cloud ML Engine

```
JOB_DIR=census_keras
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.4 \
                                    --job-dir $JOB_DIR \
                                    --package-path trainer \
                                    --module-name trainer.task \
                                    --region us-central1 \
                                    -- \
                                    --train-files $GCS_TRAIN_FILE \
                                    --eval-files $GCS_EVAL_FILE \
                                    --train-steps $TRAIN_STEPS
```

## Distributed Training using Cloud ML Engine

You can train the model on Cloud ML Engine in distributed mode

```
JOB_DIR=census_keras_dist
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.4 \
                                    --job-dir $JOB_DIR \
                                    --package-path trainer \
                                    --module-name trainer.task \
                                    --region us-central1 \
                                    --distributed \
                                    -- \
                                    --train-files $GCS_TRAIN_FILE \
                                    --eval-files $GCS_EVAL_FILE \
                                    --train-steps $TRAIN_STEPS
```

## Prediction using Cloud ML Engine

You can perform prediction on Cloud ML Engine by following the steps below.
Create a model on Cloud ML Engine

```
gcloud ml-engine models create keras_model --regions us-central1
```

Export the model binaries

```
MODEL_BINARIES=$JOB_DIR/export
```

Deploy the model to the prediction service

```
gcloud ml-engine versions create v1 --model keras_model --origin $MODEL_BINARIES --runtime-version 1.2
```

Create a processed sample from the data

```
python preprocess.py sample.json

```

Run the online prediction

```
gcloud ml-engine predict --model keras_model --version v1 --json-instances sample.json
```

## Resources

* [Here](https://stackoverflow.com/questions/1534210/use-different-python-version-with-virtualenv) - For using a specific version of python with virtualenv