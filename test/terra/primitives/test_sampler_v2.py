# This code is part of Qiskit.
#
# (C) Copyright IBM 2024.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for Sampler V2."""

from __future__ import annotations

import unittest
from test.terra.common import QiskitAerTestCase

import numpy as np
from numpy.typing import NDArray
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit import Parameter
from qiskit.circuit.library import RealAmplitudes, UnitaryGate
from qiskit.primitives import PrimitiveResult, SamplerPubResult, StatevectorSampler
from qiskit.primitives.containers import BitArray
from qiskit.primitives.containers.data_bin import DataBin
from qiskit.primitives.containers.sampler_pub import SamplerPub
from qiskit.providers import JobStatus
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2


class TestSamplerV2(QiskitAerTestCase):
    """Test for SamplerV2"""

    def setUp(self):
        super().setUp()
        self._shots = 10000
        self._seed = 123
        self._options = {"default_shots": self._shots, "seed": self._seed}

        self._cases = []
        hadamard = QuantumCircuit(1, 1, name="Hadamard")
        hadamard.h(0)
        hadamard.measure(0, 0)
        self._cases.append((hadamard, None, {0: 5000, 1: 5000}))  # case 0

        bell = QuantumCircuit(2, name="Bell")
        bell.h(0)
        bell.cx(0, 1)
        bell.measure_all()
        self._cases.append((bell, None, {0: 5000, 3: 5000}))  # case 1

        pqc = RealAmplitudes(num_qubits=2, reps=2)
        pqc.measure_all()
        self._cases.append((pqc, [0] * 6, {0: 10000}))  # case 2
        self._cases.append((pqc, [1] * 6, {0: 168, 1: 3389, 2: 470, 3: 5973}))  # case 3
        self._cases.append((pqc, [0, 1, 1, 2, 3, 5], {0: 1339, 1: 3534, 2: 912, 3: 4215}))  # case 4
        self._cases.append((pqc, [1, 2, 3, 4, 5, 6], {0: 634, 1: 291, 2: 6039, 3: 3036}))  # case 5

        pqc2 = RealAmplitudes(num_qubits=2, reps=3)
        pqc2.measure_all()
        self._cases.append(
            (pqc2, [0, 1, 2, 3, 4, 5, 6, 7], {0: 1898, 1: 6864, 2: 928, 3: 311})
        )  # case 6

    def _assert_allclose(self, bitarray: BitArray, target: NDArray | BitArray, rtol=1e-1, atol=5e2):
        self.assertEqual(bitarray.shape, target.shape)
        for idx in np.ndindex(bitarray.shape):
            int_counts = bitarray.get_int_counts(idx)
            target_counts = (
                target.get_int_counts(idx) if isinstance(target, BitArray) else target[idx]
            )
            max_key = max(max(int_counts.keys()), max(target_counts.keys()))
            ary = np.array([int_counts.get(i, 0) for i in range(max_key + 1)])
            tgt = np.array([target_counts.get(i, 0) for i in range(max_key + 1)])
            np.testing.assert_allclose(ary, tgt, rtol=rtol, atol=atol, err_msg=f"index: {idx}")

    def test_sampler_run(self):
        """Test run()."""

        with self.subTest("single"):
            bell, _, target = self._cases[1]
            pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
            bell = pm.run(bell)
            sampler = SamplerV2(**self._options)
            job = sampler.run([bell], shots=self._shots)
            result = job.result()
            self.assertIsInstance(result, PrimitiveResult)
            self.assertIsInstance(result.metadata, dict)
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], SamplerPubResult)
            self.assertIsInstance(result[0].data, DataBin)
            self.assertIsInstance(result[0].data.meas, BitArray)
            self._assert_allclose(result[0].data.meas, np.array(target))
            self.assertIn("simulator_metadata", result[0].metadata)

        with self.subTest("single with param"):
            pqc, param_vals, target = self._cases[2]
            sampler = SamplerV2(**self._options)
            pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
            pqc = pm.run(pqc)
            params = (param.name for param in pqc.parameters)
            job = sampler.run([(pqc, {params: param_vals})], shots=self._shots)
            result = job.result()
            self.assertIsInstance(result, PrimitiveResult)
            self.assertIsInstance(result.metadata, dict)
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], SamplerPubResult)
            self.assertIsInstance(result[0].data, DataBin)
            self.assertIsInstance(result[0].data.meas, BitArray)
            self._assert_allclose(result[0].data.meas, np.array(target))
            self.assertIn("simulator_metadata", result[0].metadata)

        with self.subTest("multiple"):
            pqc, param_vals, target = self._cases[2]
            sampler = SamplerV2(**self._options)
            pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
            pqc = pm.run(pqc)
            params = (param.name for param in pqc.parameters)
            job = sampler.run(
                [(pqc, {params: [param_vals, param_vals, param_vals]})], shots=self._shots
            )
            result = job.result()
            self.assertIsInstance(result, PrimitiveResult)
            self.assertIsInstance(result.metadata, dict)
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], SamplerPubResult)
            self.assertIsInstance(result[0].data, DataBin)
            self.assertIsInstance(result[0].data.meas, BitArray)
            self._assert_allclose(result[0].data.meas, np.array([target, target, target]))
            self.assertIn("simulator_metadata", result[0].metadata)

    def test_sampler_run_multiple_times(self):
        """Test run() returns the same results if the same input is given."""
        bell, _, _ = self._cases[1]
        sampler = SamplerV2(**self._options)
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        bell = pm.run(bell)
        result1 = sampler.run([bell], shots=self._shots).result()
        meas1 = result1[0].data.meas
        result2 = sampler.run([bell], shots=self._shots).result()
        meas2 = result2[0].data.meas
        self._assert_allclose(meas1, meas2, rtol=0)

    def test_sample_run_multiple_circuits(self):
        """Test run() with multiple circuits."""
        bell, _, target = self._cases[1]
        sampler = SamplerV2(**self._options)
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        bell = pm.run(bell)
        result = sampler.run([bell, bell, bell], shots=self._shots).result()
        self.assertEqual(len(result), 3)
        self._assert_allclose(result[0].data.meas, np.array(target))
        self._assert_allclose(result[1].data.meas, np.array(target))
        self._assert_allclose(result[2].data.meas, np.array(target))

    def test_sampler_run_with_parameterized_circuits(self):
        """Test run() with parameterized circuits."""
        pqc1, param1, target1 = self._cases[4]
        pqc2, param2, target2 = self._cases[5]
        pqc3, param3, target3 = self._cases[6]
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        pqc1, pqc2, pqc3 = pm.run([pqc1, pqc2, pqc3])

        sampler = SamplerV2(**self._options)
        result = sampler.run(
            [(pqc1, param1), (pqc2, param2), (pqc3, param3)], shots=self._shots
        ).result()
        self.assertEqual(len(result), 3)
        self._assert_allclose(result[0].data.meas, np.array(target1))
        self._assert_allclose(result[1].data.meas, np.array(target2))
        self._assert_allclose(result[2].data.meas, np.array(target3))

    def test_run_1qubit(self):
        """test for 1-qubit cases"""
        qc = QuantumCircuit(1)
        qc.measure_all()
        qc2 = QuantumCircuit(1)
        qc2.x(0)
        qc2.measure_all()
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc, qc2 = pm.run([qc, qc2])

        sampler = SamplerV2(**self._options)
        result = sampler.run([qc, qc2], shots=self._shots).result()
        self.assertEqual(len(result), 2)
        for i in range(2):
            self._assert_allclose(result[i].data.meas, np.array({i: self._shots}))

    def test_run_2qubit(self):
        """test for 2-qubit cases"""
        qc0 = QuantumCircuit(2)
        qc0.measure_all()
        qc1 = QuantumCircuit(2)
        qc1.x(0)
        qc1.measure_all()
        qc2 = QuantumCircuit(2)
        qc2.x(1)
        qc2.measure_all()
        qc3 = QuantumCircuit(2)
        qc3.x([0, 1])
        qc3.measure_all()
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc0, qc1, qc2, qc3 = pm.run([qc0, qc1, qc2, qc3])

        sampler = SamplerV2(**self._options)
        result = sampler.run([qc0, qc1, qc2, qc3], shots=self._shots).result()
        self.assertEqual(len(result), 4)
        for i in range(4):
            self._assert_allclose(result[i].data.meas, np.array({i: self._shots}))

    def test_run_single_circuit(self):
        """Test for single circuit case."""
        sampler = SamplerV2(**self._options)
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())

        with self.subTest("No parameter"):
            circuit, _, target = self._cases[1]
            circuit = pm.run(circuit)
            param_target = [
                (None, np.array(target)),
                ({}, np.array(target)),
            ]
            for param, target in param_target:
                with self.subTest(f"{circuit.name} w/ {param}"):
                    result = sampler.run([(circuit, param)], shots=self._shots).result()
                    self.assertEqual(len(result), 1)
                    self._assert_allclose(result[0].data.meas, target)

        with self.subTest("One parameter"):
            circuit = QuantumCircuit(1, 1, name="X gate")
            param = Parameter("x")
            circuit.ry(param, 0)
            circuit.measure(0, 0)
            circuit = pm.run(circuit)
            param_target = [
                ({"x": np.pi}, np.array({1: self._shots})),
                ({param: np.pi}, np.array({1: self._shots})),
                ({"x": np.array(np.pi)}, np.array({1: self._shots})),
                ({param: np.array(np.pi)}, np.array({1: self._shots})),
                ({"x": [np.pi]}, np.array({1: self._shots})),
                ({param: [np.pi]}, np.array({1: self._shots})),
                ({"x": np.array([np.pi])}, np.array({1: self._shots})),
                ({param: np.array([np.pi])}, np.array({1: self._shots})),
            ]
            for param, target in param_target:
                with self.subTest(f"{circuit.name} w/ {param}"):
                    result = sampler.run([(circuit, param)], shots=self._shots).result()
                    self.assertEqual(len(result), 1)
                    self._assert_allclose(result[0].data.c, target)

        with self.subTest("More than one parameter"):
            circuit, param, target = self._cases[3]
            circuit = pm.run(circuit)
            param_target = [
                (param, np.array(target)),
                (tuple(param), np.array(target)),
                (np.array(param), np.array(target)),
                ((param,), np.array([target])),
                ([param], np.array([target])),
                (np.array([param]), np.array([target])),
            ]
            for param, target in param_target:
                with self.subTest(f"{circuit.name} w/ {param}"):
                    result = sampler.run([(circuit, param)], shots=self._shots).result()
                    self.assertEqual(len(result), 1)
                    self._assert_allclose(result[0].data.meas, target)

    def test_run_reverse_meas_order(self):
        """test for sampler with reverse measurement order"""
        x = Parameter("x")
        y = Parameter("y")

        qc = QuantumCircuit(3, 3)
        qc.rx(x, 0)
        qc.rx(y, 1)
        qc.x(2)
        qc.measure(0, 2)
        qc.measure(1, 1)
        qc.measure(2, 0)
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc = pm.run(qc)

        sampler = SamplerV2(**self._options)
        sampler.options.seed_simulator = self._seed
        result = sampler.run([(qc, [0, 0]), (qc, [np.pi / 2, 0])], shots=self._shots).result()
        self.assertEqual(len(result), 2)

        # qc({x: 0, y: 0})
        self._assert_allclose(result[0].data.c, np.array({1: self._shots}))

        # qc({x: pi/2, y: 0})
        self._assert_allclose(result[1].data.c, np.array({1: self._shots / 2, 5: self._shots / 2}))

    def test_run_errors(self):
        """Test for errors with run method"""
        qc1 = QuantumCircuit(1)
        qc1.measure_all()
        qc2 = RealAmplitudes(num_qubits=1, reps=1)
        qc2.measure_all()
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc1, qc2 = pm.run([qc1, qc2])

        sampler = SamplerV2(**self._options)
        with self.subTest("set parameter values to a non-parameterized circuit"):
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc1, [1e2])]).result()
        with self.subTest("missing all parameter values for a parameterized circuit"):
            with self.assertRaises(ValueError):
                _ = sampler.run([qc2]).result()
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc2, [])]).result()
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc2, None)]).result()
        with self.subTest("missing some parameter values for a parameterized circuit"):
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc2, [1e2])]).result()
        with self.subTest("too many parameter values for a parameterized circuit"):
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc2, [1e2] * 100)]).result()
        with self.subTest("negative shots, run arg"):
            with self.assertRaises(ValueError):
                _ = sampler.run([qc1], shots=-1).result()
        with self.subTest("negative shots, pub-like"):
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc1, None, -1)]).result()
        with self.subTest("negative shots, pub"):
            with self.assertRaises(ValueError):
                _ = sampler.run([SamplerPub(qc1, shots=-1)]).result()
        with self.subTest("zero shots, run arg"):
            with self.assertRaises(ValueError):
                _ = sampler.run([qc1], shots=0).result()
        with self.subTest("zero shots, pub-like"):
            with self.assertRaises(ValueError):
                _ = sampler.run([(qc1, None, 0)]).result()
        with self.subTest("zero shots, pub"):
            with self.assertRaises(ValueError):
                _ = sampler.run([SamplerPub(qc1, shots=0)]).result()
        with self.subTest("missing []"):
            with self.assertRaisesRegex(ValueError, "An invalid Sampler pub-like was given"):
                _ = sampler.run(qc1).result()
        with self.subTest("missing [] for pqc"):
            with self.assertRaisesRegex(ValueError, "Note that if you want to run a single pub,"):
                _ = sampler.run((qc2, [0, 1])).result()

    def test_run_empty_parameter(self):
        """Test for empty parameter"""
        n = 5
        qc = QuantumCircuit(n, n - 1)
        qc.measure(range(n - 1), range(n - 1))
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc = pm.run(qc)
        sampler = SamplerV2(**self._options)
        with self.subTest("one circuit"):
            result = sampler.run([qc], shots=self._shots).result()
            self.assertEqual(len(result), 1)
            self._assert_allclose(result[0].data.c, np.array({0: self._shots}))

        with self.subTest("two circuits"):
            result = sampler.run([qc, qc], shots=self._shots).result()
            self.assertEqual(len(result), 2)
            for i in range(2):
                self._assert_allclose(result[i].data.c, np.array({0: self._shots}))

    def test_run_numpy_params(self):
        """Test for numpy array as parameter values"""
        qc = RealAmplitudes(num_qubits=2, reps=2)
        qc.measure_all()
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc = pm.run(qc)
        k = 5
        params_array = np.linspace(0, 1, k * qc.num_parameters).reshape((k, qc.num_parameters))
        params_list = params_array.tolist()
        sampler = StatevectorSampler(seed=self._seed)
        target = sampler.run([(qc, params_list)], shots=self._shots).result()

        with self.subTest("ndarray"):
            sampler = SamplerV2(**self._options)
            result = sampler.run([(qc, params_array)], shots=self._shots).result()
            self.assertEqual(len(result), 1)
            self._assert_allclose(result[0].data.meas, target[0].data.meas)

        with self.subTest("split a list"):
            sampler = SamplerV2(**self._options)
            result = sampler.run(
                [(qc, params) for params in params_list], shots=self._shots
            ).result()
            self.assertEqual(len(result), k)
            for i in range(k):
                self._assert_allclose(
                    result[i].data.meas, np.array(target[0].data.meas.get_int_counts(i))
                )

    def test_run_with_shots_option(self):
        """test with shots option."""
        bell, _, _ = self._cases[1]
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        bell = pm.run(bell)
        shots = 100

        with self.subTest("run arg"):
            sampler = SamplerV2(**self._options)
            result = sampler.run([bell], shots=shots).result()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].data.meas.num_shots, shots)
            self.assertEqual(sum(result[0].data.meas.get_counts().values()), shots)

        with self.subTest("default shots"):
            sampler = SamplerV2(**self._options)
            default_shots = sampler.default_shots
            result = sampler.run([bell]).result()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].data.meas.num_shots, default_shots)
            self.assertEqual(sum(result[0].data.meas.get_counts().values()), default_shots)

        with self.subTest("pub-like"):
            sampler = SamplerV2(**self._options)
            result = sampler.run([(bell, None, shots)]).result()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].data.meas.num_shots, shots)
            self.assertEqual(sum(result[0].data.meas.get_counts().values()), shots)

        with self.subTest("pub"):
            sampler = SamplerV2(**self._options)
            result = sampler.run([SamplerPub(bell, shots=shots)]).result()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].data.meas.num_shots, shots)
            self.assertEqual(sum(result[0].data.meas.get_counts().values()), shots)

        with self.subTest("multiple pubs"):
            sampler = SamplerV2(**self._options)
            shots1 = 100
            shots2 = 200
            result = sampler.run(
                [
                    SamplerPub(bell, shots=shots1),
                    SamplerPub(bell, shots=shots2),
                ],
                shots=self._shots,
            ).result()
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].data.meas.num_shots, shots1)
            self.assertEqual(sum(result[0].data.meas.get_counts().values()), shots1)
            self.assertEqual(result[1].data.meas.num_shots, shots2)
            self.assertEqual(sum(result[1].data.meas.get_counts().values()), shots2)

    def test_run_shots_result_size(self):
        """test with shots option to validate the result size"""
        n = 7  # should be less than or equal to the number of qubits of backend
        qc = QuantumCircuit(n)
        qc.h(range(n))
        qc.measure_all()
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        qc = pm.run(qc)
        sampler = SamplerV2(**self._options)
        result = sampler.run([qc], shots=self._shots).result()
        self.assertEqual(len(result), 1)
        self.assertLessEqual(result[0].data.meas.num_shots, self._shots)
        self.assertEqual(sum(result[0].data.meas.get_counts().values()), self._shots)

    def test_primitive_job_status_done(self):
        """test primitive job's status"""
        bell, _, _ = self._cases[1]
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        bell = pm.run(bell)
        sampler = SamplerV2(**self._options)
        job = sampler.run([bell], shots=self._shots)
        _ = job.result()
        self.assertEqual(job.status(), JobStatus.DONE)

    def test_circuit_with_unitary(self):
        """Test for circuit with unitary gate."""
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())

        with self.subTest("identity"):
            gate = UnitaryGate(np.eye(2))

            circuit = QuantumCircuit(1)
            circuit.append(gate, [0])
            circuit.measure_all()
            circuit = pm.run(circuit)

            sampler = SamplerV2(**self._options)
            result = sampler.run([circuit], shots=self._shots).result()
            self.assertEqual(len(result), 1)
            self._assert_allclose(result[0].data.meas, np.array({0: self._shots}))

        with self.subTest("X"):
            gate = UnitaryGate([[0, 1], [1, 0]])

            circuit = QuantumCircuit(1)
            circuit.append(gate, [0])
            circuit.measure_all()
            circuit = pm.run(circuit)

            sampler = SamplerV2(**self._options)
            result = sampler.run([circuit], shots=self._shots).result()
            self.assertEqual(len(result), 1)
            self._assert_allclose(result[0].data.meas, np.array({1: self._shots}))

    def test_circuit_with_multiple_cregs(self):
        """Test for circuit with multiple classical registers."""
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        cases = []

        # case 1
        a = ClassicalRegister(1, "a")
        b = ClassicalRegister(2, "b")
        c = ClassicalRegister(3, "c")

        qc = QuantumCircuit(QuantumRegister(3), a, b, c)
        qc.h(range(3))
        qc.measure([0, 1, 2, 2], [0, 2, 4, 5])
        qc = pm.run(qc)
        target = {"a": {0: 5000, 1: 5000}, "b": {0: 5000, 2: 5000}, "c": {0: 5000, 6: 5000}}
        cases.append(("use all cregs", qc, target))

        # case 2
        a = ClassicalRegister(1, "a")
        b = ClassicalRegister(5, "b")
        c = ClassicalRegister(3, "c")

        qc = QuantumCircuit(QuantumRegister(3), a, b, c)
        qc.h(range(3))
        qc.measure([0, 1, 2, 2], [0, 2, 4, 5])
        qc = pm.run(qc)
        target = {
            "a": {0: 5000, 1: 5000},
            "b": {0: 2500, 2: 2500, 24: 2500, 26: 2500},
            "c": {0: 10000},
        }
        cases.append(("use only a and b", qc, target))

        # case 3
        a = ClassicalRegister(1, "a")
        b = ClassicalRegister(2, "b")
        c = ClassicalRegister(3, "c")

        qc = QuantumCircuit(QuantumRegister(3), a, b, c)
        qc.h(range(3))
        qc.measure(1, 5)
        qc = pm.run(qc)
        target = {"a": {0: 10000}, "b": {0: 10000}, "c": {0: 5000, 4: 5000}}
        cases.append(("use only c", qc, target))

        # case 4
        a = ClassicalRegister(1, "a")
        b = ClassicalRegister(2, "b")
        c = ClassicalRegister(3, "c")

        qc = QuantumCircuit(QuantumRegister(3), a, b, c)
        qc.h(range(3))
        qc.measure([0, 1, 2], [5, 5, 5])
        qc = pm.run(qc)
        target = {"a": {0: 10000}, "b": {0: 10000}, "c": {0: 5000, 4: 5000}}
        cases.append(("use only c multiple qubits", qc, target))

        # case 5
        a = ClassicalRegister(1, "a")
        b = ClassicalRegister(2, "b")
        c = ClassicalRegister(3, "c")

        qc = QuantumCircuit(QuantumRegister(3), a, b, c)
        qc.h(range(3))
        qc = pm.run(qc)
        target = {"a": {0: 10000}, "b": {0: 10000}, "c": {0: 10000}}
        cases.append(("no measure", qc, target))

        for title, qc, target in cases:
            with self.subTest(title):
                sampler = SamplerV2(**self._options)
                result = sampler.run([qc], shots=self._shots).result()
                self.assertEqual(len(result), 1)
                data = result[0].data
                self.assertEqual(len(data), 3)
                for creg in qc.cregs:
                    self.assertTrue(hasattr(data, creg.name))
                    self._assert_allclose(getattr(data, creg.name), np.array(target[creg.name]))

    def test_circuit_with_aliased_cregs(self):
        """Test for circuit with aliased classical registers."""
        q = QuantumRegister(3, "q")
        c1 = ClassicalRegister(1, "c1")
        c2 = ClassicalRegister(1, "c2")

        qc = QuantumCircuit(q, c1, c2)
        with qc.if_test((c1, 1)):
            qc.z(2)
        with qc.if_test((c2, 1)):
            qc.x(2)
        qc2 = QuantumCircuit(5, 5)
        qc2.compose(qc, [0, 2, 3], [2, 4], inplace=True)
        # Note: qc2 has aliased cregs, c0 -> c[2] and c1 -> c[4].
        # copy_empty_like copies the aliased cregs of qc2 to qc3.
        qc3 = QuantumCircuit.copy_empty_like(qc2)
        qc3.ry(np.pi / 4, 2)
        qc3.cx(2, 1)
        qc3.cx(0, 1)
        qc3.h(0)
        qc3.measure(0, 2)
        qc3.measure(1, 4)
        self.assertEqual(len(qc3.cregs), 3)
        cregs = [creg.name for creg in qc3.cregs]
        target = {
            cregs[0]: {0: 4255, 4: 4297, 16: 720, 20: 726},
            cregs[1]: {0: 5000, 1: 5000},
            cregs[2]: {0: 8500, 1: 1500},
        }

        sampler = SamplerV2(**self._options)
        result = sampler.run([qc3], shots=self._shots).result()
        self.assertEqual(len(result), 1)
        data = result[0].data
        self.assertEqual(len(data), 3)
        for creg_name, creg in target.items():
            self.assertTrue(hasattr(data, creg_name))
            self._assert_allclose(getattr(data, creg_name), np.array(creg))

    def test_no_cregs(self):
        """Test that the sampler works when there are no classical register in the circuit."""
        qc = QuantumCircuit(2)
        sampler = SamplerV2(**self._options)
        with self.assertWarns(UserWarning):
            result = sampler.run([qc]).result()

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].data), 0)

    def test_empty_creg(self):
        """Test that the sampler works if provided a classical register with no bits."""
        # Test case for issue #12043
        q = QuantumRegister(1, "q")
        c1 = ClassicalRegister(0, "c1")
        c2 = ClassicalRegister(1, "c2")
        qc = QuantumCircuit(q, c1, c2)
        qc.h(0)
        qc.measure(0, 0)

        sampler = SamplerV2(**self._options)
        result = sampler.run([qc], shots=self._shots).result()
        self.assertEqual(result[0].data.c1.array.shape, (self._shots, 0))

    def test_diff_shots(self):
        """Test of pubs with different shots"""
        bell, _, target = self._cases[1]
        pm = generate_preset_pass_manager(optimization_level=0, backend=AerSimulator())
        bell = pm.run(bell)
        sampler = SamplerV2(**self._options)
        shots2 = self._shots + 2
        target2 = {k: v + 1 for k, v in target.items()}
        job = sampler.run([(bell, None, self._shots), (bell, None, shots2)])
        result = job.result()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].data.meas.num_shots, self._shots)
        self._assert_allclose(result[0].data.meas, np.array(target))
        self.assertEqual(result[1].data.meas.num_shots, shots2)
        self._assert_allclose(result[1].data.meas, np.array(target2))

    def test_iter_pub(self):
        """Test of an iterable of pubs"""
        qc = QuantumCircuit(1)
        qc.measure_all()
        qc2 = QuantumCircuit(1)
        qc2.x(0)
        qc2.measure_all()
        sampler = SamplerV2(**self._options)
        result = sampler.run(iter([qc, qc2]), shots=self._shots).result()
        self.assertIsInstance(result, PrimitiveResult)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], SamplerPubResult)
        self.assertIsInstance(result[1], SamplerPubResult)
        self._assert_allclose(result[0].data.meas, np.array({0: self._shots}))
        self._assert_allclose(result[1].data.meas, np.array({1: self._shots}))

    def test_metadata(self):
        """Test for metadata"""
        qc = QuantumCircuit(2)
        qc.measure_all()
        qc2 = qc.copy()
        qc2.metadata = {"a": 1}
        sampler = SamplerV2(**self._options)
        result = sampler.run([(qc, None, 10), (qc2, None, 20)]).result()

        self.assertEqual(len(result), 2)
        self.assertEqual(result.metadata, {"version": 2})
        metadata = result[0].metadata
        self.assertIsInstance(metadata["simulator_metadata"], dict)
        del metadata["simulator_metadata"]
        self.assertEqual(metadata, {"shots": 10, "circuit_metadata": qc.metadata})

        metadata = result[1].metadata
        self.assertIsInstance(metadata["simulator_metadata"], dict)
        del metadata["simulator_metadata"]
        self.assertEqual(metadata, {"shots": 20, "circuit_metadata": qc2.metadata})

    def test_seed(self):
        """Test for seed options"""
        with self.subTest("empty"):
            sampler = SamplerV2()
            self.assertIsNone(sampler.seed)
        with self.subTest("set int"):
            sampler = SamplerV2(seed=self._seed)
            self.assertEqual(sampler.seed, self._seed)

    def test_default_shots(self):
        """Test for default_shots options"""
        with self.subTest("empty"):
            sampler = SamplerV2()
            self.assertEqual(sampler.default_shots, 1024)
        with self.subTest("set int"):
            sampler = SamplerV2(seed=self._seed)
            self.assertEqual(sampler.seed, self._seed)


if __name__ == "__main__":
    unittest.main()
