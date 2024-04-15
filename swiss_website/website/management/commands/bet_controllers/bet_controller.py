from abc import ABCMeta, abstractmethod

class BetController(metaclass=ABCMeta):
    @abstractmethod
    def bet(self, auction_obj, price, price_max, is_aggressive=False):
        pass

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def prepare(self):
        pass

    @abstractmethod
    def logout(self):
        pass
