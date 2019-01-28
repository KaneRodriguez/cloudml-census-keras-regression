### Modified Open Source Keras version of the Census sample

This sample enables easy training of a multiple output regression Keras model with hyperparemeter tuning and distributed training, all on the Google ML Engine or locally with the gcloud sdk :)

## Assign the data

The following will assign your local and gcloud hosted training and evaluation data as well as create a bucket from your current gcloud project.

Note: If you do not have a gcloud project, give [this](https://cloud.google.com/ml-engine/docs/tensorflow/getting-started-training-prediction) a read.

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
TRAIN_STEPS=2000
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
JOB_DIR=gs://$BUCKET_NAME/$JOB_NAME
TRAIN_STEPS=200
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.12 \
                                    --job-dir $JOB_DIR \
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
JOB_NAME=output_keras_dist
JOB_DIR=gs://$BUCKET_NAME/$JOB_NAME
TRAIN_STEPS=10
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.4 \
                                    --job-dir $JOB_DIR \
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

## Distributed Training using Cloud ML Engine and Hyperparameter Tuning

You can train the model on Cloud ML Engine in distributed mode and take advantage of hyperparameter tuning.

```
JOB_NAME=output_keras_htune_dist_999
JOB_DIR=gs://$BUCKET_NAME/$JOB_NAME
TRAIN_STEPS=20
HPTUNING_CONFIG=hptuning_config.yaml
gcloud ml-engine jobs submit training $JOB_NAME \
                                    --stream-logs \
                                    --runtime-version 1.4 \
                                    --job-dir $JOB_DIR \
                                    --package-path trainer \
                                    --config $HPTUNING_CONFIG \
                                    --module-name trainer.task \
                                    --region $REGION \
                                    --scale-tier STANDARD_1 \
                                    -- \
                                    --train-files $GCS_TRAIN_FILE \
                                    --eval-files $GCS_EVAL_FILE \
                                    --train-steps $TRAIN_STEPS \
                                    --distributed True \
                                    --hypertune True
```

## Prediction using Cloud ML Engine

You can perform prediction on Cloud ML Engine by following the steps below.
Create a model on Cloud ML Engine

```
MODEL_NAME=${JOB_NAME}_model
MODEL_VERSION=v1
gcloud ml-engine models create $MODEL_NAME --regions $REGION
```

Export the model binaries

```
MODEL_BINARIES=$JOB_DIR/export
```

Note: If using hypertuning model:

* go to the storage bucket for this project on Google Cloud Platform 
* enter the folder for the hypertune job you want to use for prediction
* take note of the last folder created (highest number)
* use that number below in place of ITERATION_NUMBER

```
ITERATION_NUMBER=2
MODEL_BINARIES=$JOB_DIR/$ITERATION_NUMBER/export
```


Deploy the model to the prediction service

```
gcloud ml-engine versions create $MODEL_VERSION --model $MODEL_NAME --origin $MODEL_BINARIES --runtime-version 1.4
```

Create a processed sample from the data

```
python preprocess.py test.json
```

Run the online prediction

```
gcloud ml-engine predict --model $MODEL_NAME --version $MODEL_VERSION --json-instances test.json --runtime-version 1.4
```

## Resources

* [Here](https://stackoverflow.com/questions/1534210/use-different-python-version-with-virtualenv) - For using a specific version of python with virtualenv
