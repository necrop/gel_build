"""
WordclassRatios
"""

from frequency.frequencypredictor import FrequencyPredictor
from frequency.wordclass.corpusprobability import (OecLemposProbability,
                                                   BncPosProbability,
                                                   OecPosProbability)
from frequency.wordclass.wordclassmodel import HierarchicalModel, FlatModel
from frequency.wordclass.ngramsetmanager import NgramSetManager
from frequency.wordclass.utilities import adjust_to_unity

CORPUS_MANAGERS = {
    'bnc': BncPosProbability(),
    'oecpos': OecPosProbability(),
    'oeclempos': OecLemposProbability(),
}
FREQUENCY_PREDICTOR = FrequencyPredictor()
AWKWARD_CLASSES = {'VBZ', 'VBD', 'VBN', 'VBG', 'NNS', 'JJR', 'JJS',
                   'RBR', 'RBS'}


class WordclassRatios(object):

    """
    Manage the way that an overall ngram score (for the main untagged
    ngram) is subdivided between different parts of speech, e.g. between
    impact n. and impact v.

    There are four possible methods:
      1. base subdivision on ratios found in OEC pos tables
      2. base subdivision on ratios found in BNC pos tables
      3. base subdivision on ratios found in OEC lempos tables
      4. base subdivision on predicted frequency

    (1/2) is used if the OEC/BNC tables cover all the right
    parts of speech; failing that, (3) is used if the OEC lempos
    tables cover all the right parts of speech; failing that,
    (4) is used.

    Special handling ('verblike') for cases where there's a VBG or VBN
    and JJ or NN: these can be handled by the BNC method, but can't be
    usefully handled by any of the other methods.
    """

    def __init__(self, **kwargs):
        self.wordform = kwargs.get('form', None)
        self.lex_items = kwargs.get('lex_items', [])
        self.ngram = kwargs.get('ngram', None)
        self.ngram_manager = NgramSetManager(self.ngram,
                                             kwargs.get('tagged_ngrams', []))
        self.wordclass_model = HierarchicalModel(self.lex_items,
                                                 self.wordform)
        self.corpus_probability_sets = {
            'bnc': CORPUS_MANAGERS['bnc'].find(self.wordform),
            'oec': CORPUS_MANAGERS['oecpos'].find(self.wordform),
            'oec_lempos': _find_oec(self.lex_items),
        }
        self.calibrator = None
        self._set_ratios()

    def find_ratios(self, wordclasses, year):
        """
        Derive the appropriate set of ratios for each decade.
        """
        ratios = {}
        # Shortcut in case of just a single wordclass
        if len(self.wordclass_model.full_set_of_wordclasses()) <= 1:
            for w in wordclasses:
                ratios[w] = 1.0 / len(wordclasses)
            for lex_item in self.lex_items:
                lex_item.wordclass_method = 'singleton'
            return ratios
        else:
            if self.calibrator:
                calibrated_value = self.calibrator.calibrate(year)
                self.wordclass_model.inject_calibration(calibrated_value)
            for w in wordclasses:
                ratios[w] = self.wordclass_model.pos_ratio(w)
            if not 'NP' in ratios and self.wordclass_model.pos_ratio('NP') > 0:
                ratios['NP'] = self.wordclass_model.pos_ratio('NP')
            return adjust_to_unity(ratios)

    def _set_ratios(self):
        self._set_partofspeech_ratios()
        self._set_base_ratios()
        self._set_group_ratios()
        self.wordclass_model.log_methods()
        self.wordclass_model = FlatModel(self.wordclass_model)

        calibrator = Calibrator(self.wordclass_model, self.ngram_manager)
        if calibrator.is_viable():
            self.calibrator = calibrator

    def _set_partofspeech_ratios(self):
        """
        Establish ratios for specific parts of speech (lowest
        level of the wordclass model, below base wordclasses)

        Note that OEC lempos probabilities can't be used here, since
        the OEC lempos tables are not granular enough (they only give
        probabilities for base wordclasses, not for specific parts
        of speech)
        """
        for group in self.wordclass_model.model().values():
            for base in group.model().values():
                method_type = None
                ratio_set = dict()
                if len(base.model()) == 1:
                    for pos in base.model().keys():
                        ratio_set[pos] = 1.0
                    method_type = 'singleton'

                if not method_type:
                    for corpus in ('oec', 'bnc'):
                        probability_set = self.corpus_probability_sets[corpus]
                        if (probability_set and
                                probability_set.covers(base.full_set_of_wordclasses())):
                            for pos in base.model().keys():
                                ratio_set[pos] = probability_set.ratio(pos)
                            method_type = corpus
                            break

                if not method_type:
                    for pos, item in base.model().items():
                        ratio_set[pos] = item.predicted_frequency()
                    method_type = 'predictions'
                    if ('NP' in base.model() and
                            'NN' in base.model() and
                            len(base.model().keys()) == 2):
                        ratio_set = self._np_adjuster(base.model(), ratio_set)

                ratio_set = adjust_to_unity(ratio_set)
                base.set_ratios(ratio_set, method_type)

    def _set_base_ratios(self):
        """
        Set ratios for base wordclasses within each group.
        Based on measured or predicted frequencies.
        """
        for group in self.wordclass_model.model().values():
            method_type = None
            ratio_set = {}

            # No need to bother when there is only one wordclass (singleton)
            if len(group.model()) == 1:
                for wc in group.model().keys():
                    ratio_set[wc] = 1.0
                method_type = 'singleton'

            if not method_type:
                # Take ratios from OEC/BNC pos, if it's available and covers
                #  the right set of wordclasses
                for corpus in ('bnc', 'oec'):
                    probability_set = self.corpus_probability_sets[corpus]
                    if (probability_set and
                            probability_set.covers(group.base_set_of_wordclasses(), base=True)):
                        for wc in group.model().keys():
                            ratio_set[wc] = probability_set.base_ratios()[wc]
                        method_type = corpus
                        break

            if not method_type:
                # Take ratios from OEC/BNC pos, if it's available and covers
                #  *nearly* the right set of wordclasses. If a minor wordclass
                #  is not covered, use an estimate for this.
                for corpus in ('bnc', 'oec'):
                    probability_set = self.corpus_probability_sets[corpus]
                    if (probability_set and
                            probability_set.almost_covers(group.base_set_of_wordclasses())):
                        missing = probability_set.almost_covers(group.base_set_of_wordclasses())
                        est = self._estimate_missing(missing=missing,
                                                     corpus=corpus,
                                                     model=group.model())
                        if est is not None:
                            # Set the ratios of the wordclasses that *are* covered
                            for wc in group.base_set_of_wordclasses():
                                if wc != missing:
                                    ratio_set[wc] = probability_set.base_ratios()[wc]
                            # Use estimate as the ratio of the missing wordclass
                            ratio_set[missing] = est
                            method_type = corpus
                            break

            if not method_type:
                # Take ratios from OEC lempos, if it's available and covers
                #  the right set of wordclasses
                probability_set = self.corpus_probability_sets['oec_lempos']
                if (probability_set and
                        probability_set.covers(group.base_set_of_wordclasses(), base=True) and
                        not group.is_verblike()):
                    for wc in group.model().values():
                        ratio_set[wc.wordclass] =\
                            probability_set.sum_subcategories(list(wc.model().keys()))
                    method_type = 'oeclempos'

            if not method_type:
                # Take ratios from OEC lempos, if it's available and covers
                #  *nearly* the right set of wordclasses. If a minor wordclass
                #  is not covered, use an estimate for this.
                probability_set = self.corpus_probability_sets['oec_lempos']
                if (probability_set and
                        probability_set.almost_covers(group.base_set_of_wordclasses()) and
                        not group.is_verblike()):

                    missing = probability_set.almost_covers(group.base_set_of_wordclasses())
                    est = self._estimate_missing(missing=missing,
                                                 trace=False,
                                                 corpus='oec',
                                                 model=group.model())
                    if est:
                        # Set the ratios of the wordclasses that *are* covered
                        for wc in group.base_set_of_wordclasses():
                            if wc != missing:
                                ratio_set[wc] = probability_set.base_ratios()[wc]
                        # Use estimate as the ratio of the missing wordclass
                        ratio_set[missing] = est
                        method_type = 'oeclempos'

            # Fall back on predictions
            if not method_type:
                for wc, item in group.model().items():
                    ratio_set[wc] = item.predicted_frequency()
                ratio_set = _crosscheck(ratio_set, group.model())
                method_type = 'predictions'

            ratio_set = adjust_to_unity(ratio_set)
            group.set_ratios(ratio_set, method_type)

    def _set_group_ratios(self):
        """
        Set ratios for main groups
        Based on measured or predicted frequencies.

        Groups are either 'core' (NN + VB + JJ) or 'other' (everything else)
        """
        method_type = None
        if len(self.wordclass_model.model()) == 1:
            ratio_set = {grp: 1.0 for grp in self.wordclass_model.model().keys()}
            method_type = 'singleton'

        if not method_type:
            probability_set = self.corpus_probability_sets['bnc']
            if (probability_set and
                    self.wordclass_model.groupset() == probability_set.groupset()):
                ratio_set = {grp: probability_set.group_ratios()[grp]
                             for grp in self.wordclass_model.groupset()}
                method_type = 'bnc'

        if not method_type:
            probability_set = self.corpus_probability_sets['oec_lempos']
            if (probability_set and
                    self.wordclass_model.groupset() == probability_set.groupset() and
                    probability_set.covers(self.wordclass_model.base_set_of_wordclasses(), base=True) and
                    probability_set.sum_ratios(self.wordclass_model.base_set_of_wordclasses()) > 0.9):
                ratio_set = {grp: probability_set.group_ratios()[grp]
                             for grp in self.wordclass_model.groupset()}
                method_type = 'oeclempos'

        if not method_type:
            ratio_set = {pos: item.predicted_frequency() for pos, item
                         in self.wordclass_model.model().items()}
            ratio_set = _crosscheck(ratio_set, self.wordclass_model.model())
            method_type = 'predictions'

        ratio_set = adjust_to_unity(ratio_set)
        self.wordclass_model.set_ratios(ratio_set, method_type)

    def method(self):
        return self.wordclass_model.method()

    def _estimate_missing(self, **kwargs):
        """
        If all but one of the wordclasses are accounted for by the
        corpus probability set, and the missing wordclass appears
        to be minor (based on predicted frequency), then we'll just
        estimate the missing wordclass.

        This is most likely to capture VBG+JJ+NN sets where either
        the JJ or NN is missing in BNC. May also capture
        some VBN+JJ+NN sets, where the NN is vanishingly rare.
        """
        missing = kwargs.get('missing')
        model = kwargs.get('model')
        corpus = kwargs.get('corpus', 'bnc').lower()
        trace = kwargs.get('trace', False)

        # The missing item has to have a predicted frequency ratio
        #  below this threshold
        if corpus == 'bnc':
            threshold = 0.2
        elif corpus == 'oec':
            threshold = 0.1

        # How significant is the missing wordclass, as a proportion of
        #  the total predicted frequencies? The ratio needs to be low, in
        #  order for it to be plausible that it's missing from the BNC data
        sum_predictions = sum([b.predicted_frequency()
                               for b in model.values()])
        if sum_predictions:
            predicted_ratio = model[missing].predicted_frequency()\
                              / sum_predictions
        else:
            predicted_ratio = 1

        if trace:
            print('-------------------------------------------------')
            print(self.wordform)
            print('\t%s:' % corpus.upper())
            probability_set = self.corpus_probability_sets[corpus]
            for wordclass, f in probability_set.base_ratios().items():
                print('\t\t%s\t%0.3g' % (wordclass, f))
            print('\tpredictions:')
            for b in model.values():
                print('\t\t%s\t%0.3g' % (b.wordclass, b.predicted_frequency()))
            if predicted_ratio < threshold:
                print('---> %s = %0.3g' % (missing, predicted_ratio))
            else:
                print('FAILED  (%s = %0.3g)' % (missing, predicted_ratio))
            print('-------------------------------------------------')

        if predicted_ratio < threshold:
            return predicted_ratio
        else:
            return None

    def _np_adjuster(self, model, ratio_set):
        """
        Where a set consists of NN and NP, make sure that the NN is
        not scoring artificially high.

        If the NN's calculated score (based on the ratio already derived)
        is higher than its predicted frequency (based on size), then the
        ratio is recalculated from the NN's predicted frequency.
        """
        ratio_set = adjust_to_unity(ratio_set)
        ngram_total = self.ngram.frequency('1970-2000')
        nn_freq_calculated = ngram_total * ratio_set['NN']
        nn_freq_predicted = model['NN'].predicted_frequency()

        if nn_freq_predicted < nn_freq_calculated:
            nn_revised_ratio = nn_freq_predicted / ngram_total
            ratio_set = {'NN': nn_revised_ratio, 'NP': 1 - nn_revised_ratio}
        return ratio_set


class Calibrator(object):

    """
    Handles recalibration of default ratios to mirror the changing ratios
    observed in the tagged ngrams.

    This assumes that the set of tagged ngrams corresponds reasonably well
    to the wordclasses in question - this is checked by the
    is_viable() method.
    """

    def __init__(self, wordclass_manager, ngram_manager):
        self.wordclass_model = wordclass_manager
        self.ngram_manager = ngram_manager

    def is_viable(self):
        if (len(self.wordclass_model.base_set_of_wordclasses()) > 1 and
                self.ngram_manager.covers(self.wordclass_model.base_set_of_wordclasses()) and
                self.ngram_manager.coverage(self.wordclass_model.base_set_of_wordclasses(), decade=2000) > 0.7 and
                not self.wordclass_model.is_verblike()):
            self.set_baseline()
            if self.reference_metaratio < 20:
                return True
            else:
                return False
        else:
            return False

    def set_baseline(self):
        """
        Establish reference values, which will be used in subsequent
        calibrations
        """
        # Set ngram ratios for the year corresponding to the corpus data
        if self.wordclass_model.method() == 'bnc':
            year = 1980
        else:
            year = 2000
        self.ngram_manager.set_ratios(year)

        # Only consider the ratio between the top two wordclasses
        wcm_ratios = self._list_wordclassmodel_ratios()
        self.wordclasses = (wcm_ratios[0][0], wcm_ratios[1][0])

        self.reference_metaratio = _metaratio([self.ngram_manager.find_ngram(wc).ratio
                                               for wc in self.wordclasses])
        self.baseline_metaratio = _metaratio([self.wordclass_model.base_ratio(wc)
                                              for wc in self.wordclasses])
        self.total = sum([self.wordclass_model.base_ratio(wc)
                          for wc in self.wordclasses])

    def calibrate(self, year, trace=False):
        # Reset ngram ratios for the year in question
        self.ngram_manager.set_ratios(year)
        this_year_metaratio = _metaratio([self.ngram_manager.find_ngram(wc).ratio
                                          for wc in self.wordclasses])

        divergence = this_year_metaratio / self.reference_metaratio
        recalibrated_metaratio = self.baseline_metaratio * divergence

        recalibrated_ratios = {
            self.wordclasses[0]: self.total - (1.0/(1+recalibrated_metaratio)),
            self.wordclasses[1]: 1.0/(1+recalibrated_metaratio),
        }
        if trace:
            self._trace(year, this_year_metaratio, recalibrated_ratios)
        return recalibrated_ratios

    def _list_ngram_ratios(self):
        ratios = list()
        for base in self.wordclass_model.base_set_of_wordclasses():
            ratios.append((base, self.ngram_manager.find_ngram(base).ratio))
        ratios.sort(key=lambda a: a[1], reverse=True)
        return ratios

    def _list_wordclassmodel_ratios(self):
        ratios = list()
        for base, r in self.wordclass_model.base_ratios().items():
            ratios.append((base, r))
        ratios.sort(key=lambda a: a[1], reverse=True)
        return ratios

    def _trace(self, year, this_year_metaratio, recalibrated_ratios):
        print('-----------------------------------')
        print(self.ngram_manager.form())
        print('%s\t%d' % (self.wordclass_model.method(), year))
        print(self.wordclasses)
        for pos, val in self.wordclass_model.base_ratios().items():
            print('\tbaseline: %s\t%0.3g' % (pos, val))
        print('ref: %0.3g   this-yr: %0.3g   baseline: %0.3g' % (
              self.reference_metaratio, this_year_metaratio,
              self.baseline_metaratio))
        for pos, r in recalibrated_ratios.items():
                print('\t%s\t%0.3g' % (pos, r))
        print('-----------------------------------')


def _find_oec(lex_items):
    """
    Find the appropriate OEC lempos probability set.

    Note that this will be the OEC probability set for the base *lemma*,
    not for the particular wordform.

    Hence we give up if the lex_items encompass more than one base lemma
    """
    lex_baseforms = list(set([l.base for l in lex_items]))
    if len(lex_baseforms) == 1:
        return CORPUS_MANAGERS['oeclempos'].find(lex_baseforms[0])
    else:
        return None


def _metaratio(ratio_tuple):
    """
    Return the ratio of a tuple of two ratios
    """
    ratio1, ratio2 = ratio_tuple
    if ratio1 < 0.0001:
        ratio1 = 0.0001
    if ratio2 < 0.0001:
        ratio2 = 0.0001
    return ratio1 / ratio2


def _crosscheck(ratios, model_dict):
    """
    Check that the predicted ratios are not completely out of line with
    the naive ratios we'd derive by looking at the weighted size of the
    blocks being compared.

    If they *are* out of line, we switch to a more naive approach, which
    just predicts frequency in proportion to weighted size.

    This is only done in cases where there's a significant difference
    in size, or where one of the sizes is very small (c.2 quotations);
    this is the area where the reliability of predicted frequency
    tends to break down.
    """
    trace = False

    # Bug out if there's only a single category
    if len(ratios) == 1:
        return ratios

    # Bug out if there are awkward wordclasses involved - since,
    # for example, we don't necessarily expect VBZ to be more frequent
    # than NNS just because it's in a larger entry.
    wordclasses = set()
    for group in model_dict.values():
        [wordclasses.add(wc) for wc in group.full_set_of_wordclasses()]
    if wordclasses.intersection(AWKWARD_CLASSES):
        return ratios

    ratios = adjust_to_unity(ratios)
    sizes = [(pos, item.summed_weighted_size())
             for pos, item in model_dict.items()]
    sizes.sort(key=lambda i: i[1], reverse=True)
    try:
        sizes_ratio = sizes[0][1] / sizes[1][1]
    except ZeroDivisionError:
        sizes_ratio = sizes[0][1] / 0.5
    largest = sizes[0][0]
    next_largest = sizes[1][0]

    # Bug out if the size ratio of largest to next largest is not big
    # enough to be indicative
    if sizes_ratio > 3:
        pass
    elif sizes[1][1] < 2 and sizes_ratio > 2:
        pass
    else:
        return ratios

    # Bug out if predicted ratios are already different enough
    if ratios[largest] / ratios[next_largest] > sizes_ratio:
        return ratios

    # Switch to naive ratios, based on weighted size rather than
    #  predicted frequency
    naive_ratios = {pos: item.summed_weighted_size() for pos, item
                    in model_dict.items()}
    naive_ratios = adjust_to_unity(naive_ratios)

    if trace:
        print('------------------------------------------------------')
        try:
            print(list(model_dict.values())[0].form())
        except IndexError:
            print('UNKNOWN')
        for group in model_dict.values():
            print(group.full_set_of_wordclasses())
        print('-------------------------------------------------------')
        print(sizes)
        print(ratios)
        print('---->')
        print(naive_ratios)

    ratios = naive_ratios
    return ratios