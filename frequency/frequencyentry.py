"""
FrequencyEntry
"""

from lex.gbn.ngram import Ngram
from frequency.frequencypredictor import FrequencyPredictor
from frequency.oedsize.oedentrysize import WeightedSize
from frequency.wordclass.corpusprobability import BncPosProbability
from lex.frequencytable import FrequencyTable

FREQUENCY_PREDICTOR = FrequencyPredictor()
BNC_PROB = BncPosProbability()
WEIGHTED_SIZE_MANAGER = WeightedSize(averaged=True)
DEFAULT_SIZES = {
    'general': float(1),  # size assigned to unsized lemmas
    'np': float(20),  # size assigned to encyclopedic entries
}


class FrequencyEntry(object):

    def __init__(self, node):
        self.node = node
        self.sortcode = node.get('sort')
        self.form = node.findtext('./form')

        self.lex_items = [LexItem(instance, self.form) for instance in
                          node.findall('./lex/instance')]
        self.compile_ngrams()

    def gram_count(self):
        if self.tagged_ngrams:
            return self.tagged_ngrams[0].gram_count
        else:
            return 0

    def compile_ngrams(self):
        self.tagged_ngrams = _parse_raw_ngrams(self.node,
                                               self.form,
                                               self.sortcode)

        # Special handling of interjections: If there's an interjection
        #  ('UH') registered in the corresponding BNC probability set,
        #   we adjust all the ngram values downwards proportionally.
        #  (Since the interjection will be missing from this entry set,
        #   treated separately - e.g. 'fuck_UH' is treated
        #   separately as 'Fuck!'.)
        bnc_prob = BNC_PROB.find(self.form)
        if bnc_prob and bnc_prob.interjection_ratio:
            remainder = 1 - bnc_prob.interjection_ratio
            for ngram in self.tagged_ngrams:
                ngram.multiply_values(remainder)

        # Pick out the 'ALL' ngram, to be used as the main unmarked
        #  set of values
        self.ngram = None
        for n in self.tagged_ngrams:
            if n.wordclass == 'ALL':
                self.ngram = n

    def raw_ngram(self):
        """
        Get the main ('ALL') ngram in its raw form, without any special
        handling/adjustments for interjections, etc.
        """
        ngrams = _parse_raw_ngrams(self.node, self.form, self.sortcode)
        for n in ngrams:
            if n.wordclass == 'ALL':
                return n
        return None

    def contains_oed_entry(self):
        return any([l.is_oed_entry() for l in self.lex_items])

    def contains_wordclass(self, wordclass):
        return any([l.wordclass == wordclass for l in self.lex_items])


class LexItem(object):

    def __init__(self, node, form):
        self.node = node
        self.form = form
        self.scores = {}
        self.est = {}
        self.attributes = {key: node.get(key) for key in node.attrib}
        for key in ('start', 'end'):
            self.attributes[key] = int(self.attributes[key])

    @property
    def base(self):
        return self.attributes.get('base', None)

    @property
    def xrid(self):
        return self.attributes.get('xrid', None)

    @property
    def xnode(self):
        return self.attributes.get('xnode', None)

    @property
    def wordclass_id(self):
        return self.attributes['wordclassId']

    @property
    def type_id(self):
        return self.attributes['typeId']

    @property
    def start(self):
        return self.attributes['start']

    @property
    def end(self):
        return self.attributes['end']

    @property
    def wordclass(self):
        return self.attributes['wordclass']

    @property
    def is_variant(self):
        return bool(self.attributes.get('variant'))

    def size(self, date=2000, mode='weighted'):
        s = _find_size(self.xrid,
                       self.xnode,
                       wordclass=self.wordclass,
                       date=date,
                       mode=mode)
        if self.is_variant:
            return s / 3
        else:
            return s

    def frequency_table(self):
        try:
            return self._frequency_table
        except AttributeError:
            fnode = self.node.find('./frequency')
            if fnode is not None:
                self._frequency_table = FrequencyTable(node=fnode)
            else:
                self._frequency_table = None
            return self._frequency_table

    def frequencies(self):
        try:
            return self._frequencies
        except AttributeError:
            self._frequencies = dict()
            if self.frequency_table() is not None:
                for p in self.frequency_table().data:
                    self._frequencies[p] = self.frequency_table().frequency(period=p)
            return self._frequencies

    def frequency(self, period='modern'):
        if period in self.frequencies():
            return self.frequencies()[period]
        elif 'modern' in self.frequencies():
            return self.frequencies()['modern']
        else:
            return float(0)

    def is_oed_entry(self):
        if (self.xrid and
                self.xnode and
                WEIGHTED_SIZE_MANAGER.find_size(id=self.xrid, eid=self.xnode)):
            return True
        else:
            return False

    def predicted_frequency(self, date=2000):
        try:
            self._predictions
        except AttributeError:
            self._predictions = {}
        if not date in self._predictions:
            self._predictions[date] = FREQUENCY_PREDICTOR.predict(
                size=self.size(date=date),
                wordclass=self.wordclass,
            )
        return self._predictions[date]


def _find_size(id, eid, wordclass='NN', date=2000, mode='weighted'):
    size = None
    if id and eid:
        size = WEIGHTED_SIZE_MANAGER.find_size(id=id,
                                               eid=eid,
                                               type=mode,
                                               date=date)
    if not size:
        if wordclass == 'NP':
            size = DEFAULT_SIZES['np']
        else:
            size = DEFAULT_SIZES['general']
    return size


def _parse_raw_ngrams(node, wordform, sortcode):
    ngrams = []
    for ngram_node in node.findall('gbn/ngram'):
        datestring = ngram_node.text
        if datestring:
            dates = datestring.strip().replace(' ', '\t')
            wordclass = ngram_node.get('wordclass')
            # Determiners get remapped to adjective, since OED appears
            # to treat 'the', 'a', 'this', etc., as adjectives
            if wordclass == 'DET':
                wordclass = 'ADJ'
            line = '%s\t%s\t%s\t%s' % (sortcode,
                                       wordform,
                                       wordclass,
                                       dates)
            ngram = Ngram(line, gramCount=ngram_node.get('n'))

            # Add this ngram to the list; unless the same wordclass already
            #  appears in the list, in which case we merge in this
            #  one's counts
            merged = False
            for previous in ngrams:
                if previous.wordclass == ngram.wordclass:
                    previous.merge(ngram)
                    merged = True
                    break
            if not merged:
                ngrams.append(ngram)
    return ngrams
