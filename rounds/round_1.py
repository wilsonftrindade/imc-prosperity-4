import json
from typing import List, Dict, Any

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out

logger = Logger()



class Trader:

    PEPPER = "INTARIAN_PEPPER_ROOT"
    ASH = "ASH_COATED_OSMIUM"

    PEPPER_LIMIT = 80
    ASH_LIMIT = 80

    # Pepper parameters
    PEPPER_SLOPE_WINDOW = 200
    PEPPER_SHORT_THRESHOLD = -0.8
    PEPPER_RSQUARED_MIN = 0.7

    # ASH parameters
    ASH_HARD_PEG = 10000
    ASH_PEG_WEIGHT = 0.85
    ASH_MIN_EDGE = 2
    ASH_GAMMA = 0.10
    ASH_MAX_CLIP = 10

    def run(self, state: TradingState):
        conversions = 0
        traderData = ""
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except:
            trader_state = {}

        history = trader_state.get("pepper_history", [])
        od_pepper = state.order_depths.get(self.PEPPER)
        history = self._update_history(history, od_pepper)

        result = {}
        result[self.PEPPER] = self.trade_pepper(state, history)
        result[self.ASH] = self.trade_ash(state)

        new_trader_data = json.dumps({"pepper_history": history})
        logger.flush(state, result, conversions, traderData)
        return result, 0, new_trader_data

    def _update_history(self, history: List[float], od) -> List[float]:
        new_history = list(history)
        if od and od.buy_orders and od.sell_orders:
            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            new_history.append((best_bid + best_ask) / 2.0)
        if len(new_history) > self.PEPPER_SLOPE_WINDOW:
            new_history = new_history[-self.PEPPER_SLOPE_WINDOW:]
        return new_history

    def _is_strong_downtrend(self, history: List[float]) -> bool:
        n = len(history)
        if n < self.PEPPER_SLOPE_WINDOW:
            return False

        x_mean = (n - 1) / 2.0
        y_mean = sum(history) / n

        ss_xy = 0.0
        ss_xx = 0.0
        ss_yy = 0.0

        for i in range(n):
            dx = i - x_mean
            dy = history[i] - y_mean
            ss_xy += dx * dy
            ss_xx += dx * dx
            ss_yy += dy * dy

        if ss_xx == 0 or ss_yy == 0:
            return False

        slope = ss_xy / ss_xx
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)

        return slope < self.PEPPER_SHORT_THRESHOLD and r_squared > self.PEPPER_RSQUARED_MIN

    def trade_pepper(self, state: TradingState, history: List[float]) -> List[Order]:
        od = state.order_depths.get(self.PEPPER)
        if od is None:
            return []
        if self._is_strong_downtrend(history):
            return self._pepper_short(state, od)
        return self._pepper_long(state, od)

    def _pepper_long(self, state: TradingState, od) -> List[Order]:
        orders = []
        if not od.sell_orders:
            return []
        position = state.position.get(self.PEPPER, 0)
        buy_room = self.PEPPER_LIMIT - position
        if buy_room <= 0:
            return []
        for ask_price in sorted(od.sell_orders.keys()):
            ask_volume = -od.sell_orders[ask_price]
            fill = min(ask_volume, buy_room)
            if fill > 0:
                orders.append(Order(self.PEPPER, int(ask_price), int(fill)))
                buy_room -= fill
            if buy_room <= 0:
                break
        if buy_room > 0:
            if od.buy_orders:
                best_bid = max(od.buy_orders.keys())
                best_ask = min(od.sell_orders.keys())
                ideal_bid = best_bid + 1
                if ideal_bid >= best_ask:
                    ideal_bid = best_bid
            else:
                best_ask = min(od.sell_orders.keys())
                ideal_bid = best_ask - 1
            orders.append(Order(self.PEPPER, int(ideal_bid), int(buy_room)))
        return orders

    def _pepper_short(self, state: TradingState, od) -> List[Order]:
        orders = []
        if not od.buy_orders:
            return []
        position = state.position.get(self.PEPPER, 0)
        sell_room = self.PEPPER_LIMIT + position
        if sell_room <= 0:
            return []
        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            bid_volume = od.buy_orders[bid_price]
            fill = min(bid_volume, sell_room)
            if fill > 0:
                orders.append(Order(self.PEPPER, int(bid_price), -int(fill)))
                sell_room -= fill
            if sell_room <= 0:
                break
        if sell_room > 0:
            if od.sell_orders:
                best_ask = min(od.sell_orders.keys())
                best_bid = max(od.buy_orders.keys())
                ideal_ask = best_ask - 1
                if ideal_ask <= best_bid:
                    ideal_ask = best_ask
            else:
                best_bid = max(od.buy_orders.keys())
                ideal_ask = best_bid + 1
            orders.append(Order(self.PEPPER, int(ideal_ask), -int(sell_room)))
        return orders

    def trade_ash(self, state: TradingState) -> List[Order]:
        od = state.order_depths.get(self.ASH)
        if not od:
            return []

        orders = []
        position = state.position.get(self.ASH, 0)

        best_bid = max(od.buy_orders.keys()) if od.buy_orders else self.ASH_HARD_PEG - 5
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else self.ASH_HARD_PEG + 5

        if od.buy_orders and od.sell_orders:
            bid_vol = od.buy_orders[best_bid]
            ask_vol = -od.sell_orders[best_ask]
            total_vol = bid_vol + ask_vol
            micro_price = ((best_bid * ask_vol) + (best_ask * bid_vol)) / total_vol
        else:
            micro_price = (best_bid + best_ask) / 2.0

        fair_value = (self.ASH_HARD_PEG * self.ASH_PEG_WEIGHT) + (micro_price * (1 - self.ASH_PEG_WEIGHT))

        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price >= fair_value:
                break
            qty = -od.sell_orders[ask_price]
            room = self.ASH_LIMIT - position
            if room > 0:
                filled = min(qty, room)
                orders.append(Order(self.ASH, ask_price, filled))
                position += filled

        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price <= fair_value:
                break
            qty = od.buy_orders[bid_price]
            room = self.ASH_LIMIT + position
            if room > 0:
                filled = min(qty, room)
                orders.append(Order(self.ASH, bid_price, -filled))
                position -= filled

        skew = position * self.ASH_GAMMA

        ideal_bid = best_bid + 1
        ideal_ask = best_ask - 1

        max_safe_bid = fair_value - self.ASH_MIN_EDGE - skew
        min_safe_ask = fair_value + self.ASH_MIN_EDGE - skew

        our_bid = int(min(ideal_bid, max_safe_bid))
        our_ask = int(max(ideal_ask, min_safe_ask))

        if our_bid >= our_ask:
            our_bid = int(fair_value) - 1
            our_ask = int(fair_value) + 1

        buy_cap = min(self.ASH_LIMIT - position, self.ASH_MAX_CLIP)
        sell_cap = min(self.ASH_LIMIT + position, self.ASH_MAX_CLIP)

        if buy_cap > 0:
            orders.append(Order(self.ASH, our_bid, buy_cap))
        if sell_cap > 0:
            orders.append(Order(self.ASH, our_ask, -sell_cap))

        return orders