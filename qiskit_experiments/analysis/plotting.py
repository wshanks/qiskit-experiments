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
Plotting functions for experiment analysis
"""
from typing import Callable, Optional
import numpy as np

from qiskit_experiments.base_analysis import AnalysisResult
from qiskit_experiments.matplotlib import pyplot, requires_matplotlib

# pylint: disable = unused-import
from qiskit_experiments.matplotlib import HAS_MATPLOTLIB


@requires_matplotlib
def plot_curve_fit(
    func: Callable,
    result: AnalysisResult,
    confidence_interval: bool = True,
    ax: Optional["pyplot.AxesSubplot"] = None,
    num_fit_points: int = 100,
    labelsize: int = 14,
    grid: bool = True,
    **kwargs,
) -> "pyplot.AxesSubplot":
    """Generate plot of a curve fit analysis result.

    Wraps ``matplotlib.pyplot.plot``.

    Args:
        func: the fit funcion for curve_fit.
        result: an AnalysisResult from curve_fit.
        confidence_interval: if True plot the confidence interval from popt_err.
        ax: Optional, a matplotlib axes to add the plot to.
        num_fit_points: the number of points to plot for xrange.
        labelsize: label size for plot
        grid: Show grid on plot.
        **kwargs: Additional options for matplotlib.pyplot.plot

    Returns:
        AxesSubPlot: the matplotlib axes containing the plot.

    Raises:
        ImportError: if matplotlib is not installed.
    """
    if ax is None:
        figure = pyplot.figure()
        ax = figure.subplots()

    # Result data
    popt = result["popt"]
    popt_err = result["popt_err"]
    xmin, xmax = result["xrange"]

    # Default plot options
    plot_opts = kwargs.copy()
    if "color" not in plot_opts:
        plot_opts["color"] = "blue"
    if "linestyle" not in plot_opts:
        plot_opts["linestyle"] = "-"
    if "linewidth" not in plot_opts:
        plot_opts["linewidth"] = 2

    # Plot fit data
    xs = np.linspace(xmin, xmax, num_fit_points)
    ys_fit = func(xs, *popt)
    ax.plot(xs, ys_fit, **plot_opts)

    # Plot standard error interval
    if confidence_interval:
        ys_upper = func(xs, *(popt + popt_err))
        ys_lower = func(xs, *(popt - popt_err))
        ax.fill_between(xs, ys_lower, ys_upper, alpha=0.1, color=plot_opts["color"])

    # Formatting
    ax.tick_params(labelsize=labelsize)
    ax.grid(grid)
    return ax


@requires_matplotlib
def plot_scatter(
    xdata: np.ndarray,
    ydata: np.ndarray,
    ax: Optional["pyplot.AxesSubplot"] = None,
    labelsize: int = 14,
    grid: bool = True,
    **kwargs,
) -> "pyplot.AxesSubplot":
    """Generate a scatter plot of xy data.

    Wraps ``matplotlib.pyplot.scatter``.

    Args:
        xdata: xdata used for fitting
        ydata: ydata used for fitting
        ax: Optional, a matplotlib axes to add the plot to.
        labelsize: label size for plot
        grid: Show grid on plot.
        **kwargs: Additional options for matplotlib.pyplot.scatter

    Returns:
        AxesSubPlot: the matplotlib axes containing the plot.
    """
    if ax is None:
        figure = pyplot.figure()
        ax = figure.subplots()

    # Default plot options
    plot_opts = kwargs.copy()
    if "c" not in plot_opts:
        plot_opts["c"] = "grey"
    if "marker" not in plot_opts:
        plot_opts["marker"] = "x"

    # Plot data
    ax.scatter(xdata, ydata, **plot_opts)

    # Formatting
    ax.tick_params(labelsize=labelsize)
    ax.grid(grid)
    return ax


@requires_matplotlib
def plot_errorbar(
    xdata: np.ndarray,
    ydata: np.ndarray,
    sigma: Optional[np.ndarray] = None,
    ax: Optional["pyplot.AxesSubplot"] = None,
    labelsize: int = 14,
    grid: bool = True,
    **kwargs,
) -> "pyplot.AxesSubplot":
    """Generate an errorbar plot of xy data.

    Wraps ``matplotlib.pyplot.errorbar``

    Args:
        xdata: xdata used for fitting
        ydata: ydata used for fitting
        sigma: Optional, standard deviation of ydata
        ax: Optional, a matplotlib axes to add the plot to.
        labelsize: label size for plot
        grid: Show grid on plot.
        **kwargs: Additional options for matplotlib.pyplot.scatter

    Returns:
        AxesSubPlot: the matplotlib axes containing the plot.
    """
    if ax is None:
        figure = pyplot.figure()
        ax = figure.subplots()

    # Default plot options
    plot_opts = kwargs.copy()
    if "color" not in plot_opts:
        plot_opts["color"] = "red"
    if "marker" not in plot_opts:
        plot_opts["marker"] = "."
    if "markersize" not in plot_opts:
        plot_opts["markersize"] = 9
    if "linestyle" not in plot_opts:
        plot_opts["linestyle"] = "--"

    # Plot data
    ax.errorbar(xdata, ydata, yerr=sigma, **plot_opts)

    # Formatting
    ax.tick_params(labelsize=labelsize)
    ax.grid(grid)
    return ax