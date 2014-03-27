"""
FrequencyPredictor
"""

import os
import numpy
from collections import namedtuple

import gelconfig
from frequency.wordclass.utilities import wordclass_category

PREDICTIONS_DIR = gelconfig.FREQUENCY_PREDICTION_DIR
DataSeries = namedtuple('Series', ['size', 'frequency'])


class FrequencyPredictor(object):

    """
    Essentially, this just loads and queries the data built by the
    neighbouring RegressionCompiler module. But we keep them in separate
    modules to avoid circular imports
    """

    models = dict()

    def __init__(self):
        if not FrequencyPredictor.models:
            _load_models()

    def predict(self, **kwargs):
        wordclass = kwargs.get('wordclass', 'NN')
        size = kwargs.get('size', 1)
        category = wordclass_category(wordclass)
        if not category in FrequencyPredictor.models:
            category = 'NN'
        return numpy.interp(size,
                            FrequencyPredictor.models[category].size,
                            FrequencyPredictor.models[category].frequency)


def _load_models():
    filenames = [f for f in os.listdir(PREDICTIONS_DIR)
                 if f.endswith('_lowess.txt')]
    for filename in filenames:
        wordclass = filename.split('_')[0]
        with open(os.path.join(PREDICTIONS_DIR, filename)) as filehandle:
            data_points = [[max(float(c), 0) for c in l.strip().split('\t')]
                           for l in filehandle.readlines()]
        xp = [d[0] for d in data_points]
        yp = [d[1] for d in data_points]
        _extrapolate(xp, yp)
        FrequencyPredictor.models[wordclass] = DataSeries(xp, yp)


def _extrapolate(xp, yp):
    """
    Add a further extrapolated point, in case of having to
    resolve higher x values.

    The new x-value is three times the last x-value. The new y-value
    is extrapolated from the slope of the last few points. (Several slopes
    are extrapolated from points near the end, and y-values are calculated
    for each; the new y-value is calculated as the mean of these.)
    """
    new_x = xp[-1] * 3
    y1 = yp[-1] + (new_x-xp[-1]) * (yp[-1]-yp[-20]) / (xp[-1]-xp[-20])
    y2 = yp[-1] + (new_x-xp[-1]) * (yp[-11]-yp[-30]) / (xp[-11]-xp[-30])
    y3 = yp[-1] + (new_x-xp[-1]) * (yp[-21]-yp[-40]) / (xp[-21]-xp[-40])
    new_y = numpy.mean((y1, y2, y3))
    xp.append(new_x)
    yp.append(new_y)


def chart(**kwargs):
    """
    Plot a chart of LOWESS values for a given set of wordclasses

    Returns a matplotlib.pyplot instance

    Usage:
        chart = fp.chart(wordclasses=("NN", "JJ), xmax=20)
        chart.show()
    """
    from matplotlib import pyplot as plt
    from lex.wordclass.wordclass import Wordclass

    xmax = kwargs.get('xmax', 250)
    ymax = kwargs.get('ymax', 100)
    figsize = kwargs.get('figsize', (14, 10))
    wordclasses = kwargs.get('wordclasses', ('NN', 'JJ', 'VB', 'RB'))
    out_file = kwargs.get('outFile', None)

    labels = [Wordclass(w).equivalent('description', default=w)
              for w in wordclasses]

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=figsize,
                           facecolor='white')
    for wc, label in zip(wordclasses, labels):
        ax.plot(FrequencyPredictor.models[wc]['x'],
                FrequencyPredictor.models[wc]['y'],
                linewidth=4, label=label)
    ax.legend(loc='upper left', shadow=True)
    ax.set_xlim([0, xmax])
    ax.set_ylim([0, ymax])
    ax.set_xlabel('entry size (weighted)')
    ax.set_ylabel('average frequency')
    ax.set_title('OED entry size-to-frequency')
    ax.grid(False)

    if out_file is None:
        plt.show()
    else:
        fig.savefig(os.path.join(PREDICTIONS_DIR, out_file), dpi=80)
