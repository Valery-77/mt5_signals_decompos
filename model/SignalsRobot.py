import asyncio
from datetime import datetime
import aiohttp
import settings
from model.DealComment import DealComment
from model.Terminal import Terminal


class SignalsRobot:
    __slots__ = ["source", "signals_settings", "exist_lieder_signals", "new_lieder_signals",
                 "investor_signals_list", "event_loop"]

    def __init__(self):
        self.source = {}
        self.signals_settings = {}
        self.exist_lieder_signals = []
        self.investor_signals_list = []
        self.new_lieder_signals = []
        self.event_loop = asyncio.new_event_loop()

    @staticmethod
    def create_position_signal_json(lieder_balance, lieder_position):
        #   расчет плеча сделки лидера
        contract_size = Terminal.get_contract(lieder_position.symbol)
        if contract_size and lieder_balance > 0:
            leverage = (contract_size * lieder_position.volume * lieder_position.price_open) / lieder_balance
        else:
            leverage = 0
        #   тело запроса
        return {'ticket': lieder_position.ticket,
                'deal_type': lieder_position.type,
                'current_price': lieder_position.price_current,
                'deal_leverage': leverage,
                'signal_symbol': lieder_position.symbol,
                'open_price': lieder_position.price_open,
                'target_value': lieder_position.tp,
                'stop_value': lieder_position.sl,
                'status': True, }
        # 'profitability': lieder_position.profit,
        # 'type_ticket': '???',
        # 'pattern': 'Из стратегии',
        # 'signal_class': 'Из стратегии',
        # 'leverage': -1,
        # 'goal_value': -1,
        # 'stop': -1,
        # 'close_date': -1,
        # 'fin_res': -1,
        # 'draw_down': -1}

    @staticmethod
    def unite_signals_list(signals_list, signal_settings):
        united_signals = []
        for signal_ in signals_list:
            signal = signal_.copy()
            signal.update(signal_settings)  # сложить данные о сигнале лидера и настроек сигнала инвестора
            united_signals.append(signal)
        return united_signals

    def reset_source(self, only_investors=False):
        if only_investors:
            self.source['investors'] = []
        else:
            self.source = {
                # 'lieder': {}
                # 'investors': [{}, {}],
                # 'signals': [[{}, {}], [{}, {}]],
                # 'terminals_path': [str, str]
                'lieder': {'login': 66587203,
                           'password': '3hksvtko',
                           'server': 'MetaQuotes-Demo',
                           'terminal_path': r'C:\Program Files\MetaTrader 5\terminal64.exe'},
                'investors': [],
                # 'signals': [],
                'terminals_path': [r'C:\Program Files\MetaTrader 5_2\terminal64.exe',
                                   r'C:\Program Files\MetaTrader 5_3\terminal64.exe']}

    def get_investor_data(self, investor):
        idx = self.get_investor_id(investor)
        if idx < 0:
            return {}, {}, idx
        else:
            init_data = {'login': self.source['investors'][idx]['login'],
                         'server': self.source['investors'][idx]['server'],
                         'password': self.source['investors'][idx]['password'],
                         'terminal_path': self.source['terminals_path'][idx]}
            setting = {'multiplier': self.source['investors'][idx]['multiplier'],
                       'investment': self.source['investors'][idx]['investment'],
                       'opening_deal': self.source['investors'][idx]['opening_deal'],
                       'closing_deal': self.source['investors'][idx]['closing_deal'],
                       'target_and_stop': self.source['investors'][idx]['target_and_stop'],
                       'risk': self.source['investors'][idx]['risk'],
                       'signal_relevance': self.source['investors'][idx]['signal_relevance'],
                       'profitability': self.source['investors'][idx]['profitability'],
                       'profit': self.source['investors'][idx]['profit']}
            return init_data, setting, idx

    def get_investor_id(self, investor):
        for _ in self.source['investors']:
            if _['login'] == investor['login']:
                return self.source['investors'].index(_)
        return -1

    async def get_investor_settings(self, sleep=settings.sleep_update):
        url = settings.host + 'signals_settings'
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as get_response:
                        response = await get_response.json()
            except Exception as e:
                print(e)
                response = {}
            if len(response):
                self.reset_source(only_investors=True)
                self.signals_settings = response[0]
                investor_data_first = {'login': self.signals_settings['investor_login_1'],
                                       'password': self.signals_settings['investor_password_1'],
                                       'server': self.signals_settings['investor_server_1'],
                                       'investment': self.signals_settings['investment_1'],
                                       'multiplier': self.signals_settings['multiplier'],
                                       'opening_deal': self.signals_settings['opening_deal'],
                                       'closing_deal': self.signals_settings['closing_deal'],
                                       'target_and_stop': self.signals_settings['target_and_stop'],
                                       'profitability': self.signals_settings['profitability'],
                                       'risk': self.signals_settings['risk'],
                                       'profit': self.signals_settings['profit'],
                                       'signal_relevance': self.signals_settings['signal_relevance']}

                self.source['investors'].append(investor_data_first)
                investor_data_second = investor_data_first.copy()
                investor_data_second['login'] = self.signals_settings['investor_login_2']
                investor_data_second['password'] = self.signals_settings['investor_password_2']
                investor_data_second['server'] = self.signals_settings['investor_server_2']
                investor_data_second['investment'] = self.signals_settings['investment_2']
                self.source['investors'].append(investor_data_second)
            else:
                self.reset_source()
            await asyncio.sleep(sleep)

    async def get_signals_list(self, sleep=settings.sleep_update):
        url = settings.host + 'active_signals'
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as get_response:
                        response = await get_response.json()
            except Exception as e:
                print(e)
                response = {}
            investor_signals_list = []
            if len(response):
                for signal in response:
                    investor_signals_list.append(signal)
            self.investors_executor()
            await asyncio.sleep(sleep)

    async def disable_closed_positions_signals(self):
        """Отправка статуса"""
        close_position_signal_list = []
        for old_signal in self.exist_lieder_signals:  # Отправка статуса и даты закрытия
            signal_exist = False
            for new_signal in self.new_lieder_signals:
                if old_signal['ticket'] == new_signal['ticket']:
                    signal_exist = True
                    break
            if not signal_exist:
                async with aiohttp.ClientSession() as session:
                    url = settings.host + f'update_signal/{old_signal["ticket"]}'
                    data = {'status': False, 'close_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    async with session.patch(url=url, data=data) as resp_patch:
                        await resp_patch.json()
                close_position_signal_list.append(old_signal)

        self.exist_lieder_signals = self.new_lieder_signals.copy()  # -----------

        return close_position_signal_list

    def investors_executor(self):
        if len(self.source['investors']):
            for _ in self.source['investors']:
                self.execute_investor(_, self.investor_signals_list)

    async def execute_lieder(self, sleep=settings.sleep_update):
        url_post = settings.host + 'create_signal'
        while True:
            lieder_positions = Terminal.get_lieder_positions(lieder_init_data=self.source['lieder'])
            new_lieder_signals = []

            if lieder_positions:
                try:
                    balance = Terminal.get_balance()
                    for position in lieder_positions:  # Коллекция существующих сигналов
                        data_json = self.create_position_signal_json(balance, position)
                        new_lieder_signals.append(data_json)
                    for new_signal in new_lieder_signals:  # Отправка сигналов на сервер
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url=url_post, data=new_signal) as resp_post:
                                await resp_post.json()
                                if resp_post.status == 400:  # Если такой сигнал существует, обновить данные
                                    url = settings.host + f'update_signal/{new_signal["ticket"]}'
                                    data = {'current_price': new_signal['current_price'],
                                            'target_value': new_signal['target_value'],
                                            'stop_value': new_signal['stop_value'], }
                                    async with session.patch(url=url, data=data) as resp_patch:
                                        await resp_patch.json()
                except Exception as e:
                    print('execute_lieder()', e)

            await self.disable_closed_positions_signals()  # ----------------------------   Закрытие сигналов

            print(
                f'\n\tЛидер [{self.source["lieder"]["login"]}] {datetime.now().time()} - {len(new_lieder_signals)} сигнал')
            await asyncio.sleep(sleep)

    def execute_investor(self, investor, new_signals_list):
        investor_init_data, settings_signal, investor_id = self.get_investor_data(investor)
        if not Terminal.init(investor_init_data):
            return

        print(
            f'\tИнвестор [{investor["login"]}] {datetime.now().time()} - {len(Terminal.get_investor_positions())} позиций')
        #   ---------------------------------------------------------------------------     Объединение сигналов и настроек
        signal_list = SignalsRobot.unite_signals_list(new_signals_list, settings_signal)
        #   ---------------------------------------------------------------------------     Закрытие позиций по Сопровождению
        exist_positions = Terminal.get_investor_positions()
        for e_pos in exist_positions:
            comment = DealComment().from_string(e_pos.comment)
            position_exist = False
            for signal in signal_list:
                if signal['closing_deal'] != 'Сопровождение':
                    continue
                if signal['ticket'] == comment.lieder_ticket:
                    position_exist = True
                    break
            if not position_exist:
                Terminal.close_position(investor=investor, position=e_pos, reason=110)
        #   ---------------------------------------------------------------------------     Открытие
        for signal in signal_list:

            if signal['opening_deal'] in ['Пропуск', 'Не выбрано']:  # Пропустить по настройкам
                continue
            if not Terminal.is_symbol_allow(signal['signal_symbol']):  # Пропустить если символ недоступен
                print(f'\t\tСимвол {signal["signal_symbol"]} недоступен')
                continue
            if Terminal.is_position_opened(signal):  # Пропустить если уже открыта
                continue
            if Terminal.is_lieder_position_in_investor_history(signal):  # Пропустить если уже была открыта (в истории)
                print(f'\t\tПозиция по сигналу {signal["ticket"]} закрыта ранее инвестором [{investor["login"]}]')
                continue
            if not Terminal.is_signal_relevance(signal):  # Пропустить если сигнал неактуален
                print(f'\t\tСигнал {signal["ticket"]} неактуален')
                continue
            if signal['opening_deal'] == 'Сопровождение' or signal['target_and_stop'] == 'Выставлять':
                tp = Terminal.get_signal_pips_tp(signal)
                sl = Terminal.get_signal_pips_sl(signal)
            else:
                tp = sl = 0.0
            volume = Terminal.get_deal_volume(signal)
            response = Terminal.open_position(symbol=signal['signal_symbol'], deal_type=signal['deal_type'],
                                              lot=volume, lieder_position_ticket=signal['ticket'], tp=tp, sl=sl)
            if response:
                try:
                    ret_code = response.retcode
                except AttributeError:
                    ret_code = response['retcode']
                if ret_code:
                    deal_type = 'BUY' if signal['deal_type'] == 0 else 'SELL'
                    msg = f'\t --- [{investor["login"]}] {deal_type} {settings.send_retcodes[ret_code][1]}:{ret_code} : сигнал {signal["ticket"]}'
                    print(msg)
            else:
                print('EMPTY_OPEN_DEAL_RESPONSE')
        #   ---------------------------------------------------------------------------     Сопровождение
        for signal in signal_list:

            # Коррекция Тейк-профит и Стоп-лосс
            if signal['opening_deal'] == 'Сопровождение' or signal['target_and_stop'] == 'Выставлять':
                Terminal.synchronize_position_limits(signal=signal)

        #   ---------------------------------------------------------------------------     Закрытие
        for signal in signal_list:
            if signal['closing_deal'] in ['Пропуск', 'Не выбрано']:  # Пропустить по настройкам
                continue

            if signal['closing_deal'] == 'Закрыть':  # Ручное закрытие через инвест платформу
                Terminal.close_signal_position(signal=signal, reason=111)

            if Terminal.is_risk_achieved(signal):  # Риск
                Terminal.close_signal_position(signal=signal, reason=112)

            if Terminal.is_profitability_achieved(signal):  # Доходность
                Terminal.close_signal_position(signal=signal, reason=113)

            if Terminal.is_profit_achieved(signal):  # Прибыль
                Terminal.close_signal_position(signal=signal, reason=114)

    def run(self):
        print(
            f'\nСистема сигналов [{settings.start_date}]. Обновление Лидера [{self.source["lieder"]["login"]}] {settings.sleep_update} с.\n')
        self.event_loop.create_task(self.get_investor_settings())
        self.event_loop.create_task(self.execute_lieder())
        self.event_loop.create_task(self.get_signals_list())
        self.event_loop.run_forever()
