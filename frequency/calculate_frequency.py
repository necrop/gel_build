"""
calculate_frequency
"""

from collections import defaultdict

import gelconfig
from frequency.frequencyiterator import FrequencyIterator
from frequency.wordclass.wordclassratios import WordclassRatios
from frequency.homographscorer import HomographScorer
from lex.frequencytable import FrequencyTable

PERIODS = {name: value for name, value in gelconfig.FREQUENCY_PERIODS}


def calculate_frequency(in_dir, out_dir):
    """
    Calculate the frequency to be assigned to each lemma/type.
    """
    # Iterate through each entry in the frequency build files
    freq_iterator = FrequencyIterator(inDir=in_dir,
                                      outDir=out_dir,
                                      message='Calculating frequencies')
    for entry in freq_iterator.iterate():
        _apportion_scores(entry)
        for item in entry.lex_items:
            _compute_average_frequencies(item)
            # Add the entry weighted size to each lex_item
            item.node.set('size', '%0.3g' % item.size())
            # Add a full frequency table to each lex_item in the entry
            data = {p: {'frequency': f, 'estimate': item.estimated[p]}
                    for p, f in item.average_frequency.items()}
            freq_node = FrequencyTable(data=data).to_xml(band=False, log=False)
            freq_node.set('wcMethod', item.wordclass_method)
            item.node.append(freq_node)


def _apportion_scores(entry):
    if entry.ngram is None:
        for lex_item in entry.lex_items:
            lex_item.wordclass_method = 'null'
    else:
        wordclass_ratios = WordclassRatios(
            form=entry.form,
            lex_items=entry.lex_items,
            ngram=entry.ngram,
            tagged_ngrams=entry.tagged_ngrams,
            )

        for decade in sorted(entry.ngram.decades):
            if decade < 1750:
                pass
            else:
                # Filter out any lex_items that weren't in existence
                #  at the time,so we don't need to worry about them
                concurrent = _filter_lex_items(entry.lex_items, decade)

                # Cluster into p.o.s.-sets (sets of homograph lex_items
                #   with the same wordclass)
                pos_sets = defaultdict(list)
                for lex_item in concurrent:
                    wordclass = lex_item.wordclass
                    if wordclass == 'MD':
                        wordclass = 'VB'
                    pos_sets[wordclass].append(lex_item)

                # Derive the ratios for each part of speech
                ratios = wordclass_ratios.find_ratios(pos_sets.keys(), decade)

                for pos, homographs in pos_sets.items():
                    # Frequency for this set =
                    #  total ngram frequency * ratio for this part-of-speech
                    total_frequency =\
                        entry.ngram.decade_frequency(decade) * ratios[pos]
                    # Split this resulting frequency between the homographs
                    #  in the set
                    homograph_scorer = HomographScorer(
                        homographs=homographs,
                        frequency=total_frequency,
                        year=decade,
                        )
                    homograph_scorer.estimate()


def _compute_average_frequencies(lex_item):
    """
    Turn year-by-year values into decade-by-decade values, by
    calculating the average frequency across each period specified
    in PERIODS - i.e. for each decade.
    """
    lex_item.average_frequency = dict()
    lex_item.estimated = dict()
    for period, year_range in sorted(PERIODS.items()):
        start, end = year_range
        # How many decades in the period? 1850-1900 and 1850-1899
        #   should both be counted as 5 decades
        num_decades = (((end-1)-start) // 10) + 1
        sum_scores = sum([lex_item.scores[d] for d in lex_item.scores
                          if d >= start and d < end])
        estimated = set([lex_item.est[d] for d in lex_item.est
                          if d >= start and d < end])
        lex_item.average_frequency[period] = sum_scores / num_decades
        if True in estimated:
            lex_item.estimated[period] = True
        else:
            lex_item.estimated[period] = False


def _filter_lex_items(lex_items, decade):
    # Select all the lexitems that were current during the
    # decade in question
    return [l for l in lex_items if (not l.start or
            (l.start < decade and l.end > decade + 9))]
