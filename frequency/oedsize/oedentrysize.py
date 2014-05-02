"""
SizeIndexer
"""

import os
from collections import defaultdict, namedtuple
import string
import pickle
from functools import lru_cache

import numpy

import gelconfig
from lex.entryiterator import EntryIterator


PICKLE_DIR = gelconfig.WEIGHTED_SIZE_DIR
DATES = (1600, 1630, 1670, 1700, 1730, 1770, 1800, 1830, 1870, 1900,
         1930, 1970, 2000, 2010)
WINDOW_SIZE = 10  # window size for moving average
EntryData = namedtuple('EntryData', ['entry_id', 'node_id', 'wordclass',
                                     'num_quotations', 'sizes', 'start',
                                     'is_revised', 'inherit'])


def build_weighted_size_index():
    for letter in string.ascii_uppercase:
        iterator = EntryIterator(dict_type='oed',
                                 file_filter='oed_%s.xml' % letter,
                                 verbosity='low',
                                 fix_ligatures=True)

        entries = []
        for entry in iterator.iterate():
            blocks = []
            for block in entry.s1blocks():
                if (block.primary_wordclass() and
                        block.primary_wordclass().penn):
                    wordclass = block.primary_wordclass().penn
                else:
                    wordclass = '?'
                if len(entry.s1blocks()) == 1:
                    # If there's only one <s1> block, it's effectively
                    #  equivalent to the parent entry. So we make a dummy
                    #  entry, and later let it inherit from the parent entry.
                    block_data = EntryData(int(entry.id),
                                           int(block.node_id()),
                                           wordclass,
                                           0,
                                           [],
                                           0,
                                           entry.is_revised,
                                           True,
                                           )
                else:
                    block_sizes = [(d, block.weighted_size(
                                   revised=entry.is_revised,
                                   disregard_obsolete=True,
                                   currentYear=d)) for d in DATES]
                    block_sizes = [(d, round(n, 2)) for d, n in block_sizes]
                    block_data = EntryData(int(entry.id),
                                           int(block.node_id()),
                                           wordclass,
                                           block.num_quotations(),
                                           block_sizes,
                                           block.date().start,
                                           entry.is_revised,
                                           False,
                                           )
                blocks.append(block_data)

            try:
                entry_wordclass = blocks[0].wordclass
            except IndexError:
                entry_wordclass = '?'
            sizes = [(d, entry.weighted_size(revised=entry.is_revised,
                     disregard_obsolete=True, currentYear=d)) for d in DATES]
            sizes = [(d, round(n, 2)) for d, n in sizes]
            num_quotations = entry.num_quotations(force_recount=True,
                                                  include_derivatives=False)
            entry_data = EntryData(int(entry.id),
                                   0,
                                   entry_wordclass,
                                   num_quotations,
                                   sizes,
                                   entry.date().start,
                                   entry.is_revised,
                                   False,
                                   )

            if len(blocks) > 1:
                # Adjust block sizes to fit the entry size. We only need
                #  bother if there's more than one block; if there's only
                #  one block, it'll be inheriting from the entry anyway.
                blocks = _adjust_block_sizes(blocks, entry_data)

            entries.append(entry_data)
            entries.extend(blocks)

        out_file = os.path.join(PICKLE_DIR, letter)
        with open(out_file, 'wb') as filehandle:
            for entry in entries:
                pickle.dump(entry, filehandle)


class WeightedSize(object):

    """
    Manages the lookup of weighted-size values for OED entries
    """

    index = defaultdict(lambda: defaultdict(dict))

    def __init__(self, **kwargs):
        self.moving_average = kwargs.get('averaged', True)

    def find_size(self, **kwargs):
        entry_id = int(kwargs.get('id', 0))
        node_id = int(kwargs.get('eid', 0))
        mode = kwargs.get('type', 'actual').lower()
        date = int(kwargs.get('date', 2000))

        if not WeightedSize.index:
            _load_index()
        if (not entry_id in WeightedSize.index or
                not node_id in WeightedSize.index[entry_id]):
            return None
        else:
            entry_data = WeightedSize.index[entry_id][node_id]
            if mode == 'actual':
                return entry_data.num_quotations
            elif mode == 'weighted' and not self.moving_average:
                return numpy.interp(date,
                                    [p[0] for p in entry_data.sizes],
                                    [p[1] for p in entry_data.sizes])
            elif mode == 'weighted':
                years, values = _moving_average(entry_id, node_id)
                return numpy.interp(date, years, values)


def _load_index():
    print('Caching OED entry-size data...')
    for letter in string.ascii_uppercase:
        datasets = []
        pickle_file = os.path.join(PICKLE_DIR, letter)
        with open(pickle_file, 'rb') as filehandle:
            while 1:
                try:
                    data = pickle.load(filehandle)
                except EOFError:
                    break
                else:
                    datasets.append(data)

        for data in datasets:
            if data.inherit:
                WeightedSize.index[data.entry_id][data.node_id] =\
                    WeightedSize.index[data.entry_id][0]
            else:
                WeightedSize.index[data.entry_id][data.node_id] = data
    print('\t...caching complete.')
    #for node_id, value in WeightedSize.index[91451].items():
    #    print(node_id)
    #    print(repr(value))


@lru_cache(128)
def _moving_average(entry_id, node_id):
    entry_data = WeightedSize.index[entry_id][node_id]

    # Create interpolated values for each decade
    years = [p[0] for p in entry_data.sizes]
    values = [p[1] for p in entry_data.sizes]
    interpolated_years = range(1600, 2020, 10)
    interpolated_values = [numpy.interp(yr, years, values)
                           for yr in interpolated_years]

    # Calculate moving average
    averaged_values = []
    span = WINDOW_SIZE // 2
    for i, v in enumerate(interpolated_values):
        first = i - span
        if first < 0:
            first = 0
        last = i + span
        if last > len(interpolated_values):
            last = len(interpolated_values)
        window = interpolated_values[first:last]
        averaged_values.append(numpy.mean(window))

    return interpolated_years, averaged_values


def _adjust_block_sizes(blocks, entry):
    if entry.num_quotations <= sum([b.num_quotations for b in blocks]) + 2:
        # Don't change anything if the block sizes add up (more or less)
        #  to the entry size.
        return blocks
    else:
        # Make adjustments if the entry size is more than the sum of the
        #  block sizes; this suggests that there's a compounds block
        #  or revision section, which should be credited to one of the
        #  blocks.
        wordclass_set = set([block.wordclass for block in blocks])

        # First we do this for the actual size (the .num_quotations attribute)
        block_sizes = [b.num_quotations for b in blocks]
        actual_adjusted = _assign_excess(entry.num_quotations,
                                         block_sizes,
                                         wordclass_set)

        # Then we we do it for each row in the weighted size list
        #  (the .sizes attribute)
        # Results go into buckets in the weighted_adjusted list - one
        #  bucket for each block. The buckets are homologous with the
        #  original .sizes list, so can then be used as a drop-in
        #  replacement.
        weighted_adjusted = [list() for _ in blocks]
        for i, year in enumerate(DATES):
            year_sizes = [block.sizes[i][1] for block in blocks]
            year_adjusted = _assign_excess(entry.sizes[i][1],
                                           year_sizes,
                                           wordclass_set)
            for value, bucket in zip(year_adjusted, weighted_adjusted):
                bucket.append((year, value))

        # Create a new version of each block, with the adjusted
        #  values dropped in.
        blocks_new = []
        for block, adjusted_size, weighted_size in zip(blocks,
                                                       actual_adjusted,
                                                       weighted_adjusted):
            blocks_new.append(block._replace(num_quotations=adjusted_size,
                                             sizes=weighted_size))
        return blocks_new


def _assign_excess(entry_size, block_sizes, wordclass_set):
    block_total = sum(block_sizes)
    difference = entry_size - block_total
    if not block_total or difference <= 0:
        return block_sizes

    # If the two blocks are a NN and JJ, we share out the difference
    #  in proportion to their original sizes...
    if wordclass_set == {'NN', 'JJ'}:
        new_sizes = [size + ((size / block_total) * difference)
                     for size in block_sizes]
    # ...Otherwise, we just assign the difference to the largest of
    #  the two blocks
    else:
        new_sizes = []
        for size in block_sizes:
            if size == max(block_sizes):
                new_sizes.append(size + difference)
            else:
                new_sizes.append(size)
    return [round(n, 2) for n in new_sizes]
