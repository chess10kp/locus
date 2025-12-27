class NotLinuxException(Exception):
    def __init__(self):
        super().__init__("Dashboard probably doesnt work on non-linux envs")


class NoValueFoundException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class WeatherUnavailableException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
