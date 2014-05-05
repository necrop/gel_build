"""
interjectionhandler

In general, interjections are handled by treating xxx_UH as Xxx!
e.g. for 'fuck' as an interjection, we sue the ngram for 'Fuck!'

But this can underestimate the interjection (and, conversely, overestimate
the other parts of speech for the same word) - e.g. for the lemma 'hey',
almost all occurrences are interjections, not just those with the surface
form 'Hey!'.

To mitigate for this, we check for BNC probability sets which include a
ratio for the UH-use. For these lemmas, we cache the corresponding ngram.
Then, when we're processing the frequency entry for the interjections
(e.g. 'Hey!'), we retrieve the 'hey' ngram from the cache, figure out what
proportion of its counts should be assigned to the interjection, and
add this to the ngram counts for 'Hey!'

The FrequencyEntry.compile_ngrams() method includes logic
to reduce counts proportionally for the other parts of speech.
"""

from frequency.frequencyiterator import FrequencyIterator
from frequency.wordclass.corpusprobability import BncPosProbability

BNC_PROB = BncPosProbability()


class InterjectionHandler:

    def __init__(self, in_dir):
        self.in_dir = in_dir
        self.index = {}

    def index_interjections(self):
        freq_iterator = FrequencyIterator(in_dir=self.in_dir,
                                          message='Checking interjections')
        # Iterate through each entry in the frequency build files, looking
        #   for entries for which BNC gives an interjection ratio; cache
        #   the main ngram in memory
        for entry in freq_iterator.iterate():
            wordform = entry.form
            bnc_prob = BNC_PROB.find(wordform)
            if bnc_prob and bnc_prob.interjection_ratio:
                self.index[wordform] = entry.raw_ngram()

    def supplement_ngram(self, wordform, ngram):
        wordform = wordform.lower().strip('!')
        try:
            supplement = self.index[wordform]
        except KeyError:
            pass
        else:
            if supplement:
                # Retrieve the BNC probability set
                bnc_prob = BNC_PROB.find(wordform)
                # Adjust the supplement to the correct proportion
                # (based on the ratio given in BNC)
                supplement.multiply_values(bnc_prob.interjection_ratio)
                # Add new values to the existing ngram values
                # (e.g. 'hey' values added to 'Hey!' values)
                if not ngram:
                    ngram = supplement
                else:
                    ngram.merge(supplement)
        return ngram
