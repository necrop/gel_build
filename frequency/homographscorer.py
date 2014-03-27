"""
HomographScorer
"""


class HomographScorer(object):

    def __init__(self, **kwargs):
        self.homographs = kwargs.get('homographs', [])
        self.frequency = kwargs.get('frequency', float(0))
        self.year = kwargs.get('year', 2000)

    def estimate(self):
        if len(self.homographs) == 1:
            self.homographs[0].scores[self.year] = self.frequency
            self.homographs[0].est[self.year] = False

        else:
            # Predict frequency for each homograph, based on entry size
            for homograph in self.homographs:
                homograph.prediction = homograph.predicted_frequency(self.year)

            max_prediction = max([h.prediction for h in self.homographs])

            # Triage:
            #  Homographs with relatively high predicted frequency
            #    (at least 10% of the highest prediction) get treated as 'big guns':
            #    these will share the actual ngram frequency.
            #  Homographs with lower predicted frequency get treated as
            #    'small fry': these will stick with predictions (factored downwards
            #    if necessary).
            big_guns = [h for h in self.homographs
                        if h.prediction >= max_prediction / 10]
            small_fry = [h for h in self.homographs
                         if h.prediction < max_prediction / 10]
            big_guns_total = sum([h.prediction for h in big_guns])
            small_fry_total = sum([h.prediction for h in small_fry])

            # Small fry keep the original predictions (or reduced
            #  proportionately if the total would exceed 10% of
            #  the total frequency)
            cap = self.frequency / 10
            if small_fry_total == 0:
                for homograph in small_fry:
                    homograph.scores[self.year] = 0
            elif small_fry_total < cap:
                for homograph in small_fry:
                    homograph.scores[self.year] = homograph.prediction
            else:
                for homograph in small_fry:
                    ratio = homograph.prediction / small_fry_total
                    homograph.scores[self.year] = cap * ratio
            # recalculate the total
            small_fry_total = sum([h.scores[self.year] for h in small_fry])

            # Big guns each get a proportionate share of the actual
            #  ngram frequency (minus whatever needs to be assigned to
            #  the small fry)
            if big_guns_total == 0:
                for homograph in big_guns:
                    homograph.scores[self.year] = 0
            else:
                for homograph in big_guns:
                    ratio = homograph.prediction / big_guns_total
                    homograph.scores[self.year] = (self.frequency - small_fry_total) * ratio

            for homograph in self.homographs:
                homograph.est[self.year] = True

    def trace(self):
        print('-----------------------------------------')
        print(self.homographs[0].form, self.homographs[0].wordclass)
        print('year: %d    total frequency: %0.3g   total prediction: %0.3g' %
              (self.year, self.frequency,
               sum([h.prediction for h in self.homographs])))
        for h in sorted(self.homographs, key=lambda h: h.prediction, reverse=True):
            print('\tsize=%0.3g\tprediction:%0.2g\tscore:%0.2g' %
                  (h.size(date=self.year), h.prediction, h.scores[self.year]))
        print('-----------------------------------------')
