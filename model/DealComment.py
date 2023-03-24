class DealComment:
    __slots__ = ['parent_ticket', 'reason']

    SEPARATOR = '-'

    reasons = {
        101: 'Открыто системой',
        105: 'Лимиты изменены',
        110: 'Закрыто Лидером',
        111: 'Закрыто через инвест платформу',
        112: 'Закрыто по достижению уровня Риска',
        113: 'Закрыто по достижению уровня Доходности',
        114: 'Закрыто по достижению уровня Прибыли',
        115: 'Закрыто принудительно все',
    }

    def __init__(self):
        self.parent_ticket = -1
        self.reason = 0

    @staticmethod
    def is_valid(string: str):
        if len(string) > 0:
            sliced = string.split(DealComment.SEPARATOR)
            if len(sliced) == 2:
                try:
                    if int(sliced[1]) not in DealComment.reasons:
                        return False
                    ticket = int(sliced[0])
                    if ticket < 0:
                        return False
                except ValueError:
                    return False
            else:
                return False
        return True

    @property
    def string(self):
        return f'{self.parent_ticket}' + DealComment.SEPARATOR + f'{self.reason}'

    def from_string(self, string: str):
        if not DealComment.is_valid(string):
            return self
        split_str = string.split(DealComment.SEPARATOR)
        self.parent_ticket = int(split_str[0])
        self.reason = int(split_str[1])
        return self
