# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Implements the Keras Sequential model."""

from builtins import range
from ntpath import basename
import os

import keras

from keras import backend as K
from keras import layers
from keras import models
from keras.backend import relu

import pandas as pd
import tensorflow as tf

from tensorflow.python.saved_model import builder as saved_model_builder
from tensorflow.python.saved_model import signature_constants
from tensorflow.python.saved_model import tag_constants
from tensorflow.python.saved_model.signature_def_utils_impl import predict_signature_def
from tensorflow.python.lib.io import file_io

# CSV columns in the input file. -- MUST INCLUDE ALL COLUMNS!
CSV_COLUMNS = ('O1','H1','L1','C1','O2','H2','L2','C2','O3','H3','L3','C3','O4','H4','L4','C4','V1','V2','V3','V4','O5','H5','L5','C5','V5','O6','H6','L6','C6')

# For all categorical columns, use a [''] instead
CSV_COLUMN_DEFAULTS = [[0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0],
                       [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0], [0]]

# Add categorical columns like so: CATEGORICAL_COLS = (('col title', number of categories in col), ('col2 title', number of categories in col2), . . .)
CATEGORICAL_COLS = ()

# Note: do not add continuous columns that you want to be in the output
CONTINUOUS_COLS = ('O1','H1','L1','C1','O2','H2','L2','C2','O3','H3','L3','C3','O4','H4','L4','C4','V1','V2','V3','V4','O5','H5','L5','C5','V5')

# These represent the columns that the model will be trained to predict
LABEL_COLUMNS = ('O6','H6','L6','C6')

# Zip up and create a list of the categorical columns
ZIPPED_CATEGORICAL_COLS = list(zip(*CATEGORICAL_COLS))
CAT_COLS = ()
# Check if empty, if not, use the first
if len(ZIPPED_CATEGORICAL_COLS) > 0:
    CAT_COLS = ZIPPED_CATEGORICAL_COLS[0]

# Calculate what the unused columns are
UNUSED_COLUMNS = set(CSV_COLUMNS) - set(CAT_COLS + CONTINUOUS_COLS + LABEL_COLUMNS)


def model_fn(input_dim,
             labels_dim,
             hidden_units=[100, 70, 50, 20],
             learning_rate=0.1):
  """Create a Keras Sequential model with layers.

  Args:
    input_dim: (int) Input dimensions for input layer.
    labels_dim: (int) Label dimensions for input layer.
    hidden_units: [int] the layer sizes of the DNN (input layer first)
    learning_rate: (float) the learning rate for the optimizer.

  Returns:
    A Keras model.
  """

  # "set_learning_phase" to False to avoid:
  # AbortionError(code=StatusCode.INVALID_ARGUMENT during online prediction.
  K.set_learning_phase(False)
  model = models.Sequential()

  for units in hidden_units:
    model.add(layers.Dense(units=units, input_dim=input_dim, activation=relu))
    input_dim = units

  # Add a dense final layer
  model.add(layers.Dense(labels_dim))
  compile_model(model, learning_rate)
  return model


def compile_model(model, learning_rate):
  model.compile(
      loss='mse',
      optimizer=keras.optimizers.RMSprop(lr=learning_rate),
      metrics=['mae', 'mse'])
  return model


def _save_oncloud(model, export_path):
    tmpPath = './tmp_folder'
    ### Allow overwriting of export_path if it already exists by removing it first..
    if file_io.file_exists(tmpPath):
        # print("Need to overwrite preexisting path. Recursively deleting... ", tmpPath)
        file_io.delete_recursively(tmpPath)

    builder = saved_model_builder.SavedModelBuilder(tmpPath)

    signature = predict_signature_def(
        inputs={'input': model.inputs[0]}, outputs={'income': model.outputs[0]})

    with K.get_session() as sess:
        builder.add_meta_graph_and_variables(
            sess=sess,
            tags=[tag_constants.SERVING],
            signature_def_map={
                signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY: signature
            })

    # Relevant to here: http://liufuyang.github.io/2017/04/02/just-another-tensorflow-beginner-guide-4.html
    # Also, similar hack done in task.py
    modelSavePath = builder.save()

    # Save model on to google storage
    with file_io.FileIO(modelSavePath, mode='rb') as input_f:
        with file_io.FileIO(os.path.join(export_path, basename(modelSavePath)), mode='w+') as output_f:
            output_f.write(input_f.read())

def to_savedmodel(model, export_path):
  """Convert the Keras HDF5 model into TensorFlow SavedModel."""
  if export_path.startswith('gs://'):
      _save_oncloud(model, export_path)
  else:
      ### Allow overwriting of export_path if it already exists by removing it first..
      if file_io.file_exists(export_path):
          file_io.delete_recursively(export_path)

      builder = saved_model_builder.SavedModelBuilder(export_path)

      signature = predict_signature_def(
          inputs={'input': model.inputs[0]}, outputs={'income': model.outputs[0]})

      with K.get_session() as sess:
          builder.add_meta_graph_and_variables(
              sess=sess,
              tags=[tag_constants.SERVING],
              signature_def_map={
                  signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY: signature
              })
          builder.save()



def to_numeric_features(features, feature_cols=None):
  """Converts the pandas input features to numeric values.

  Args:
    features: Input features in the data age (continuous) workclass
      (categorical) fnlwgt (continuous) education (categorical) education_num
      (continuous) marital_status (categorical) occupation (categorical)
      relationship (categorical) race (categorical) gender (categorical)
      capital_gain (continuous) capital_loss (continuous) hours_per_week
      (continuous) native_country (categorical)
    feature_cols: Column list of converted features to be returned. Optional,
      may be used to ensure schema consistency over multiple executions.

  Returns:
    A pandas dataframe.
  """

  for col in CATEGORICAL_COLS:
    features = pd.concat(
        [features, pd.get_dummies(features[col[0]], drop_first=True)], axis=1)
    features.drop(col[0], axis=1, inplace=True)

  # Remove the unused columns from the dataframe.
  for col in UNUSED_COLUMNS:
    features.pop(col)

  # Re-index dataframe (if categories list changed from the previous dataset)
  if feature_cols is not None:
    features = features.T.reindex(feature_cols).T.fillna(0)
  return features


def generator_input(filenames, chunk_size, batch_size=64):
  """Produce features and labels needed by keras fit_generator."""

  feature_cols = None
  while True:
    input_reader = pd.read_csv(
        tf.gfile.Open(filenames[0]),
        names=CSV_COLUMNS,
        chunksize=chunk_size,
        na_values=' ?')

    for input_data in input_reader:
      input_data = input_data.dropna()
      # Pop off all of the columns we want to predict and concatenate them
      labels = pd.concat([input_data.pop(x) for x in LABEL_COLUMNS], 1)

      input_data = to_numeric_features(input_data, feature_cols)

      # Retains schema for next chunk processing.
      if feature_cols is None:
        feature_cols = input_data.columns

      idx_len = input_data.shape[0]
      for index in range(0, idx_len, batch_size):
        yield (input_data.iloc[index:min(idx_len, index + batch_size)],
               labels.iloc[index:min(idx_len, index + batch_size)])
