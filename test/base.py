# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""
Qiskit Experiments test case class
"""

import os
import json
import pickle
import unittest
import warnings
from typing import Any, Callable, Optional

import fixtures
import testtools
import uncertainties
from qiskit.utils.deprecation import deprecate_func
import qiskit_aer.backends.aerbackend
# The following imports are just for _patched_run_circuits
import qiskit.primitives.backend_sampler_v2
from qiskit.circuit import QuantumCircuit
from qiskit.providers import BackendV1, BackendV2
from qiskit.result import Result

from qiskit_experiments.framework import (
    ExperimentDecoder,
    ExperimentEncoder,
    ExperimentData,
)
from qiskit_experiments.framework.experiment_data import ExperimentStatus
from .extended_equality import is_equivalent


# Workaround until https://github.com/Qiskit/qiskit-aer/pull/2142 is released
try:
    del qiskit_aer.backends.aerbackend.AerBackend.get_translation_stage_plugin
except AttributeError:
    pass

# Fail tests that take longer than this
TEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT", 60))
# Use testtools by default as a (mostly) drop in replacement for
# unittest's TestCase. This will enable the fixtures used for capturing stdout
# stderr, and pylogging to attach the output to stestr's result stream.
USE_TESTTOOLS = os.environ.get("QE_USE_TESTTOOLS", "TRUE").lower() not in ("false", "0", "no")


def create_base_test_case(use_testtools: bool) -> unittest.TestCase:
    """Create the base test case class for package tests

    This function produces the base class for qiskit-experiments tests using
    either ``unittest.TestCase`` or ``testtools.TestCase`` for the base class.
    The creation of the class is done in this function rather than directly
    executed in the module so that, even when ``USE_TESTTOOLS`` is true, a
    ``unittest`` base class can be produced for ``test_base.py`` to check that
    no hard-dependence on ``testtools`` has been introduced.
    """
    if use_testtools:

        class BaseTestCase(testtools.TestCase):
            """Base test class."""

            # testtools maintains their own version of assert functions which mostly
            # behave as value adds to the std unittest assertion methods. However,
            # for assertEquals and assertRaises modern unittest has diverged from
            # the forks in testtools and offer more (or different) options that are
            # incompatible testtools versions. Just use the stdlib versions so that
            # our tests work as expected.
            assertRaises = unittest.TestCase.assertRaises
            assertEqual = unittest.TestCase.assertEqual

            def setUp(self):
                super().setUp()
                if os.environ.get("QISKIT_TEST_CAPTURE_STREAMS"):
                    stdout = self.useFixture(fixtures.StringStream("stdout")).stream
                    self.useFixture(fixtures.MonkeyPatch("sys.stdout", stdout))
                    stderr = self.useFixture(fixtures.StringStream("stderr")).stream
                    self.useFixture(fixtures.MonkeyPatch("sys.stderr", stderr))
                    self.useFixture(fixtures.LoggerFixture(nuke_handlers=False, level=None))

    else:

        class BaseTestCase(unittest.TestCase):
            """Base test class."""

            def useFixture(self, fixture):  # pylint: disable=invalid-name
                """Shim so that useFixture can be called in subclasses

                useFixture is a testtools.TestCase method. The actual fixture is
                not used when using unittest.
                """

    class QETestCase(BaseTestCase):
        """Qiskit Experiments specific extra functionality for test cases."""

        def setUp(self):
            super().setUp()
            self.useFixture(fixtures.Timeout(TEST_TIMEOUT, gentle=True))

        @classmethod
        def setUpClass(cls):
            """Set-up test class."""
            super().setUpClass()

            # Hack to pass metadata through to test backends
            qiskit.primitives.backend_sampler_v2._run_circuits = _patched_run_circuits

            warnings.filterwarnings("error", category=DeprecationWarning)
            # Tests should not generate any warnings unless testing those
            # warnings. In that case, the test should catch the warning
            # assertWarns or warnings.catch_warnings.
            warnings.filterwarnings("error", module="qiskit_experiments")
            # Ideally, changes introducing pending deprecations should include
            # alternative code paths and not need to generate warnings in the
            # tests but until this exception is necessary until the use of the
            # deprecated ScatterTable methods are removed.
            warnings.filterwarnings(
                "default",
                module="qiskit_experiments",
                message=".*Curve data uses dataframe representation.*",
                category=PendingDeprecationWarning,
            )
            warnings.filterwarnings(
                "default",
                module="qiskit_experiments",
                message=".*The curve data representation has been replaced by the `DataFrame` format.*",
                category=PendingDeprecationWarning,
            )
            warnings.filterwarnings(
                "default",
                module="qiskit_experiments",
                message=".*Could not determine job completion time.*",
                category=UserWarning,
            )


            # Some functionality may be deprecated in Qiskit Experiments. If
            # the deprecation warnings aren't filtered, the tests will fail as
            # ``QiskitTestCase`` sets all warnings to be treated as an error by
            # default.
            # pylint: disable=invalid-name
            allow_deprecationwarning_message = [
                ".*qiskit.providers.models.backendconfiguration.GateConfig.*",
                ".*qiskit.qobj.pulse_qobj.PulseLibraryItem.*",
                ".*qiskit.providers.models.backendconfiguration.UchannelLO.*",
                ".*qiskit.providers.models.backendconfiguration.PulseBackendConfiguration.*",
                ".*qiskit.qobj.pulse_qobj.PulseQobjInstruction.*",
                ".*qiskit.providers.models.backendconfiguration.QasmBackendConfiguration.*",
                ".*qiskit.qobj.common.QobjDictField.*",
                ".*qiskit.providers.models.backendproperties.BackendProperties.*",
                ".*qiskit.providers.fake_provider.fake_backend.FakeBackend.*",
                ".*qiskit.providers.backend.BackendV1.*",
            ]
            for msg in allow_deprecationwarning_message:
                warnings.filterwarnings("default", category=DeprecationWarning, message=msg)

        def assertExperimentDone(
            self,
            experiment_data: ExperimentData,
            timeout: Optional[float] = None,
        ):
            """Blocking execution of next line until all threads are completed then
            checks if status returns Done.

            Args:
                experiment_data: Experiment data to evaluate.
                timeout: The maximum time in seconds to wait for executor to
                    complete. Defaults to the value of ``TEST_TIMEOUT``.
            """
            if timeout is None and TEST_TIMEOUT != 0:
                timeout = TEST_TIMEOUT
            experiment_data.block_for_results(timeout=timeout)

            self.assertEqual(
                experiment_data.status(),
                ExperimentStatus.DONE,
                msg="All threads are executed but status is not DONE. " + experiment_data.errors(),
            )

        def assertEqualExtended(
            self,
            first: Any,
            second: Any,
            *,
            msg: Optional[str] = None,
            strict_type: bool = False,
        ):
            """Extended equality assertion which covers Qiskit Experiments classes.

            .. note::
                Some Qiskit Experiments class may intentionally avoid implementing
                the equality dunder method, or may be used in some unusual situations.
                These are mainly caused by to JSON round trip situation, and some custom classes
                doesn't guarantee object equality after round trip.
                This assertion function forcibly compares input two objects with
                the custom equality checker, which is implemented for unittest purpose.

            Args:
                first: First object to compare.
                second: Second object to compare.
                msg: Optional. Custom error message issued when first and second object are not equal.
                strict_type: Set True to enforce type check before comparison.
            """
            default_msg = f"{first} != {second}"

            self.assertTrue(
                is_equivalent(first, second, strict_type=strict_type),
                msg=msg or default_msg,
            )

        def assertRoundTripSerializable(
            self,
            obj: Any,
            *,
            check_func: Optional[Callable] = None,
            strict_type: bool = False,
        ):
            """Assert that an object is round trip serializable.

            Args:
                obj: the object to be serialized.
                check_func: Optional, a custom function ``check_func(a, b) -> bool``
                    to check equality of the original object with the decoded
                    object. If None :meth:`.assertEqualExtended` is called.
                strict_type: Set True to enforce type check before comparison.
            """
            try:
                encoded = json.dumps(obj, cls=ExperimentEncoder)
            except TypeError:
                self.fail("JSON serialization raised unexpectedly.")
            try:
                decoded = json.loads(encoded, cls=ExperimentDecoder)
            except TypeError:
                self.fail("JSON deserialization raised unexpectedly.")

            if check_func is not None:
                self.assertTrue(check_func(obj, decoded), msg=f"{obj} != {decoded}")
            else:
                self.assertEqualExtended(obj, decoded, strict_type=strict_type)

        def assertRoundTripPickle(
            self,
            obj: Any,
            *,
            check_func: Optional[Callable] = None,
            strict_type: bool = False,
        ):
            """Assert that an object is round trip serializable using pickle module.

            Args:
                obj: the object to be serialized.
                check_func: Optional, a custom function ``check_func(a, b) -> bool``
                    to check equality of the original object with the decoded
                    object. If None :meth:`.assertEqualExtended` is called.
                strict_type: Set True to enforce type check before comparison.
            """
            try:
                encoded = pickle.dumps(obj)
            except TypeError:
                self.fail("pickle raised unexpectedly.")
            try:
                decoded = pickle.loads(encoded)
            except TypeError:
                self.fail("pickle deserialization raised unexpectedly.")

            if check_func is not None:
                self.assertTrue(check_func(obj, decoded), msg=f"{obj} != {decoded}")
            else:
                self.assertEqualExtended(obj, decoded, strict_type=strict_type)

        @classmethod
        @deprecate_func(
            since="0.6",
            additional_msg="Use test.extended_equality.is_equivalent instead.",
            pending=True,
            package_name="qiskit-experiments",
        )
        def json_equiv(cls, data1, data2) -> bool:
            """Check if two experiments are equivalent by comparing their configs"""
            return is_equivalent(data1, data2)

        @staticmethod
        @deprecate_func(
            since="0.6",
            additional_msg="Use test.extended_equality.is_equivalent instead.",
            pending=True,
            package_name="qiskit-experiments",
        )
        def ufloat_equiv(data1: uncertainties.UFloat, data2: uncertainties.UFloat) -> bool:
            """Check if two values with uncertainties are equal. No correlation is considered."""
            return is_equivalent(data1, data2)

        @classmethod
        @deprecate_func(
            since="0.6",
            additional_msg="Use test.extended_equality.is_equivalent instead.",
            pending=True,
            package_name="qiskit-experiments",
        )
        def analysis_result_equiv(cls, result1, result2):
            """Test two analysis results are equivalent"""
            return is_equivalent(result1, result2)

        @classmethod
        @deprecate_func(
            since="0.6",
            additional_msg="Use test.extended_equality.is_equivalent instead.",
            pending=True,
            package_name="qiskit-experiments",
        )
        def curve_fit_data_equiv(cls, data1, data2):
            """Test two curve fit result are equivalent."""
            return is_equivalent(data1, data2)

        @classmethod
        @deprecate_func(
            since="0.6",
            additional_msg="Use test.extended_equality.is_equivalent instead.",
            pending=True,
            package_name="qiskit-experiments",
        )
        def experiment_data_equiv(cls, data1, data2):
            """Check two experiment data containers are equivalent"""
            return is_equivalent(data1, data2)

    return QETestCase


QiskitExperimentsTestCase = create_base_test_case(USE_TESTTOOLS)


def _patched_run_circuits(
    circuits: QuantumCircuit | list[QuantumCircuit],
    backend: BackendV1 | BackendV2,
    **run_options,
) -> tuple[list[Result], list[dict]]:
    """Remove metadata of circuits and run the circuits on a backend.
    Args:
        circuits: The circuits
        backend: The backend
        monitor: Enable job minotor if True
        **run_options: run_options
    Returns:
        The result and the metadata of the circuits
    """
    if isinstance(circuits, QuantumCircuit):
        circuits = [circuits]
    metadata = []
    for circ in circuits:
        metadata.append(circ.metadata)
        # Commenting out this line is only change from qiskit.primitives.backend_estimator._run_circuits
        # circ.metadata = {}
    if isinstance(backend, BackendV1):
        max_circuits = getattr(backend.configuration(), "max_experiments", None)
    elif isinstance(backend, BackendV2):
        max_circuits = backend.max_circuits
    else:
        raise RuntimeError("Backend version not supported")
    if max_circuits:
        jobs = [
            backend.run(circuits[pos : pos + max_circuits], **run_options)
            for pos in range(0, len(circuits), max_circuits)
        ]
        result = [x.result() for x in jobs]
    else:
        result = [backend.run(circuits, **run_options).result()]
    return result, metadata
