"""
NgramValuesInserter
"""

import string
import os

from lxml import etree

from lex.gbn.tableiterator import TableIterator
from frequency.frequencyiterator import FrequencyIterator

alphabet = string.ascii_lowercase


def insert_ngram_values(in_dir, out_dir):
    """
    Fetch ngrams from the Google Ngram repository, and insert them
    into the frequency build data
    """
    for letter in alphabet:
        # Load in the list of all forms from the lexicon
        forms = {}
        freq_iterator = FrequencyIterator(inDir=in_dir,
                                          outDir=None,
                                          message='Loading ngram data',
                                          letters=letter)
        for entry in freq_iterator.iterate():
            forms[entry.form] = list()

        # Hunt for these lemmas in the GBN data
        for gram_count in (1, 2, 3, 4):
            print('\tchecking %s/%d...' % (letter, gram_count))
            gbn_iterator = TableIterator(gramCount=gram_count,
                                         letter=letter,
                                         verbose=False)
            for ngram in gbn_iterator.iterate():
                if ngram.lemma in forms:
                    line = '%d\t%s' % (gram_count, ngram.line)
                    forms[ngram.lemma].append(line)

        # Add GBN stats to the list of forms
        freq_iterator = FrequencyIterator(inDir=in_dir,
                                          outDir=out_dir,
                                          letters=letter)
        for entry in freq_iterator.iterate():
            gbn_node = etree.SubElement(entry.node, 'gbn')
            for line in forms[entry.form]:
                parts = line.split('\t')
                gram_count = parts.pop(0)
                parts.pop(0)  # remove the sortcode
                parts.pop(0)  # remove the form
                ngram_node = etree.SubElement(gbn_node, 'ngram')
                ngram_node.set('n', gram_count)
                ngram_node.set('wordclass', parts.pop(0))
                if parts:
                    ngram_node.text = ' '.join(parts)
