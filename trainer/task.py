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
"""This code implements a Feed forward neural network using Keras API."""

import argparse
import glob
import json
import os

from keras.callbacks import Callback
from keras.callbacks import ModelCheckpoint
from keras.callbacks import TensorBoard
from keras.models import load_model

from tensorflow.python.lib.io import file_io
from tensorflow.core.framework.summary_pb2 import Summary
import tensorflow as tf

import trainer.model as model

INPUT_SIZE = 25
CLASS_SIZE = 4

# CHUNK_SIZE specifies the number of lines
# to read in case the file is very large
CHUNK_SIZE = 5000
CHECKPOINT_FILE_PATH = 'checkpoint.{epoch:02d}-{mean_squared_error:.2f}.hdf5'
CENSUS_MODEL = 'output_model.hdf5'


class ContinuousEval(Callback):
  """Continuous eval callback to evaluate the checkpoint once

     every so many epochs.
  """

  def __init__(self,
               eval_frequency,
               eval_files,
               learning_rate,
               job_dir,
               steps=1000):
    self.eval_files = eval_files
    self.eval_frequency = eval_frequency
    self.learning_rate = learning_rate
    self.job_dir = job_dir
    self.steps = steps
    self.last_loss_val = None

  def on_epoch_begin(self, epoch, logs={}):
    """Compile and save model."""

    if epoch > 0 and epoch % self.eval_frequency == 0:
      # Unhappy hack to work around h5py not being able to write to GCS.
      # Force snapshots and saves to local filesystem, then copy them over to GCS.
      model_path_glob = 'checkpoint.*'
      if not self.job_dir.startswith('gs://'):
        model_path_glob = os.path.join(self.job_dir, model_path_glob)
      checkpoints = glob.glob(model_path_glob)
      if len(checkpoints) > 0:
        checkpoints.sort()
        census_model = load_model(checkpoints[-1])
        census_model = model.compile_model(census_model, self.learning_rate)
        loss, mae, mse = census_model.evaluate_generator(
            model.generator_input(self.eval_files, chunk_size=CHUNK_SIZE),
            steps=self.steps)
        self.last_loss_val = loss
        print('\nEvaluation epoch[{}] metrics[{:.2f}, {:.2f}, {:.2f}] {}'.format(
            epoch, loss, mae, mse, census_model.metrics_names))
        if self.job_dir.startswith('gs://'):
          copy_file_to_gcs(self.job_dir, checkpoints[-1])
      else:
        print('\nEvaluation epoch[{}] (no checkpoints found)'.format(epoch))


def train_and_evaluate(args):
  # Showcasing the hypertuning parameters here.
  # The first-layer-size is being tuned in this example
  hidden_units = [args.first_layer_size, 70, 50, 20]
  census_model = model.model_fn(INPUT_SIZE, CLASS_SIZE, hidden_units)
  try:
    os.makedirs(args.job_dir)
  except:
    pass

  # Unhappy hack to workaround h5py not being able to write to GCS.
  # Force snapshots and saves to local filesystem, then copy them over to GCS.
  checkpoint_path = CHECKPOINT_FILE_PATH
  if not args.job_dir.startswith('gs://'):
    checkpoint_path = os.path.join(args.job_dir, checkpoint_path)

  # Model checkpoint callback.
  checkpoint = ModelCheckpoint(
      checkpoint_path,
      monitor='val_loss',
      verbose=1,
      save_best_only=False,
      period=args.checkpoint_epochs,
      mode='min')

  # Continuous eval callback.
  evaluation = ContinuousEval(args.eval_frequency, args.eval_files,
															args.learning_rate, args.job_dir)

  # Tensorboard logs callback.
  tb_log = TensorBoard(
      log_dir=os.path.join(args.job_dir, 'logs'),
      histogram_freq=0,
      write_graph=True,
      embeddings_freq=0)

  callbacks = [checkpoint, evaluation, tb_log]

  census_model.fit_generator(
      model.generator_input(args.train_files, chunk_size=CHUNK_SIZE),
      steps_per_epoch=args.train_steps,
      epochs=args.num_epochs,
      use_multiprocessing=args.distributed,
      callbacks=callbacks)

  # Unhappy hack to workaround h5py not being able to write to GCS.
  # Force snapshots and saves to local filesystem, then copy them over to GCS.
  if args.job_dir.startswith('gs://'):
    census_model.save(CENSUS_MODEL)
    copy_file_to_gcs(args.job_dir, CENSUS_MODEL)
  else:
    census_model.save(os.path.join(args.job_dir, CENSUS_MODEL))

  # Convert the Keras model to TensorFlow SavedModel.
  model.to_savedmodel(census_model, os.path.join(args.job_dir, 'export'))

  # The following is for hyperparameter tuning and is adapted from here: https://cloud.google.com/ml-engine/docs/tensorflow/using-hyperparameter-tuning
  # Note: the last_loss_val is updated after each checkpoint, but we only write the summary once.
  summary = Summary(value=[Summary.Value(tag='val_loss', simple_value=evaluation.last_loss_val)])

  # more hypertune info here: https://cloud.google.com/solutions/machine-learning/recommendation-system-tensorflow-train-cloud-ml-engine

  job_dir = args.job_dir

  if args.hypertune:
      # if tuning, join the trial number to the output path
      trial = json.loads(os.environ.get('TF_CONFIG', '{}')).get('task', {}).get('trial', '')
      output_dir = os.path.join(job_dir, trial)
  else:
      output_dir = job_dir

  eval_path = os.path.join(output_dir, 'val_loss')
  summary_writer = tf.summary.FileWriter(eval_path)

  # Note: adding the summary to the writer is enough for hyperparameter tuning.
  # ML Engine looks for any summary added with the hyperparameter metric tag.
  summary_writer.add_summary(summary)
  summary_writer.flush()


# h5py workaround: copy local models over to GCS if the job_dir is GCS.
def copy_file_to_gcs(job_dir, file_path):
  with file_io.FileIO(file_path, mode='rb') as input_f:
    with file_io.FileIO(
        os.path.join(job_dir, file_path), mode='w+') as output_f:
      output_f.write(input_f.read())


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--train-files',
      nargs='+',
      help='Training file local or GCS')
  parser.add_argument(
      '--eval-files',
      nargs='+',
      help='Evaluation file local or GCS')
  parser.add_argument(
      '--job-dir',
      type=str,
      help='GCS or local dir to write checkpoints and export model',
      default='/tmp/census-keras')
  parser.add_argument(
      '--train-steps',
      type=int,
      default=100,
      help="""\
        Maximum number of training steps to perform
        Training steps are in the units of training-batch-size.
        So if train-steps is 500 and train-batch-size if 100 then
        at most 500 * 100 training instances will be used to train.""")
  parser.add_argument(
      '--eval-steps',
      help='Number of steps to run evalution for at each checkpoint',
      default=100,
      type=int)
  parser.add_argument(
      '--train-batch-size',
      type=int,
      default=40,
      help='Batch size for training steps')
  parser.add_argument(
      '--eval-batch-size',
      type=int,
      default=40,
      help='Batch size for evaluation steps')
  parser.add_argument(
      '--learning-rate',
      type=float,
      default=0.003,
      help='Learning rate for SGD')
  parser.add_argument(
      '--eval-frequency',
      default=10,
      help='Perform one evaluation per n epochs')
  parser.add_argument(
      '--first-layer-size',
      type=int,
      default=100,
      help='Number of nodes in the first layer of DNN')
  parser.add_argument(
      '--num-layers',
      type=int,
      default=4,
      help='Number of layers in DNN')
  parser.add_argument(
      '--scale-factor',
      type=float,
      default=0.25,
      help="""Rate of decay size of layer for Deep Neural Net.
        max(2, int(first_layer_size * scale_factor**i))""")
  parser.add_argument(
      '--eval-num-epochs',
      type=int,
      default=1,
      help='Number of epochs during evaluation')
  parser.add_argument(
      '--num-epochs',
      type=int,
      default=20,
      help='Maximum number of epochs on which to train')
  parser.add_argument(
      '--checkpoint-epochs',
      type=int,
      default=5,
      help='Checkpoint per n training epochs')
  parser.add_argument(
      '--distributed',
      type=bool,
      default=False,
      help='Is this model going to be trained distributed or not')
  parser.add_argument(
      '--hypertune',
      type=bool,
      default=False,
      help='Is this model going to be trained hypertuned or not')

  args, _ = parser.parse_known_args()
  train_and_evaluate(args)
