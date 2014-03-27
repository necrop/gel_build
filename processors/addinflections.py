"""
AddInflections
"""

import re

from lxml import etree

import gelconfig
from lex.gel.fileiterator import FileIterator
from lex.inflections.mmh.mmhcache import MmhCache
from lex.inflections.inflection import Inflection, ArchaicEndings
from lex.wordclass.wordclass import Wordclass
from lex.lemma import Lemma

MORPHOLOGY = MmhCache()
INFLECTOR = Inflection()
ARCHAIC = ArchaicEndings()
INFLECTABLE = set(('NN', 'JJ', 'VB'))
UNINFLECTABLE = re.compile(r'(^the |[ -](and)[ -])', re.I)
DONT_PLURALIZE = re.compile(r'[a-z]{3}(' + gelconfig.UNPLURALIZED + ')$', re.I)


def add_inflections(in_dir, out_dir):
    iterator = FileIterator(in_dir=in_dir, out_dir=out_dir, verbosity='low')
    for filecontent in iterator.iterate():
        for entry in filecontent.entries:
            for wordclass_set in [wcs for wcs in entry.wordclass_sets()
                                  if wcs.wordclass() in INFLECTABLE]:
                _process_wordclass_set(wordclass_set)


def _process_wordclass_set(wordclass_set):
    morphsets = wordclass_set.morphsets()
    wordclass = wordclass_set.wordclass()
    if morphsets and not _dont_inflect(morphsets[0].form, wordclass):
        # Set the model, and apply this to the first morphset
        model = InflectionSet(morphsets[0].form, wordclass)
        if not UNINFLECTABLE.search(morphsets[0].form):
            inflections, matched = _inflect_from_mmh(morphsets[0], wordclass)
            if not matched:
                inflections = _compute_inflections(morphsets[0], wordclass)
            for inflection in inflections:
                model.add_inflection(inflection)
        morphsets[0].inflections = model

        for i, morphset in enumerate(morphsets):
            # We skip the first morphset, since this has already been
            #  done when setting the model
            if i == 0:
                continue
            inf_set = InflectionSet(morphset.form, wordclass)
            if model.is_inflected():
                inflections, matched = _inflect_from_mmh(morphset, wordclass)
                if not matched:
                    inflections = _compute_inflections(morphset, wordclass,
                                                      model=model)
                for inflection in inflections:
                    inf_set.add_inflection(inflection)
            morphset.inflections = inf_set

        for morphset in morphsets:
            if morphset.date().end <= 1500:
                inf_set = morphset.inflections
                extra_inflections = []
                for inflection in inf_set.inflections:
                    archaics = ARCHAIC.process(inflection.form, inflection.wordclass)
                    for a in archaics:
                        extra_inflections.append(
                            InflectionUnit(a, inflection.wordclass, True))
                for inflection in extra_inflections:
                    inf_set.add_inflection(inflection)

        for morphset in morphsets:
            inf_set = morphset.inflections
            if morphset.types()[0].is_computed():
                for inflection in inf_set.inflections:
                    inflection.computed = True
            for inflection in inf_set.inflections:
                morphset.node.append(inflection.xml())


class InflectionSet(object):

    def __init__(self, baseform, baseclass):
        self.lemma_manager = Lemma(baseform)
        self.baseclass = baseclass
        self.inflections = []
        self.inflections_computed = {}

    @property
    def baseform(self):
        return self.lemma_manager.lemma

    def add_inflection(self, inf_unit):
        self.inflections.append(inf_unit)

    def is_inflected(self):
        if self.inflections:
            return True
        else:
            return False

    def is_regular(self, wordclass):
        if not wordclass in self.inflections_computed:
            self.inflections_computed[wordclass] =\
                INFLECTOR.compute_inflection(self.baseform, wordclass)
        for inflection in self.inflections:
            if (inflection.wordclass == wordclass and
                inflection.form == self.inflections_computed[wordclass]):
                return True
        return False


class InflectionUnit(object):

    def __init__(self, form, wordclass, computed):
        self.lemma_manager = Lemma(form)
        self.wordclass = wordclass
        self.computed = computed

    @property
    def form(self):
        return self.lemma_manager.lemma

    def xml(self):
        wordclass_manager = Wordclass(self.wordclass)
        node = etree.Element('type')
        if self.computed:
            node.set('computed', 'true')
        formnode = etree.SubElement(node, 'form')
        formnode.text = self.form
        node.append(wordclass_manager.to_xml())
        return node


def _inflect_from_mmh(morphset, wordclass):
    mmh_sets = MORPHOLOGY.inflect_fuzzy(morphset.form, wordclass=wordclass)
    # Allow for US variation in inflected forms (esp. no consonant
    #  doubling in adjective grades and verb inflections) 
    if (morphset.date().end > 1900 and
            wordclass in ('VB', 'JJ') and
            len(mmh_sets) > 1 and
            ((mmh_sets[0].variant_type == 'us' and mmh_sets[1].variant_type != 'us') or
            (mmh_sets[0].variant_type != 'us' and mmh_sets[1].variant_type == 'us'))):
        mmh_sets = mmh_sets[0:2]
    # If it's a noun, pick a morphology set with a plural, even if it's not
    #  the highest-scoring - in order to be inclusive of plural forms, even
    #  if rarely used (e.g. 'intelligences').
    elif mmh_sets and wordclass == 'NN' and mmh_sets[0].contains('NNS'):
        mmh_sets = [mmh_sets[0],]
    elif mmh_sets and wordclass == 'NN':
        base_lemma = mmh_sets[0].lemma
        plural_sets = [mmh_set for mmh_set in mmh_sets if
                       mmh_set.lemma == base_lemma and
                       mmh_set.contains('NNS')]
        try:
            mmh_sets = [plural_sets[0],]
        except IndexError:
            mmh_sets = [mmh_sets[0],] 
    # Otherwise, just pick the first morphology set (the highest-scoring one).
    elif mmh_sets:
        mmh_sets = [mmh_sets[0],]

    output = []
    seen = set()
    for mmh_set in mmh_sets:
        for unit in mmh_set.morphunits:
            signature = (unit.form, unit.wordclass)
            if unit.wordclass != wordclass and not signature in seen:
                output.append(InflectionUnit(unit.form,
                                             unit.wordclass,
                                             mmh_set.computed))
                seen.add(signature)

    return output, len(mmh_sets)


def _compute_inflections(morphset, wordclass, model=None):
    if wordclass == 'VB':
        return _compute_verb_inflections(morphset, model)
    elif wordclass == 'NN':
        return _compute_plural(morphset, model)
    else:
        # We don't compute inflections for adjectives; if it's not in the
        #  morphology hub, we assume it does not inflect.
        return []


def _compute_plural(morphset, model):
    if (INFLECTOR.has_plural_form(morphset.form) or
            DONT_PLURALIZE.search(morphset.form)):
        return []
    if model and not model.is_regular('NNS'):
        return []

    if morphset.date().end <= 1600:
        plural = INFLECTOR.compute_inflection(morphset.form, 'NNS',
                                              archaic=True)
    else:
        plural = INFLECTOR.compute_inflection(morphset.form, 'NNS')
    #print repr(morphset.form) + '\t' + repr(plural)
    return [InflectionUnit(plural, 'NNS', True),]


def _compute_verb_inflections(morphset, model):
    output = []
    for inf_class in ('VBZ', 'VBG', 'VBD', 'VBN'):
        if model and not model.is_regular(inf_class):
            continue
        if (model and morphset.date().end < 1700 and
                not _verb_matches(model.baseform, morphset.form)):
            continue

        form = INFLECTOR.compute_inflection(morphset.form, inf_class)
        output.append(InflectionUnit(form, inf_class, True))
    return output


def _verb_matches(form1, form2):
    if re.search(r'ne?$', form1) and not re.search(r'ne?$', form2):
        return False
    elif re.search(r'ne?$', form2) and not re.search(r'ne?$', form1):
        return False
    else:
        return True


def _dont_inflect(form, wordclass):
    if 'etc.' in form or ',' in form:
        return True
    elif wordclass == 'VB' and re.search(r'(^| )(the|of|a|an|in|if|i) ', form, re.I):
        return True
    elif wordclass == 'VB' and re.search(r'[ -].+[ -]', form):
        return True
    elif wordclass == 'NN' and re.search(r'(^| )(a|an|his|her|its|if|i) ', form, re.I):
        return True
    elif wordclass == 'NN' and re.search(r' .+ of ', form):
        return True
    return False