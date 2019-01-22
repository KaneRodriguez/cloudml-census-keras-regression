### Modified Open Source Keras version of the Census sample

The sample runs both as a standalone Keras code and on Cloud ML Engine. It enables easy training of a multiple output regression Keras model with hyperparemeter tuning and distributed training.

## Assign the data

The following will assign your local and gcloud hosted training and evaluation as well as create a bucket from your current gcloud project.

```
TRAIN_FILE=$(pwd)/data/output_train.csv
EVAL_FILE=$(pwd)/data/output_test.csv

PROJECT_ID=$(gcloud config list project --format "value(core.project)")
BUCKET_NAME=${PROJECT_ID}-mlengine

REGION=us-central1

gsutil mb -l $REGION gs://$BUCKET_NAME

gsutil cp -r data gs://$BUCKET_NAME/data

gsutil cp ../test.json gs://$BUCKET_NAME/data/test.json

GCS_TRAIN_FILE=gs://$BUCKET_NAME/data/output_train.csv
GCS_EVAL_FILE=gs://$BUCKET_NAME/data/output_test.csv
TEST_JSON=gs://$BUCKET_NAME/data/test.json
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
JOB_DIR=$(pwd)/output_keras
TRAIN_STEPS=2000
python -m trainer.task --train-files $TRAIN_FILE \
                       --eval-files $EVAL_FILE \
                       --job-dir $JOB_DIR \
                       --train-steps $TRAIN_STEPS
```

## Training using gcloud local

You can run Keras training using gcloud locally

```
JOB_DIR=$(pwd)/output_keras
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
JOB_DIR=$(pwd)/output_keras_dist
TRAIN_STEPS=20
gcloud ml-engine local train --package-path trainer \
                             --module-name trainer.task \
                             --distributed \
                             -- \
                             --train-files $TRAIN_FILE \
                             --eval-files $EVAL_FILE \
                             --job-dir $JOB_DIR \
                             --train-steps $TRAIN_STEPS \
                             --distributed True
```

## Prediction using gcloud local

You can run prediction on the SavedModel created from Keras HDF5 model

```
python preprocess.py test.json
```

```
gcloud ml-engine local predict --model-dir=$JOB_DIR/export \
                               --json-instances test.json
```

## Training using Cloud ML Engine

You can train the model on Cloud ML Engine

```
JOB_NAME=output_keras_single_1
OUTPUT_PATH=gs://$BUCKET_NAME/$JOB_NAME
TRAIN_STEPS=200
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.12 \
                                    --job-dir $OUTPUT_PATH \
                                    --package-path trainer \
                                    --module-name trainer.task \
                                    --region $REGION \
                                    -- \
                                    --train-files $GCS_TRAIN_FILE \
                                    --eval-files $GCS_EVAL_FILE \
                                    --train-steps $TRAIN_STEPS
```

## Distributed Training using Cloud ML Engine

You can train the model on Cloud ML Engine in distributed mode

```
JOB_NAME=output_keras_dist_4
OUTPUT_PATH=gs://$BUCKET_NAME/$JOB_NAME
TRAIN_STEPS=20
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.12 \
                                    --job-dir $OUTPUT_PATH \
                                    --package-path trainer \
                                    --module-name trainer.task \
                                    --region $REGION \
                                    --scale-tier STANDARD_1 \
                                    -- \
                                    --train-files $GCS_TRAIN_FILE \
                                    --eval-files $GCS_EVAL_FILE \
                                    --train-steps $TRAIN_STEPS \
                                    --distributed True

```

## Prediction using Cloud ML Engine

You can perform prediction on Cloud ML Engine by following the steps below.
Create a model on Cloud ML Engine

```
gcloud ml-engine models create keras_model --regions $REGION
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
python preprocess.py test.json

```

Run the online prediction

```
gcloud ml-engine predict --model keras_model --version v1 --json-instances test.json
```

## Resources

* [Here](https://stackoverflow.com/questions/1534210/use-different-python-version-with-virtualenv) - For using a specific version of python with virtualenv