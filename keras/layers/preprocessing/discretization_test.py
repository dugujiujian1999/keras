import os

import numpy as np
import pytest
from absl.testing import parameterized

from keras import backend
from keras import layers
from keras import models
from keras import testing
from keras.saving import saving_api


class DiscretizationTest(testing.TestCase, parameterized.TestCase):
    def test_discretization_basics(self):
        self.run_layer_test(
            layers.Discretization,
            init_kwargs={
                "bin_boundaries": [0.0, 0.5, 1.0],
            },
            input_shape=(2, 3),
            expected_output_shape=(2, 3),
            expected_num_trainable_weights=0,
            expected_num_non_trainable_weights=0,
            expected_num_seed_generators=0,
            expected_num_losses=0,
            supports_masking=False,
            run_training_check=False,
        )

    def test_adapt_flow(self):
        layer = layers.Discretization(num_bins=4)
        layer.adapt(
            np.random.random((32, 3)),
        )
        output = layer(np.array([[0.0, 0.1, 0.3]]))
        self.assertTrue(output.dtype, "int32")

    @parameterized.parameters(
        [
            ("int", [[-1.0, 0.0, 0.1, 0.8, 1.2]], [[0, 1, 1, 2, 3]]),
            ("one_hot", [0.1, 0.8], [[0, 1, 0, 0], [0, 0, 1, 0]]),
            ("multi_hot", [[0.1, 0.8]], [[0, 1, 1, 0]]),
            (
                "one_hot",
                [[[0.15, 0.75], [0.85, 0.45]]],
                [
                    [
                        [[0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
                        [[0.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
                    ]
                ],
            ),
            (
                "multi_hot",
                [[[0.15, 0.75], [0.85, 0.45]]],
                [[[0.0, 1.0, 1.0, 0.0], [0.0, 1.0, 1.0, 0.0]]],
            ),
            ("count", [[0.1, 0.8, 0.9]], [[0, 1, 2, 0]]),
        ]
    )
    def test_correctness(self, output_mode, input_array, expected_output):
        input_array = np.array(input_array)
        expected_output = np.array(expected_output)

        layer = layers.Discretization(
            bin_boundaries=[0.0, 0.5, 1.0], output_mode=output_mode
        )
        output = layer(input_array)
        self.assertTrue(backend.is_tensor(output))
        self.assertAllClose(output, expected_output)

    @pytest.mark.skipif(
        backend.backend() != "tensorflow",
        reason="tf_data only exists in TensorFlow",
    )
    def test_tf_data_compatibility(self):
        from tensorflow import data as tf_data

        # With fixed bins
        layer = layers.Discretization(
            bin_boundaries=[0.0, 0.35, 0.5, 1.0], dtype="float32"
        )
        x = np.array([[-1.0, 0.0, 0.1, 0.2, 0.4, 0.5, 1.0, 1.2, 0.98]])
        self.assertAllClose(layer(x), np.array([[0, 1, 1, 1, 2, 3, 4, 4, 3]]))
        ds = tf_data.Dataset.from_tensor_slices(x).batch(1).map(layer)
        for output in ds.take(1):
            output = output.numpy()
        self.assertAllClose(output, np.array([[0, 1, 1, 1, 2, 3, 4, 4, 3]]))

        # With adapt flow
        layer = layers.Discretization(num_bins=4)
        layer.adapt(
            np.random.random((32, 3)),
        )
        x = np.array([[0.0, 0.1, 0.3]])
        ds = tf_data.Dataset.from_tensor_slices(x).batch(1).map(layer)
        for output in ds.take(1):
            output.numpy()

    def test_saving(self):
        # With fixed bins
        layer = layers.Discretization(bin_boundaries=[0.0, 0.35, 0.5, 1.0])
        model = models.Sequential(
            [
                layers.Input((2,)),
                layer,
            ]
        )
        fpath = os.path.join(self.get_temp_dir(), "model.keras")
        model.save(fpath)
        model = saving_api.load_model(fpath)
        x = np.array([[-1.0, 0.0, 0.1, 0.2, 0.4, 0.5, 1.0, 1.2, 0.98]])
        self.assertAllClose(layer(x), np.array([[0, 1, 1, 1, 2, 3, 4, 4, 3]]))

        # With adapt flow
        layer = layers.Discretization(num_bins=4)
        layer.adapt(
            np.random.random((32, 3)),
        )
        ref_input = np.random.random((1, 2))
        ref_output = layer(ref_input)
        model = models.Sequential(
            [
                layers.Input((2,)),
                layer,
            ]
        )
        fpath = os.path.join(self.get_temp_dir(), "model.keras")
        model.save(fpath)
        model = saving_api.load_model(fpath)
        self.assertAllClose(layer(ref_input), ref_output)

    @pytest.mark.skipif(
        backend.backend() != "tensorflow",
        reason="Sparse tensor only works in TensorFlow",
    )
    def test_sparse_inputs(self):
        from tensorflow import sparse

        x = sparse.from_dense(np.array([[-1.0, 0.2, 0.7, 1.2]]))
        layer = layers.Discretization(bin_boundaries=[0.0, 0.5, 1.0])
        output = layer(x)
        self.assertTrue(backend.is_tensor(output))
        self.assertAllClose(output, np.array([[0, 1, 2, 3]]))
