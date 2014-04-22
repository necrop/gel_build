"""
WordclassModel
"""

from collections import Counter

from lex.propernames.propernames import is_proper_name
from frequency.frequencypredictor import FrequencyPredictor
from frequency.wordclass.utilities import wordclass_base, wordclass_group

freqPredictor = FrequencyPredictor()

default_sizes = {
    'general': float(1),  # size assigned to unsized lemmas
    'np': float(30),  # size assigned to encyclopedic entries
}


class Model(object):

    """
    Base class for WordclassModel, Group, and Base
    """

    def model(self):
        return self._model

    def form(self):
        try:
            return self.lex_items()[0].form
        except IndexError:
            return '[UNKNOWN]'

    def full_set_of_wordclasses(self):
        fullset = set()
        for subcat in self.model().values():
            [fullset.add(wc) for wc in subcat.full_set_of_wordclasses()]
        return fullset

    def base_set_of_wordclasses(self):
        return set([wordclass_base(wc)
                    for wc in self.full_set_of_wordclasses()])

    def lex_items(self):
        """
        Return all the lex_items in child container.
        Recurses through the hierarchy of child containers.
        """
        items = []
        for subcat in self.model().values():
            items.extend(subcat.lex_items())
        return items

    def summed_weighted_size(self):
        return sum([l.size(mode='weighted') for l in self.lex_items()])

    def summed_actual_size(self):
        return sum([l.size(mode='actual') for l in self.lex_items()])

    def predicted_frequency(self):
        return sum([j.predicted_frequency()
                    for j in self.model().values()])

    def set_ratios(self, ratio_set, type):
        for wordclass, val in ratio_set.items():
            self.model()[wordclass].ratio = val
            self.model()[wordclass]._ratio_type = type
        self._ratio_type = type

    def ratio_type(self):
        try:
            return self._ratio_type
        except AttributeError:
            return 'not set'

    def is_verblike(self):
        if ({'VBG', 'JJ'}.issubset(self.full_set_of_wordclasses()) or
                {'VBG', 'NN'}.issubset(self.full_set_of_wordclasses()) or
                {'VBN', 'JJ'}.issubset(self.full_set_of_wordclasses())):
            return True
        else:
            return False


class HierarchicalModel(Model):

    """
    Top-level model (level 1)

    Model is a dict of Group() instances
    """

    def __init__(self, lex_items, wordform):
        self.wordform = wordform
        self.lex_items = lex_items
        self.np_added = False
        self.build_model()
        self.add_np()

    def build_model(self):
        self._model = dict()
        for l in self.lex_items:
            group_type = wordclass_group(l.wordclass)
            if not group_type in self._model:
                self._model[group_type] = Group(group_type)
            self._model[group_type].add(l)

    def add_np(self):
        """
        Check if a dummy "NP" wordclass needs to be added
        """
        if (not 'NP' in self.full_set_of_wordclasses() and
                self.wordform.lower() != self.wordform and
                is_proper_name(self.wordform)):
            group_type = wordclass_group('NP')
            base_class = wordclass_base('NP')
            if not group_type in self.model():
                self.model()[group_type] = Group('core')
            self.model()[group_type].add_null(base_class)
            self.model()[group_type].model()[base_class].add_null('NP')
            self.np_added = True

    def pos_ratios(self):
        ratios = dict()
        for g in self.model().values():
            for base in g.model().values():
                for pos in base.model().values():
                    r = pos.ratio * base.ratio * g.ratio
                    ratios[pos.wordclass] = r
        return ratios

    def pos_ratio(self, pos):
        try:
            return self.pos_ratios()[pos]
        except KeyError:
            return float(0)

    def groupset(self):
        return set(self.model().keys())

    def stringify(self):
        t = self.wordform + '\n'
        for g in self.model().values():
            t += '\t%s  pf=%0.3g  r=%0.3g  %s\n' % (g.type,
                                                    g.predicted_frequency(),
                                                    g.ratio,
                                                    g.ratio_type())
            for b in g.model().values():
                t += '\t\t%s  pf=%0.3g  r=%0.3g  %s\n' % (b.wordclass,
                                                          b.predicted_frequency(),
                                                          b.ratio,
                                                          b.ratio_type())
                for pos in b.model().values():
                    t += '\t\t\t%s  pf=%0.3g  r=%0.3g  %s\n' % (pos.wordclass,
                                                                pos.predicted_frequency(),
                                                                pos.ratio,
                                                                pos.ratio_type())
        t += '\t'.join(['%s=%0.3g' % (pos, r) for pos, r
                        in self.pos_ratios().items()]) + '\n'
        return t

    def log_methods(self):
        """
        Record the method used against each lex item (as the lex item's
        'wordclass_method' attribute).
        """
        for g in self.model().values():
            for b in g.model().values():
                for pos in b.model().values():
                    m = None
                    for t in ('predictions', 'oec', 'bnc'):
                        if b.ratio_type() == t or pos.ratio_type() == t:
                            m = t
                            break
                    if m is None:
                        m = pos.ratio_type()
                    for l in pos.lex_items():
                        l.wordclass_method = m


class FlatModel(Model):

    def __init__(self, hmodel):
        self.wordform = hmodel.wordform
        self.lex_items = hmodel.lex_items
        self.np_added = hmodel.np_added
        self.calibrations = None

        self._model = dict()
        for g in hmodel.model().values():
            for b in g.model().values():
                b.ratio = b.ratio * g.ratio
                self._model[b.wordclass] = b

    def pos_ratios(self):
        try:
            return self._pos_ratios
        except AttributeError:
            self.recalculate_pos_ratios()
            return self._pos_ratios

    def recalculate_pos_ratios(self):
        self._pos_ratios = dict()
        for base in self.model().values():
            for pos in base.model().values():
                if (self.calibrations is not None and
                    base.wordclass in self.calibrations):
                    r = pos.ratio * self.calibrations[base.wordclass]
                else:
                    r = pos.ratio * base.ratio
                self._pos_ratios[pos.wordclass] = r

    def pos_ratio(self, pos):
        try:
            return self.pos_ratios()[pos]
        except KeyError:
            return float(0)

    def base_ratios(self):
        ratios = dict()
        for base in self.model().values():
            ratios[base.wordclass] = base.ratio
        return ratios

    def base_ratio(self, wordclass):
        try:
            return self.model()[wordclass].ratio
        except KeyError:
            return float(0)

    def method(self):
        c = Counter([b.ratio_type() for b in self.model().values()])
        return c.most_common(1)[0][0]

    def inject_calibration(self, c):
        self.calibrations = c
        self.recalculate_pos_ratios()

    def stringify(self):
        t = self.wordform + '\n'
        for b in self.model().values():
            t += '\t\t%s  pf=%0.3g  r=%0.3g  %s\n' % (b.wordclass,
                                                      b.predicted_frequency(),
                                                      b.ratio,
                                                      b.ratio_type())
            for pos in b.model().values():
                t += '\t\t\t%s  pf=%0.3g  r=%0.3g  %s\n' % (pos.wordclass,
                                                            pos.predicted_frequency(),
                                                            pos.ratio,
                                                            pos.ratio_type())
        t += '\t'.join(['%s=%0.3g' % (pos, r) for pos, r
                        in self.pos_ratios().items()]) + '\n'
        return t


class Group(Model):

    """
    Group of wordclasses (level 2): either
     - "core" (NN, VB, and JJ)
     - "other" (everything else)

    Model is a dict of Base() instances
    """

    def __init__(self, type):
        self.type = type
        self._model = dict()
        self.ratio = 1.0  # default placeholder

    def add(self, lex_item):
        base = wordclass_base(lex_item.wordclass)
        if not base in self.model():
            self.model()[base] = Base(base)
        self.model()[base].add(lex_item)

    def add_null(self, wordclass):
        if not wordclass in self.model():
            self.model()[wordclass] = Base(wordclass)


class Base(Model):

    """
    Base wordclass, e.g. NN, VB, JJ (level 3)

    Model is a dict of PartOfSpeech() instances
    """

    def __init__(self, wordclass):
        self.wordclass = wordclass
        self._model = dict()
        self.ratio = 1.0  # default placeholder

    def add(self, lex_item):
        if not lex_item.wordclass in self.model():
            self.model()[lex_item.wordclass] = PartOfSpeech(lex_item.wordclass)
        self.model()[lex_item.wordclass].add(lex_item)

    def add_null(self, wordclass):
        if not wordclass in self.model():
            self.model()[wordclass] = PartOfSpeech(wordclass)


class PartOfSpeech(object):

    """
    Specific part of speech, e.g. NN, NNS, VB, VBZ, VBD, etc. (level 4)
    """

    def __init__(self, wordclass):
        self.wordclass = wordclass
        self.baseclass = wordclass_base(wordclass)
        self.items = list()
        self.ratio = 1.0  # default placeholder

    def add(self, lex_item):
        self.items.append(lex_item)

    def lex_items(self):
        return self.items

    def full_set_of_wordclasses(self):
        return {self.wordclass, }

    def base_set_of_wprdclasses(self):
        return {self.baseclass, }

    def predicted_frequency(self):
        try:
            return self._predicted_frequency
        except AttributeError:
            if self.wordclass == 'NP':
                self._predicted_frequency = freqPredictor.predict(
                    size=default_sizes['np'], wordclass='NP',)
            elif self.items:
                # Predicted frequency for the group is based on
                #  predicted frequency of the largest item in the group
                self._predicted_frequency = max(
                    [l.predicted_frequency(date=2000) for l in self.items])
            else:
                self._predicted_frequency = freqPredictor.predict(
                    size=default_sizes['general'], wordclass='NN',)
            return self._predicted_frequency

    def ratio_type(self):
        try:
            return self._ratio_type
        except AttributeError:
            return 'not set'

