from typing import Iterable

from dmp.preprocessing.preprocessor import Preprocessor


class Standardizer(Preprocessor):
    
    def __init__(self, data: Iterable):
        # Welford's algorithm
        minimum = None
        maximum = None
        for element in data:
            if minimum is None or minimum > element:
                minimum = element
            if maximum is None or maximum < element:
                maximum = element
        
        self.minimum = minimum
        self.maximum = maximum
        if maximum is None or minimum is None:
            self.range = None
        else:
            self.range = maximum - minimum
        
    
    def forward(self, element):
        return (element - self.minimum) / self.range
    
    def backward(self, element):
        return element * self.range + self.minimum
