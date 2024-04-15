from abc import ABCMeta, abstractmethod

class ExtractorController(metaclass=ABCMeta):

    @abstractmethod
    def update_needed(self, car):
        pass

    @abstractmethod
    def get_data(self):
        pass

    @abstractmethod
    def get_all_cars(self, car):
        pass

    @abstractmethod
    def get_car_json(self, car):
        pass

    @abstractmethod
    def save_car_json(self, car_data):
        pass
