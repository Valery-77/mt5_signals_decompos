import settings
from datetime import datetime, timedelta
from model.DealComment import DealComment
from model.MetaTrader5Wrapper import MetaTrader5Wrapper as M_t
from math import fabs


class Terminal:
    __slots__ = []

    @staticmethod
    def init(data):
        return M_t.init_mt(data)

    @staticmethod
    def get_balance():
        return M_t.get_balance()

    @staticmethod
    def get_contract(symbol):
        return M_t.get_contract_size(symbol)

    @staticmethod
    def get_signal_pips_tp(signal):
        """Расчет Тейк-профит в пунктах"""
        symbol = signal['signal_symbol']
        level = signal['target_value']
        price = signal['open_price']
        result = 0.0
        if level > 0:
            result = round(fabs(price - level) / M_t.get_symbol_info_point(symbol))
        return result

    @staticmethod
    def get_signal_pips_sl(signal):
        """Расчет Стоп-лосс в пунктах"""
        symbol = signal['signal_symbol']
        level = signal['stop_value']
        price = signal['open_price']
        result = 0.0
        if level > 0:
            result = round(
                fabs(price - level) / M_t.get_symbol_info_point(symbol))
        return result

    @staticmethod
    def get_position_pips_tp(position, price=None):
        """Расчет Тейк-профит в пунктах"""
        if price is None:
            price = position.price_open
        result = 0.0
        if position.tp > 0:
            result = round(fabs(price - position.tp) / M_t.get_symbol_info_point(position.symbol))
        return result

    @staticmethod
    def get_position_pips_sl(position, price=None):
        """Расчет Стоп-лосс в пунктах"""
        if price is None:
            price = position.price_open
        result = 0.0
        if position.sl > 0:
            result = round(fabs(price - position.sl) / M_t.get_symbol_info_point(position.symbol))
        return result

    @staticmethod
    def get_lieder_positions(lieder_init_data):
        if M_t.init_mt(lieder_init_data):
            return M_t.get_positions()
        return None

    @staticmethod
    def get_investor_positions(only_own=True):
        result = []
        positions = M_t.get_positions()
        if not positions:
            return []
        if only_own and len(positions) > 0:
            for _ in positions:
                if positions[positions.index(_)].magic == settings.MAGIC and DealComment.is_valid(_.comment):
                    result.append(_)
        else:
            result = positions
        return result

    @staticmethod
    def is_position_opened(lieder_position):
        """Проверка позиции лидера на наличие в списке позиций инвестора"""
        invest_positions = Terminal.get_investor_positions(only_own=False)
        if len(invest_positions) > 0:
            for pos in invest_positions:
                if DealComment.is_valid(pos.comment):
                    comment = DealComment().from_string(pos.comment)
                    if lieder_position['ticket'] == comment.lieder_ticket:
                        return True
        return False

    @staticmethod
    def is_lieder_position_in_investor_history(signal):
        date_from = settings.start_date + settings.SERVER_DELTA_TIME
        date_to = datetime.today().replace(microsecond=0) + timedelta(days=1)
        deals = M_t.get_history_deals_get_with_date(date_from, date_to)
        if not deals:
            deals = []
        result = None
        if len(deals) > 0:
            for pos in deals:
                if DealComment.is_valid(pos.comment):
                    comment = DealComment().from_string(pos.comment)
                    if signal['ticket'] == comment.lieder_ticket:
                        result = pos
                        break
        return result

    @staticmethod
    def open_position(symbol, deal_type, lot, lieder_position_ticket: int, tp=0.0, sl=0.0):
        """Открытие позиции"""
        try:
            point = M_t.get_symbol_info_point(symbol)
            price = tp_in = sl_in = 0.0
            if deal_type == 0:  # BUY
                deal_type = M_t.get_order_type_buy()
                price = M_t.get_symbol_info_tick(symbol).ask
            if tp != 0:
                tp_in = price + tp * point
            if sl != 0:
                sl_in = price - sl * point
            elif deal_type == 1:  # SELL
                deal_type = M_t.get_order_type_sell()
                price = M_t.get_symbol_info_tick(symbol).bid
                if tp != 0:
                    tp_in = price - tp * point
                if sl != 0:
                    sl_in = price + sl * point
        except AttributeError:
            return {'retcode': -200}
        comment = DealComment()
        comment.parent_ticket = lieder_position_ticket
        comment.reason = 101
        request = {
            "action": M_t.get_trade_action_deal(),
            "symbol": symbol,
            "volume": lot,
            "type": deal_type,
            "price": price,
            "sl": sl_in,
            "tp": tp_in,
            "deviation": settings.DEVIATION,
            "magic": settings.MAGIC,
            "comment": comment.string(),
            "type_time": M_t.get_order_time_gtc(),
            "type_filling": M_t.get_order_filling_fok(),
        }
        result = M_t.order_send(request)
        if result.retcode != 10009:
            print('request:', request, '\n', 'result:', result)
        return result

    @staticmethod
    def close_position(investor, position, reason):
        """Закрытие указанной позиции"""
        # if investor:
        #     init_mt(init_data=investor)
        tick = M_t.get_symbol_info_tick(position.symbol)
        if not tick:
            return
        new_comment_str = position.comment
        if DealComment.is_valid(position.comment):
            comment = DealComment().from_string(position.comment)
            comment.reason = reason
            new_comment_str = comment.string()
        request = {
            'action': M_t.get_trade_action_deal(),
            'position': position.ticket,
            'symbol': position.symbol,
            'volume': position.volume,
            'type': M_t.get_order_type_buy() if position.type == 1 else M_t.get_order_type_sell(),
            'price': tick.ask if position.type == 1 else tick.bid,
            'deviation': settings.DEVIATION,
            'magic:': settings.MAGIC,
            'comment': new_comment_str,
            'type_tim': M_t.get_order_time_gtc(),
            'type_filing': M_t.get_order_filling_ioc()
        }
        result = M_t.order_send(request)
        if comment and investor:
            print(
                f'\t\t -- [{investor["login"]}] - {comment.lieder_ticket} {DealComment.reasons[reason]} - {settings.send_retcodes[result.retcode][1]}')
        return result

    @staticmethod
    def force_close_all_positions(investor, reason):
        """Принудительное закрытие всех позиций аккаунта"""
        init_res = M_t.init_mt(init_data=investor)
        if init_res:
            positions = Terminal.get_investor_positions(only_own=False)
            if len(positions) > 0:
                for position in positions:
                    if position.magic == settings.MAGIC and DealComment.is_valid(position.comment):
                        Terminal.close_position(investor, position, reason=reason)

    @staticmethod
    def close_positions_by_lieder(investor, lieder_positions):
        """Закрытие позиций инвестора, которые закрылись у лидера"""
        M_t.init_mt(init_data=investor)
        positions_investor = Terminal.get_investor_positions()
        non_existed_positions = []
        if positions_investor:
            for ip in positions_investor:
                position_exist = False
                for lp in lieder_positions:
                    comment = DealComment().from_string(ip.comment)
                    if comment.lieder_ticket == lp.ticket:
                        position_exist = True
                        break
                if not position_exist:
                    non_existed_positions.append(ip)
        for pos in non_existed_positions:
            print('     close position:', pos.comment)
            Terminal.close_position(investor=investor, position=pos, reason=115)

    @staticmethod
    def close_signal_position(signal, reason):
        """Закрытие позиции инвестора"""
        positions_investor = Terminal.get_investor_positions()
        if positions_investor:
            for ip in positions_investor:
                comment = DealComment().from_string(ip.comment)
                if signal['ticket'] == comment.lieder_ticket:
                    Terminal.close_position(position=ip, reason=reason, investor=None)
            print(f'\t --- {signal["ticket"]} {DealComment.reasons[reason]}')

    @staticmethod
    def close_investor_positions(signal_list):
        """Закрытие позиций инвесторов по сопровождению"""
        for signal in signal_list:
            if signal['opening_deal'] == 'Сопровождение' or signal['closing_deal'] == 'Сопровождение':
                Terminal.close_signal_position(signal=signal, reason=110)

    @staticmethod
    def get_investor_position_for_signal(signal):
        positions = Terminal.get_investor_positions()
        for _ in positions:
            pos_comment = DealComment().from_string(_.comment)
            if pos_comment.lieder_ticket == signal['ticket']:
                return _
        return None

    @staticmethod
    def synchronize_position_limits(signal):
        """Изменение уровней ТП и СЛ указанной позиции"""
        i_pos = Terminal.get_investor_position_for_signal(signal)
        if not i_pos:
            return
        l_tp = Terminal.get_signal_pips_tp(signal)
        l_sl = Terminal.get_signal_pips_sl(signal)
        if l_tp > 0 or l_sl > 0:
            request = []
            new_comment_str = comment = ''
            if DealComment.is_valid(i_pos.comment):
                comment = DealComment().from_string(i_pos.comment)
                comment.reason = '004'
                new_comment_str = comment.string()
            if comment.lieder_ticket == signal['ticket']:
                i_tp = Terminal.get_position_pips_tp(i_pos)
                i_sl = Terminal.get_position_pips_sl(i_pos)
                sl_lvl = tp_lvl = 0.0
                point = M_t.get_symbol_info_point(i_pos.symbol)
                if i_pos.type == M_t.get_position_type_buy():
                    sl_lvl = i_pos.price_open - l_sl * point if l_sl > 0 else 0.0
                    tp_lvl = i_pos.price_open + l_tp * point if l_tp > 0 else 0.0
                elif i_pos.type == M_t.get_position_type_sell():
                    sl_lvl = i_pos.price_open + l_sl * point if l_sl > 0 else 0.0
                    tp_lvl = i_pos.price_open - l_tp * point if l_tp > 0 else 0.0
                if i_tp != l_tp or i_sl != l_sl:
                    request = {
                        "action": M_t.get_trade_action_sltp(),
                        "position": i_pos.ticket,
                        "symbol": i_pos.symbol,
                        "sl": sl_lvl,
                        "tp": tp_lvl,
                        "magic": settings.MAGIC,
                        "comment": new_comment_str
                    }
            if request:
                result = M_t.order_send(request)
                print('Изменение лимитов::', result)

    @staticmethod
    def is_symbol_allow(symbol):
        all_symbols = M_t.get_symbols()
        symbol_names = []
        for symbol_ in all_symbols:
            symbol_names.append(symbol_.name)

        if symbol in symbol_names:
            return M_t.select_symbol(symbol=symbol, select=True)
        else:
            return False

    #   -----------------------------------------------------------------------

    @staticmethod
    def is_signal_relevance(signal_item):
        price_open = signal_item['open_price']
        price_current = signal_item['current_price']
        deviation = signal_item['signal_relevance']
        deal_type = signal_item['deal_type']
        percent = price_open / 100
        if deal_type == 0:  # BUY
            actual_level = (price_open - price_current) / percent
        else:  # SELL
            actual_level = (price_current - price_open) / percent
        return actual_level < deviation

    @staticmethod
    def get_deal_volume(signal):
        investment_size = signal['investment'] * signal['multiplier']
        lieder_leverage = signal['deal_leverage']
        symbol = signal['signal_symbol']
        info_tick = M_t.get_symbol_info_tick(symbol)
        investor_price = info_tick.ask if signal['deal_type'] == 0 else info_tick.bid
        info_symbol = M_t.get_symbol_info(symbol)
        contract_size = info_symbol.trade_contract_size
        lot_step = info_symbol.volume_step
        decimals = str(lot_step)[::-1].find('.')
        result = round(investment_size * lieder_leverage / investor_price / contract_size, decimals)
        return result

    @staticmethod
    def is_profitability_achieved(signal):
        needed_level = signal['profitability']
        target_level = signal['target_value']
        if target_level == 0:
            print('Цель не установлена')
            return False
        if signal['deal_type'] == 0:  # BUY
            price = M_t.get_symbol_info_tick(signal['signal_symbol']).bid
            result = (target_level - price) / price * signal['multiplier']
        else:  # SELL
            price = M_t.get_symbol_info_tick(signal['signal_symbol']).ask
            result = (price - target_level) / price * signal['multiplier']
        print('profitability', result, '>=', needed_level)
        return result >= needed_level

    @staticmethod
    def is_risk_achieved(signal):
        needed_level = signal['risk']
        target_level = signal['stop_value']
        if target_level == 0:
            print('Стоп не установлен')
            return False
        if signal['deal_type'] == 0:  # BUY
            price = M_t.get_symbol_info_tick(signal['signal_symbol']).bid
            result = (target_level - price) / price * signal['multiplier']
        else:  # SELL
            price = M_t.get_symbol_info_tick(signal['signal_symbol']).ask
            result = (price - target_level) / price * signal['multiplier']
        print('risk', result, '<=', needed_level)
        return result <= needed_level

    @staticmethod
    def is_profit_achieved(signal):
        needed_level = signal['profit']
        target_level = signal['target_value']
        if target_level == 0:
            print('Цель не установлена')
            return False
        investment = signal['investment']
        if signal['deal_type'] == 0:  # BUY
            price = M_t.get_symbol_info_tick(signal['signal_symbol']).bid
            result = (target_level - price) / price * signal['multiplier'] * investment
        else:  # SELL
            price = M_t.get_symbol_info_tick(signal['signal_symbol']).ask
            result = (price - target_level) / price * signal['multiplier'] * investment
        print('profit', result, '>=', needed_level)
        return result >= needed_level
