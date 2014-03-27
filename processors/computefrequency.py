"""
computefrequency
"""

import os

import gelconfig

DIRECTORY1 = os.path.join(gelconfig.FREQUENCY_BUILD_DIR, 'types')
DIRECTORY2 = os.path.join(gelconfig.FREQUENCY_BUILD_DIR, 'types_plus_ngrams')
DIRECTORY3 = os.path.join(gelconfig.FREQUENCY_BUILD_DIR, 'types_with_frequency')
#avg_file = config.get('paths', 'frequency_averages')
RESOURCES_DIR = gelconfig.RESOURCES_DIR
oec_lempos_prob_file = os.path.join(RESOURCES_DIR, 'corpus', 'oec_lempos_probabilities.txt')
oec_pos_prob_file = os.path.join(RESOURCES_DIR, 'corpus', 'oec_pos_probabilities.txt')
bnc_prob_file = os.path.join(RESOURCES_DIR, 'corpus', 'bnc_probabilities.txt')


def list_lemmas(src_dir):
    from frequency.lemmalister import LemmaLister
    lister = LemmaLister(src_dir, DIRECTORY1)
    lister.process()


def compile_ngrams():
    from frequency.ngramvaluesinserter import insert_ngram_values
    insert_ngram_values(DIRECTORY1, DIRECTORY2)


def check_for_missing_ngrams():
    from frequency.gapfiller import find_gaps, fill_gaps
    find_gaps(DIRECTORY2)
    fill_gaps()


def compile_regression_data():
    from frequency.regressioncompiler import RegressionCompiler
    j = RegressionCompiler(DIRECTORY3)
    j.compile_data_points(letters='abcdefghijklmnopqrstuvwxyz')
    j.compile_lowess()
    #from frequency.frequencypredictor import FrequencyPredictor
    #p = FrequencyPredictor()
    #p.chart(outFile='lowess_complete.png', xmax=250, ymax=100)
    #p.chart(outFile='lowess_detail.png', xmax=20, ymax=3)
    #p.chart(outFile='lowess_verbs.png', xmax=250, ymax=100,
    #        wordclasses=('VB', 'VBZ', 'VBG', 'VBD', 'VBN'),)


def compute_frequencies():
    # We initialize the corpus probability managers here, to make sure
    #  they can find their data files
    from frequency.wordclass.corpusprobability import (OecLemposProbability,
                                                       BncPosProbability,
                                                       OecPosProbability,)
    OecLemposProbability(filepath=oec_lempos_prob_file)
    OecPosProbability(filepath=oec_pos_prob_file)
    BncPosProbability(filepath=bnc_prob_file)

    from frequency.calculate_frequency import calculate_frequency
    calculate_frequency(DIRECTORY2, DIRECTORY3)
