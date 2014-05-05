"""
CorpusProbability
"""

from collections import defaultdict

from frequency.wordclass.utilities import (wordclass_base,
                                           wordclass_group,
                                           adjust_to_unity)


class BncPosProbability(object):

    """
    Maintains a table of p.o.s. probabilities for each wordform,
    based on BNC wordlist
    """

    words = dict()
    frequency_limit = 1.0

    def __init__(self, **kwargs):
        filepath = kwargs.get('filepath', None)
        supplement = kwargs.get('supplement', None)
        if filepath and not BncPosProbability.words:
            self._load_data(filepath, supplement)

    def find(self, query):
        try:
            return BncPosProbability.words[query]
        except KeyError:
            return None

    def _load_data(self, filepath, supplement):
        for in_file in (filepath, supplement):
            if not in_file:
                continue
            with open(in_file) as filehandle:
                for line in filehandle:
                    if '\t' in line:
                        probset = PosProbabilitySet(line)
                        if probset.fpm >= self.frequency_limit:
                            BncPosProbability.words[probset.word] = probset


class OecPosProbability(object):

    """
    Maintains a table of p.o.s. probabilities for each wordform,
    based on OEC wordlist
    """

    words = dict()
    frequency_limit = 0.1

    def __init__(self, filepath=None):
        if filepath and not OecPosProbability.words:
            self._load_data(filepath)

    def find(self, query):
        try:
            return OecPosProbability.words[query]
        except KeyError:
            return None

    def _load_data(self, filepath):
        with open(filepath) as filehandle:
            for line in filehandle:
                probset = PosProbabilitySet(line)
                if probset.fpm >= self.frequency_limit:
                    OecPosProbability.words[probset.word] = probset


class OecLemposProbability(object):

    """
    Maintains a table of wordclass probabilities for each lemma,
    based on OEC lempos frequencies.
    """

    lemmas = dict()

    def __init__(self, filepath=None):
        if filepath and not OecLemposProbability.lemmas:
            self._load_data(filepath)

    def find(self, query):
        try:
            return OecLemposProbability.lemmas[query]
        except KeyError:
            return None

    def _load_data(self, filepath):
        with open(filepath) as filehandle:
            for line in filehandle:
                probset = LemposProbabilitySet(line)
                OecLemposProbability.lemmas[probset.word] = probset


class GenericProbabilitySet(object):

    """
    Set of frequency probabilities for a given lemma
    """

    def list_parts(self):
        return ', '.join(['%s=%0.4g' % (pos, self.parts[pos])
                          for pos in sorted(self.parts.keys())])

    def ratio(self, pos):
        try:
            return self.parts[pos]
        except KeyError:
            return 0

    def ratios(self):
        return self.parts

    def frequency_per_million(self, pos):
        """
        Calculate the frequency per million of a given wordclass
        (or 0, if the wordclass is not in self.parts)
        """
        return self.fpm * self.ratio(pos)

    def sum_ratios(self, wordclasses):
        """
        For a given iterable of wordclasses, return the total
        ratio that they sum to.

        E.g. if self.parts = {'NN': .25, 'JJ': .50, 'VB': .25},
        then the argument ('NN', 'JJ') will return .75.
        """
        return sum([self.ratio(pos) for pos in wordclasses])

    def covers(self, wordclasses, base=False):
        """
        For a given iterable of wordclasses, return True if they're
        all covered in self.parts, False otherwise
        """
        if base == True and set(wordclasses).issubset(self.baseset()):
            return True
        elif base == False and set(wordclasses).issubset(self.wordclass_set()):
            return True
        else:
            return False

    def wordclass_set(self):
        return set(self.parts.keys())

    def base_ratios(self):
        try:
            return self._base_ratios
        except AttributeError:
            self._base_ratios = defaultdict(lambda: 0)
            for pos, value in self.ratios().items():
                wc = wordclass_base(pos)
                self._base_ratios[wc] += value
            return self._base_ratios

    def baseset(self):
        return set(self.base_ratios().keys())

    def is_core_only(self):
        residue = 0
        for pos, ratio in self.base_ratios().items():
            if pos not in ('NN', 'JJ', 'VB'):
                residue += ratio
        if residue < 0.05:
            return True
        else:
            return False

    def group_ratios(self):
        try:
            return self._group_ratios
        except AttributeError:
            self._group_ratios = defaultdict(lambda: 0)
            for pos, value in self.ratios().items():
                grp = wordclass_group(pos)
                self._group_ratios[grp] += value
            return self._group_ratios

    def groupset(self):
        return set(self.group_ratios().keys())


class PosProbabilitySet(GenericProbabilitySet):

    """
    Set of frequency probabilities for a given wordform in BNC/OEC
    """

    def __init__(self, line):
        columns = line.strip().split('\t')
        self.word = columns[0]
        self.fpm = float(columns[1])
        self.parts = defaultdict(lambda: 0)
        for p in columns[2:]:
            pos, percentage = p.split('=')
            self.parts[pos] += float(percentage)/100

        # Special handling of interjections -  we take the interjection out
        # of the equation, but keep separate note of the ratio given to the
        # interjection originally. This supports adjustments made for
        # interjections further down the line
        if 'UH' in self.parts:
            self.interjection_ratio = self.parts['UH']
            if self.interjection_ratio > 0.99:
                # Safeguard - make the ratio slightly less than 1, so that
                # there'll at least be *something* left for other
                # parts of speech
                self.interjection_ratio = 0.99
            del self.parts['UH']
            self.parts = adjust_to_unity(self.parts)
        else:
            self.interjection_ratio = 0

    def almost_covers(self, wordclasses):
        """
        For a given iterable of wordclasses, return the one that's
        missing from the BNC set (if exactly one missing); otherwise
        returns False
        """
        missing = []
        if ((len(self.baseset()) == 2 and len(wordclasses) == 3) or
            (len(self.baseset()) == 3 and len(wordclasses) == 4)):
            for wc in wordclasses:
                if not wc in self.baseset():
                    missing.append(wc)
        if len(missing) == 1:
            return missing[0]
        else:
            return False


class LemposProbabilitySet(GenericProbabilitySet):

    """
    Set of frequency probabilities for a given lemma in OEC
    """

    penn_map = {
        'n': 'NN',
        'v': 'VB',
        'j': 'JJ',
        'r': 'RB',
        'e': 'NP',
        'p': 'PP',
        'i': 'IN',
        'c': 'CC',
        'x': 'other',
    }
    pos_to_lemma_ratios = {
        # The following are based on measurement
        'NN': ('NN', 1.07,),
        'NNS': ('NN', 3.90,),
        'NP': ('NN', 1),
        'VB': ('VB', 3.33,),
        'VBG': ('VB', 5.91,),
        'VBD': ('VB', 5.2,),
        'VBN': ('VB', 3.2,),
        'VBZ': ('VB', 17.17,),
        'MD': ('VB', 1.0),
        # The following are guesses
        'JJR': ('JJ', 15),
        'JJS': ('JJ', 20),
        'RBR': ('RB', 15),
        'RBS': ('RB', 20)
    }

    def __init__(self, line):
        columns = line.strip().split('\t')
        self.word = columns[0]
        self.fpm = float(columns[1])
        self.parts = dict()
        for p in columns[2:]:
            pos, percentage = p.split('=')
            self.parts[self.penn_map[pos]] = float(percentage)/100

    def subcategory_ratio(self, pos):
        baseclass = wordclass_base(pos)
        base_ratio = self.ratio(baseclass)
        if pos in self.pos_to_lemma_ratios:
            return base_ratio / self.pos_to_lemma_ratios[pos][1]
        else:
            return base_ratio

    def sum_subcategories(self, parts):
        if parts:
            baseclass = wordclass_base(parts[0])
            base_ratio = self.ratio(baseclass)
            total = 0
            for pos in parts:
                if pos in self.pos_to_lemma_ratios:
                    total += base_ratio / self.pos_to_lemma_ratios[pos][1]
                else:
                    total += base_ratio
            return min((total, base_ratio))
        else:
            return 0

    def almost_covers(self, wordclasses):
        """
        For a given iterable of wordclasses, return the one that's
        missing from the OEC set (if exactly one missing); otherwise
        return False
        """
        missing = []
        if len(wordclasses) > 2:
            for wc in wordclasses:
                if not wc in self.baseset():
                    missing.append(wc)
        unaccounted = float(0)
        for wc, r in self.base_ratios().items():
            if not wc in wordclasses:
                unaccounted += r
        if len(missing) == 1 and unaccounted < 0.1:
            return missing[0]
        else:
            return False
