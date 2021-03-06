import json
import requests
import time
import logging
import os
import glob

import numpy as np
import tensorflow as tf
import keras.backend as K

from core.metrics import HistoryMetric
from metrics import inception_score
from metrics import mmd


def to_rgb(x):
    x = x * 255.
    if x.shape[3] == 1:
        n, w, h, _ = x.shape
        ret = np.empty((n, w, h, 3), dtype=np.uint8)
        ret[:, :, :, 2] = ret[:, :, :, 1] = ret[:, :, :, 0] = x[:, :, :, 0]
    else:
        ret = x
    return ret


def get_latest_file_from_path(path):
    list_of_files = glob.glob(path)  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


class InceptionScore(HistoryMetric):
    name = 'inception_score'
    input_type = 'generated_and_real_samples'

    def compute(self, input_data):
        x_hat, _ = input_data
        mean, std = inception_score.get_inception_score(to_rgb(x_hat))
        return mean


class RemoteInceptionScore(HistoryMetric):
    name = 'r_inception_score'
    input_type = 'generated_and_real_samples'

    def __init__(self, experiment_id, output='output', **kwargs):
        super().__init__()
        self.precomputed_file_path = os.path.join(
            output, experiment_id,
            'tmp/precomputed_generated_and_real_samples_*')

    def compute(self, input_data):
        server = 'localhost'
        with open("server_for_inception_score.config") as f:
            server = f.readline()
            server = server.rstrip()
        filename = get_latest_file_from_path(self.precomputed_file_path)
        json_data = {'filename': filename}
        start = time.time()
        headers = {'Content-Type': 'application/json'}
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        r = requests.post("http://{}:{}/inception-score".format(server, 5000),
                          headers=headers,
                          data=json.dumps(json_data))
        print("[Remote IS] Total request took {}s".format(time.time() - start))
        response_data = json.loads(r.text)
        print("[Remote IS] Computation took {}s".format(response_data['computation_time']))
        return float(response_data['mean'])


class MaximumMeanDiscrepancy(HistoryMetric):
    name = 'mmd'
    input_type = 'generated_and_real_samples'

    def __init__(self, input_shape=(32, 32, 1), **kwargs):
        super().__init__()
        x_ph = tf.placeholder(tf.float32, shape=[None] + list(input_shape), name='mmd_x')
        x_hat_ph = tf.placeholder(tf.float32, shape=[None] + list(input_shape), name='mmd_x_hat')
        x_flat = K.batch_flatten(x_ph)
        x_hat_flat = K.batch_flatten(x_hat_ph)
        self.mmd_computer = tf.log(mmd.rbf_mmd2(x_flat, x_hat_flat))

    def compute(self, input_data):
        x_hat, x = input_data
        mmd = K.get_session().run(self.mmd_computer, feed_dict={'mmd_x:0': x, 'mmd_x_hat:0': x_hat})
        return mmd
