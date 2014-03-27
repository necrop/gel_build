"""
RegressionCompiler
"""

from collections import defaultdict
import os
import random
from itertools import groupby

import numpy
from statsmodels.nonparametric.smoothers_lowess import lowess

import gelconfig
from frequency.frequencyiterator import FrequencyIterator
from frequency.wordclass.utilities import wordclass_category

PREDICTIONS_DIR = gelconfig.FREQUENCY_PREDICTION_DIR
PERIODS = {name: value for name, value in gelconfig.FREQUENCY_PERIODS}
SAMPLE_SIZE = 10000
LOWESS_ITERATIONS = 4  # number of iterations (to mitigate outliers)
LOWESS_FRACTION = 1./5  # fraction of data points evaluated at each point


class RegressionCompiler(object):

    """
    Compile the set of data points that will be used as training data
    to predict the frequency of unknown or unambiguous items.

    The set of data points is derived from unambigious items, and plots
    weighted size  against frequency, for each point in time.

    Data points are segmented by wordclass.
    """

    def __init__(self, in_dir):
        self.in_dir = in_dir

    def compile_data_points(self, **kwargs):
        letters = kwargs.get('letters', None)
        freq_iterator = FrequencyIterator(inDir=self.in_dir,
                                          outDir=None,
                                          letters=letters,
                                          message='Compiling data points')

        # Keys will be wordclass values (NN, NNS, etc.); values will
        # be a list of data points
        self.data_points = defaultdict(list)

        for entry in freq_iterator.iterate():
            if entry.gram_count() == 1:  # and len(entry.lex_items) == 1:
                lex_items = self.largest_in_each_wordclass(entry.lex_items)
                for item in lex_items:
                    for period in item.frequency_table().data:
                        start, end = PERIODS[period]
                        lifespan = start - item.start
                        if lifespan >= -20:
                            wc = wordclass_category(item.wordclass)
                            row = (
                                item.size(date=start),
                                int(lifespan),
                                start,
                                item.frequency_table().frequency(period=period)
                            )
                            self.data_points[wc].append(row)
                            self.data_points['ALL'].append(row)

        for wordclass in self.data_points:
            self.data_points[wordclass].sort(key=lambda p: p[0])
            filepath = os.path.join(PREDICTIONS_DIR, wordclass + '.txt')
            with (open(filepath, 'w')) as fh:
                for data_point in self.data_points[wordclass]:
                    fh.write('%0.3g\t%d\t%d\t%0.4g\n' % data_point)

    def largest_in_each_wordclass(self, lex_items):
        # In the case of multiple lex_items (i.e. homographs,
        #  just use the one with the highest-frequency. (The others
        #  are likely to be estimates, so are not reliable.)
        def keyfunc(lex_item):
            return wordclass_category(lex_item.wordclass)

        lex_items = [l for l in lex_items if
                     l.is_oed_entry() and
                     l.frequency_table() is not None and
                     l.frequency_table().wordclass_method() != 'predictions']
        lex_items = sorted(lex_items, key=keyfunc)

        largest = list()
        for k, g in groupby(lex_items, key=keyfunc):
            homographs = sorted(list(g), key=lambda a: a.frequency(),
                                reverse=True)
            largest.append(homographs[0])
        return largest

    def compile_lowess(self):
        filenames = [f for f in os.listdir(PREDICTIONS_DIR) if f.endswith('.txt')
                     and not 'lowess' in f]
        for f in filenames:
            wordclass = f.split('.')[0]
            fh = open(os.path.join(PREDICTIONS_DIR, f), 'r')
            data_points = [[float(c) for c in l.strip().split('\t')]
                           for l in fh.readlines()]
            fh.close()

            data_points = self.sample_data_points(
                [d for d in data_points if d[3] > 0])
            x = numpy.array([l[0] for l in data_points])
            y = numpy.array([l[3] for l in data_points])
            results = lowess(y,
                             x,
                             frac=LOWESS_FRACTION,
                             it=LOWESS_ITERATIONS)

            outfile = os.path.join(PREDICTIONS_DIR, '%s_lowess.txt' % wordclass)
            with open(outfile, 'w') as fh:
                seen = set()
                for r in results:
                    sig = '%0.3g\t%0.3g\n' % (r[0], r[1],)
                    if sig in seen:
                        pass
                    else:
                        fh.write(sig)
                        seen.add(sig)

    def sample_data_points(self, data_points):
        """
        Random sample to reduce number of data points to 10000

        The set of data points is split into the first 90% and the last 10%,
        and these are each sampled down to 10000 independently of each other.
        The effect is that the first 90% (where data density is much higher)
        is sampled much more ruthlessly than the last 10% (where data is
        much sparser).
        """
        # Separate off the last 50 data points; these won't be sampled at all
        s1 = data_points[:-50]
        s3 = data_points[-50:]
        # Split the remainder into two subsets s1 and s2, at the point where
        #  the size value reaches 10% of the maximum; because of the skew
        #  in distribution, s1 will contain many more data points than s2
        max_size = s1[-1][0]
        split_index = numpy.searchsorted([p[0] for p in s1], max_size*0.1)
        s2 = s1[split_index:]
        s1 = s1[:split_index]
        # Sample each subset down to 10,000 data points
        if len(s1) > SAMPLE_SIZE:
            s1 = random.sample(s1, SAMPLE_SIZE)
        if len(s2) > SAMPLE_SIZE:
            s2 = random.sample(s2, SAMPLE_SIZE)
        # Recombine, then sample down to 10,000 again
        data_points = s1 + s2
        if len(data_points) > SAMPLE_SIZE:
            data_points = random.sample(data_points, SAMPLE_SIZE)
        # Add back in the last 50 data points
        data_points.extend(s3)
        return data_points
