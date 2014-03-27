"""
FrequencyMemo
"""

from collections import defaultdict

import gelconfig
from frequency.frequencyiterator import FrequencyIterator

PERIODS = [p[0] for p in gelconfig.FREQUENCY_PERIODS]


class FrequencyMemo(object):

    """
    Store all the compiled frequency tables in memory, indexed by type ID
    """

    data = None

    def __init__(self, directory):
        self.in_dir = directory

    def find_frequencies(self, id):
        if not FrequencyMemo.data:
            _load_tables(self.in_dir)
        if id in FrequencyMemo.data:
            return {period: {'fpm': value} for period, value in
                    zip(PERIODS, FrequencyMemo.data[id])}
        else:
            return None


def _load_tables(in_dir):
    FrequencyMemo.data = defaultdict(dict)
    frequency_iterator = FrequencyIterator(inDir=in_dir,
                                           outDir=None,
                                           message='Loading frequency tables')
    for entry in frequency_iterator.iterate():
        for item in entry.lex_items:
            series = [item.frequency(period=period) for period in PERIODS]
            FrequencyMemo.data[item.type_id] = series
