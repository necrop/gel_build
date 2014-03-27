"""
NgramSetManager
"""

from frequency.wordclass.utilities import wordclass_base


class NgramSetManager(object):

    def __init__(self, base_ngram, tagged_ngrams):
        self.basegram = base_ngram
        self.ngrams_list = tagged_ngrams

    def base_ngram(self):
        """
        Return the untagged ('ALL') ngram; or None if there are no ngrams.
        """
        return self.basegram

    def frequency(self, decade):
        if self.base_ngram() is not None:
            return self.base_ngram().frequency(decade)
        else:
            return 0

    def form(self):
        if self.base_ngram():
            return self.base_ngram().lemma
        else:
            return ''

    wordform = form

    def wordclass_set(self, mode='source'):
        """
        Return a set of parts of speech

        If mode='source', returns a set of native parts-of-speech
        ('NOUN', 'VERB', etc.) for each ngram (except the 'ALL' ngram).

        If mode='penn', returns a set of Penn parts-of-speech for each
        ngram (except the 'ALL' ngram).
        """
        if mode == 'source':
            return set([n.wordclass for n in self.ngrams_list if
                        n.wordclass != 'ALL'])
        elif mode == 'penn':
            return set([n.penn_wordclass() for n in self.ngrams_list if
                        n.wordclass != 'ALL' and
                        n.penn_wordclass()])

    def ngrams_by_penn(self):
        """
        Return ngrams arranged as values in a dict where the keys are
        Penn parts-of-speech.
        """
        return {n.penn_wordclass(): n for n in self.ngrams_list
                if n.wordclass != 'ALL' and n.penn_wordclass()}

    def find_ngram(self, wordclass):
        """
        Return the ngram corresponding to the wordclass specified;
        whether this is a Penn wordclass or a native wordclass
        ('NOUN', 'VERB', etc.).
        """
        if wordclass in self.ngrams_by_penn():
            return self.ngrams_by_penn()[wordclass]
        elif wordclass_base(wordclass) in self.ngrams_by_penn():
            return self.ngrams_by_penn()[wordclass_base(wordclass)]
        else:
            for ngram in self.ngrams_list:
                if ngram.wordclass == wordclass:
                    return ngram
        return None

    def set_ratios(self, decade):
        """
        Calculate the ratio of the total represented by each
        p.o.s.-tagged ngram (for a given decade).

        The value (between 0 and 1) is added to each ngram as the
        attribute 'ratio'.
        """
        if (self.base_ngram() is not None and
            self.base_ngram().decade_count(decade) > 0):
            total = self.base_ngram().decade_count(decade)
            for ngram in self.ngrams_list:
                ngram.ratio = (1 / total) * ngram.decade_count(decade)
        else:
            for ngram in self.ngrams_list:
                ngram.ratio = float(0)

    def covers(self, wordclass_set):
        """
        Check that each wordclass in the set is covered by the
        ngram set.

        Returns True or False.
        """
        for wordclass in wordclass_set:
            ngram = self.find_ngram(wordclass)
            if ngram is None:
                return False
        return True

    def coverage(self, wordclass_set, decade=2000):
        """
        For a given set of wordclasses, return the ratio of the
        ngram set that they account for.

        Returns float between 0 and 1.
        """
        self.set_ratios(decade)
        total = float(0)
        for wordclass in wordclass_set:
            ngram = self.find_ngram(wordclass)
            if ngram is not None:
                total += ngram.ratio
        return total

