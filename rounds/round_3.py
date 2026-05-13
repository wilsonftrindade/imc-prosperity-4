import json
from typing import Tuple, List, Dict, Optional, Any
import math
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
    HYDROGEL = "HYDROGEL_PACK"
    VELVET = "VELVETFRUIT_EXTRACT"

    POSITION_LIMITS = {
        HYDROGEL: 200,
        VELVET: 200,
        "VEV_4000": 300,
        "VEV_4500": 300,
        "VEV_5000": 300,
        "VEV_5100": 300,
        "VEV_5200": 300,
        "VEV_5300": 300,
        "VEV_5400": 300,
        "VEV_5500": 300,
        "VEV_6000": 300,
        "VEV_6500": 300,
    }

    STRIKES = {
        "VEV_4000": 4000,
        "VEV_4500": 4500,
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
        "VEV_5400": 5400,
        "VEV_5500": 5500,
        "VEV_6000": 6000,
        "VEV_6500": 6500,
    }

    # -------------------- Module switches --------------------
    USE_HYDROGEL = True
    USE_VELVET_PREDICTIVE = True
    USE_ITM_DIRECTIONAL_OPTIONS = True
    USE_DIRECTIONAL_OPTIONS = True

    # Old fixed-IV option module.
    # This was better than adaptive IV, residual options, smile scalping, and passive MM.
    USE_OPTIONS = False

    # Keep hedge off because the main edge is directional.
    USE_HEDGE = False

    # -------------------- TTE --------------------
    # For combined historical backtesting, use 7.0.
    # For final Round 3 submission, change this to 5.0.
    USE_DECAYING_TTE = True
    START_TTE_DAYS = 5.0

    # -------------------- Hydrogel --------------------
    HYDROGEL_ANCHOR = 10000.0
    HYDROGEL_USE_ADAPTIVE_FAIR = True
    HYDROGEL_ALPHA = 0.0015
    HYDROGEL_ADAPTIVE_WEIGHT = 0.10
    HYDROGEL_IMB_COEF = 3.0
    HYDROGEL_EDGE = 18.0
    HYDROGEL_MAX_CLIP = 60

    # -------------------- Velvet predictive crossing strategy --------------------
    VELVET_PRED_SCALE = 3.0
    VELVET_PRED_EDGE = 1.5
    VELVET_PRED_MAX_CLIP = 60
    VELVET_PRED_SOFT_LIMIT = 200

    VELVET_COEF_INTERCEPT = -19.0

    VELVET_COEF_VWAP_DEV = 0.0
    VELVET_COEF_MICRO_DEV = 0.0
    VELVET_COEF_IMB1 = 0.0

    VELVET_COEF_BASIS_4000 = 0.0
    VELVET_COEF_BASIS_4500 = 0.0
    VELVET_COEF_BASIS_5000 = -0.10
    VELVET_COEF_BASIS_5200 = -0.30
    VELVET_COEF_BASIS_5300 = 0.35

    VELVET_PRED_CAP = 12.0

    # -------------------- Deep ITM directional options --------------------
    ITM_DIRECTIONAL_VOUCHERS = ["VEV_4000", "VEV_4500"]

    ITM_OPTION_EDGES = {
        "VEV_4000": 2.0,
        "VEV_4500": 2.0,
    }

    ITM_OPTION_SOFT_LIMIT = 240
    ITM_OPTION_MAX_CLIP = 60

    # Intrinsic fair gave the same result as Black-Scholes and is cleaner.
    ITM_USE_BLACK_SCHOLES_FAIR = False

    # -------------------- Directional mid/near-money options --------------------
    DIRECTIONAL_OPTION_VOUCHERS = ["VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300"]

    DIRECTIONAL_OPTION_EDGES = {
        "VEV_5000": 3.0,
        "VEV_5100": 2.5,
        "VEV_5200": 2.5,
        "VEV_5300": 2.5,
        "VEV_5400": 1.5,
    }

    DIRECTIONAL_OPTION_SPREAD_MULT = 0.60
    DIRECTIONAL_OPTION_SOFT_LIMIT = 180
    DIRECTIONAL_OPTION_MAX_CLIP = 35

    # -------------------- Old fixed-IV options baseline --------------------
    ACTIVE_VOUCHERS = ["VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]

    SIGMAS = {
        "VEV_5000": 0.242,
        "VEV_5100": 0.240,
        "VEV_5200": 0.242,
        "VEV_5300": 0.245,
        "VEV_5400": 0.230,
        "VEV_5500": 0.249,
    }

    OPTION_EDGES = {
        "VEV_5000": 2.0,
        "VEV_5100": 1.5,
        "VEV_5200": 1.5,
        "VEV_5300": 1.5,
        "VEV_5400": 1.0,
        "VEV_5500": 1.0,
    }

    OPTION_SPREAD_MULT = 0.50
    OPTION_SOFT_LIMIT = 180
    OPTION_MAX_CLIP = 35

    HEDGE_BUFFER = 45.0
    HEDGE_MAX_CLIP = 35
    BOOK_DIRECTIONAL_DELTA_COEF = 15.0

    MIN_SIGMA = 0.05
    MAX_SIGMA = 0.80

    def __init__(self):
        self.ewma_mid = {}

    # ---------- Memory ----------

    def load_memory(self, trader_data: str) -> None:
        if not trader_data:
            return

        try:
            data = json.loads(trader_data)
            ewma = data.get("ewma_mid", {})

            if isinstance(ewma, dict):
                self.ewma_mid = {str(k): float(v) for k, v in ewma.items()}

        except Exception:
            pass

    def save_memory(self) -> str:
        try:
            return json.dumps({"ewma_mid": self.ewma_mid}, separators=(",", ":"))
        except Exception:
            return ""

    # ---------- Math helpers ----------

    def clamp(self, x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    def norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_call(self, s: float, k: float, t: float, sigma: float) -> float:
        if s <= 0.0:
            return 0.0

        if t <= 0.0 or sigma <= 0.0:
            return max(0.0, s - k)

        vol = sigma * math.sqrt(t)

        if vol <= 1e-9:
            return max(0.0, s - k)

        d1 = (math.log(s / k) + 0.5 * sigma * sigma * t) / vol
        d2 = d1 - vol

        return s * self.norm_cdf(d1) - k * self.norm_cdf(d2)

    def black_scholes_delta(self, s: float, k: float, t: float, sigma: float) -> float:
        if s <= 0.0:
            return 0.0

        if t <= 0.0 or sigma <= 0.0:
            return 1.0 if s > k else 0.0

        vol = sigma * math.sqrt(t)

        if vol <= 1e-9:
            return 1.0 if s > k else 0.0

        d1 = (math.log(s / k) + 0.5 * sigma * sigma * t) / vol

        return self.norm_cdf(d1)

    def tte_days(self, timestamp: int) -> float:
        if self.USE_DECAYING_TTE:
            day_progress = self.clamp(timestamp / 1_000_000.0, 0.0, 0.9999)
            tte_days = self.START_TTE_DAYS - day_progress
        else:
            tte_days = self.START_TTE_DAYS

        return max(0.05, tte_days)

    def tte_years(self, timestamp: int) -> float:
        return self.tte_days(timestamp) / 365.0

    # ---------- Book helpers ----------

    def best_bid_ask(self, order_depth):
        if order_depth is None or not order_depth.buy_orders or not order_depth.sell_orders:
            return None, None, 0, 0, None

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        bid_vol = order_depth.buy_orders[best_bid]
        ask_vol = -order_depth.sell_orders[best_ask]
        mid = (best_bid + best_ask) / 2.0

        return best_bid, best_ask, bid_vol, ask_vol, mid

    def imbalance(self, bid_vol: int, ask_vol: int) -> float:
        total = bid_vol + ask_vol

        if total <= 0:
            return 0.0

        return (bid_vol - ask_vol) / total

    def microprice(self, best_bid: int, best_ask: int, bid_vol: int, ask_vol: int) -> float:
        total = bid_vol + ask_vol

        if total <= 0:
            return (best_bid + best_ask) / 2.0

        return (best_bid * ask_vol + best_ask * bid_vol) / total

    def visible_vwap_mid3(self, order_depth, fallback_mid: float) -> float:
        if order_depth is None:
            return fallback_mid

        buy_levels = sorted(order_depth.buy_orders.items(), reverse=True)[:3]
        sell_levels = sorted(order_depth.sell_orders.items())[:3]

        bid_value = 0.0
        bid_volume = 0

        for price, volume in buy_levels:
            if volume > 0:
                bid_value += price * volume
                bid_volume += volume

        ask_value = 0.0
        ask_volume = 0

        for price, volume in sell_levels:
            positive_volume = -volume

            if positive_volume > 0:
                ask_value += price * positive_volume
                ask_volume += positive_volume

        if bid_volume <= 0 or ask_volume <= 0:
            return fallback_mid

        bid_vwap = bid_value / bid_volume
        ask_vwap = ask_value / ask_volume

        return (bid_vwap + ask_vwap) / 2.0

    def mid_for_product(self, state, product: str):
        order_depth = state.order_depths.get(product)
        _, _, _, _, mid = self.best_bid_ask(order_depth)
        return mid

    def get_ewma_before_update(self, key: str, mid: float, initial=None) -> float:
        if key not in self.ewma_mid:
            self.ewma_mid[key] = mid if initial is None else initial

        return self.ewma_mid[key]

    def update_ewma(self, key: str, mid: float, alpha: float, initial=None) -> float:
        previous = self.get_ewma_before_update(key, mid, initial)
        updated = previous + alpha * (mid - previous)
        self.ewma_mid[key] = updated

        return updated

    def sigma_for_product(self, product: str) -> float:
        return self.clamp(self.SIGMAS[product], self.MIN_SIGMA, self.MAX_SIGMA)

    # ---------- Execution helpers ----------

    def take_asks(
        self,
        product: str,
        order_depth,
        max_price: float,
        position: int,
        soft_limit: int,
        max_clip: int,
    ):
        orders = []
        remaining_clip = max_clip

        for ask_price in sorted(order_depth.sell_orders.keys()):
            if ask_price > max_price or remaining_clip <= 0:
                break

            available = -order_depth.sell_orders[ask_price]
            capacity = soft_limit - position
            qty = min(available, capacity, remaining_clip)

            if qty <= 0:
                break

            orders.append(Order(product, ask_price, qty))
            position += qty
            remaining_clip -= qty

        return orders, position

    def hit_bids(
        self,
        product: str,
        order_depth,
        min_price: float,
        position: int,
        soft_limit: int,
        max_clip: int,
    ):
        orders = []
        remaining_clip = max_clip

        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if bid_price < min_price or remaining_clip <= 0:
                break

            available = order_depth.buy_orders[bid_price]
            capacity = soft_limit + position
            qty = min(available, capacity, remaining_clip)

            if qty <= 0:
                break

            orders.append(Order(product, bid_price, -qty))
            position -= qty
            remaining_clip -= qty

        return orders, position

    # ---------- Hydrogel ----------

    def hydrogel_fair(self, order_depth):
        best_bid, best_ask, bid_vol, ask_vol, mid = self.best_bid_ask(order_depth)

        if mid is None:
            return None

        imb = self.imbalance(bid_vol, ask_vol)
        ewma = self.get_ewma_before_update(
            self.HYDROGEL,
            mid,
            initial=self.HYDROGEL_ANCHOR,
        )

        if self.HYDROGEL_USE_ADAPTIVE_FAIR:
            anchor_fair = (
                (1.0 - self.HYDROGEL_ADAPTIVE_WEIGHT) * self.HYDROGEL_ANCHOR
                + self.HYDROGEL_ADAPTIVE_WEIGHT * ewma
            )
        else:
            anchor_fair = self.HYDROGEL_ANCHOR

        fair = anchor_fair + self.HYDROGEL_IMB_COEF * imb

        self.update_ewma(
            self.HYDROGEL,
            mid,
            self.HYDROGEL_ALPHA,
            initial=self.HYDROGEL_ANCHOR,
        )

        return fair

    def trade_hydrogel(self, state, positions):
        product = self.HYDROGEL
        order_depth = state.order_depths.get(product)

        if order_depth is None:
            return []

        fair = self.hydrogel_fair(order_depth)

        if fair is None:
            return []

        position = positions.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        orders = []

        buy_orders, position = self.take_asks(
            product,
            order_depth,
            fair - self.HYDROGEL_EDGE,
            position,
            limit,
            self.HYDROGEL_MAX_CLIP,
        )
        orders.extend(buy_orders)

        sell_orders, position = self.hit_bids(
            product,
            order_depth,
            fair + self.HYDROGEL_EDGE,
            position,
            limit,
            self.HYDROGEL_MAX_CLIP,
        )
        orders.extend(sell_orders)

        positions[product] = position

        return orders

    # ---------- Velvet predictive strategy ----------

    def velvet_predictive_fair(self, state):
        order_depth = state.order_depths.get(self.VELVET)
        best_bid, best_ask, bid_vol, ask_vol, mid = self.best_bid_ask(order_depth)

        if mid is None:
            return None

        imb1 = self.imbalance(bid_vol, ask_vol)
        micro = self.microprice(best_bid, best_ask, bid_vol, ask_vol)
        micro_dev = micro - mid

        vwap_mid3 = self.visible_vwap_mid3(order_depth, mid)
        vwap_dev = vwap_mid3 - mid

        v4000_mid = self.mid_for_product(state, "VEV_4000")
        v4500_mid = self.mid_for_product(state, "VEV_4500")
        v5000_mid = self.mid_for_product(state, "VEV_5000")
        v5200_mid = self.mid_for_product(state, "VEV_5200")
        v5300_mid = self.mid_for_product(state, "VEV_5300")

        if (
            v4000_mid is None
            or v4500_mid is None
            or v5000_mid is None
            or v5200_mid is None
            or v5300_mid is None
        ):
            return mid

        basis_4000 = v4000_mid + 4000 - mid
        basis_4500 = v4500_mid + 4500 - mid
        basis_5000 = v5000_mid + 5000 - mid
        basis_5200 = v5200_mid + 5200 - mid
        basis_5300 = v5300_mid + 5300 - mid

        predicted_move = (
            self.VELVET_COEF_INTERCEPT
            + self.VELVET_COEF_VWAP_DEV * vwap_dev
            + self.VELVET_COEF_MICRO_DEV * micro_dev
            + self.VELVET_COEF_IMB1 * imb1
            + self.VELVET_COEF_BASIS_4000 * basis_4000
            + self.VELVET_COEF_BASIS_4500 * basis_4500
            + self.VELVET_COEF_BASIS_5000 * basis_5000
            + self.VELVET_COEF_BASIS_5200 * basis_5200
            + self.VELVET_COEF_BASIS_5300 * basis_5300
        )

        predicted_move *= self.VELVET_PRED_SCALE
        predicted_move = self.clamp(
            predicted_move,
            -self.VELVET_PRED_CAP,
            self.VELVET_PRED_CAP,
        )

        return mid + predicted_move

    def trade_velvet_predictive_with_fair(self, state, positions, fair: float):
        product = self.VELVET
        order_depth = state.order_depths.get(product)

        if order_depth is None:
            return []

        position = positions.get(product, 0)
        soft_limit = min(self.VELVET_PRED_SOFT_LIMIT, self.POSITION_LIMITS[product])
        orders = []

        buy_orders, position = self.take_asks(
            product,
            order_depth,
            fair - self.VELVET_PRED_EDGE,
            position,
            soft_limit,
            self.VELVET_PRED_MAX_CLIP,
        )
        orders.extend(buy_orders)

        sell_orders, position = self.hit_bids(
            product,
            order_depth,
            fair + self.VELVET_PRED_EDGE,
            position,
            soft_limit,
            self.VELVET_PRED_MAX_CLIP,
        )
        orders.extend(sell_orders)

        positions[product] = position

        return orders

    # ---------- ITM directional options ----------

    def trade_itm_directional_vouchers(self, state, positions, predicted_velvet_fair: float):
        orders = []

        for product in self.ITM_DIRECTIONAL_VOUCHERS:
            order_depth = state.order_depths.get(product)

            if order_depth is None:
                continue

            best_bid, best_ask, bid_vol, ask_vol, mid = self.best_bid_ask(order_depth)

            if mid is None:
                continue

            strike = self.STRIKES[product]
            fair = max(0.0, predicted_velvet_fair - strike)

            spread = best_ask - best_bid
            edge = max(self.ITM_OPTION_EDGES[product], 0.50 * spread)

            position = positions.get(product, 0)
            soft_limit = min(self.ITM_OPTION_SOFT_LIMIT, self.POSITION_LIMITS[product])

            buy_orders, position = self.take_asks(
                product,
                order_depth,
                fair - edge,
                position,
                soft_limit,
                self.ITM_OPTION_MAX_CLIP,
            )
            orders.extend(buy_orders)

            sell_orders, position = self.hit_bids(
                product,
                order_depth,
                fair + edge,
                position,
                soft_limit,
                self.ITM_OPTION_MAX_CLIP,
            )
            orders.extend(sell_orders)

            positions[product] = position

        return orders

    # ---------- Directional options ----------

    def trade_directional_vouchers(self, state, positions, predicted_velvet_fair: float):
        t = self.tte_years(state.timestamp)
        orders = []

        for product in self.DIRECTIONAL_OPTION_VOUCHERS:
            order_depth = state.order_depths.get(product)

            if order_depth is None:
                continue

            best_bid, best_ask, bid_vol, ask_vol, mid = self.best_bid_ask(order_depth)

            if mid is None:
                continue

            strike = self.STRIKES[product]
            sigma = self.sigma_for_product(product)

            fair = self.black_scholes_call(
                predicted_velvet_fair,
                strike,
                t,
                sigma,
            )

            spread = best_ask - best_bid
            edge = max(
                self.DIRECTIONAL_OPTION_EDGES[product],
                self.DIRECTIONAL_OPTION_SPREAD_MULT * spread,
            )

            position = positions.get(product, 0)
            soft_limit = min(
                self.DIRECTIONAL_OPTION_SOFT_LIMIT,
                self.POSITION_LIMITS[product],
            )

            buy_orders, position = self.take_asks(
                product,
                order_depth,
                fair - edge,
                position,
                soft_limit,
                self.DIRECTIONAL_OPTION_MAX_CLIP,
            )
            orders.extend(buy_orders)

            sell_orders, position = self.hit_bids(
                product,
                order_depth,
                fair + edge,
                position,
                soft_limit,
                self.DIRECTIONAL_OPTION_MAX_CLIP,
            )
            orders.extend(sell_orders)

            positions[product] = position

        return orders

    # ---------- Old fixed-IV options ----------

    def velvet_spot_fair_and_signal(self, state):
        order_depth = state.order_depths.get(self.VELVET)

        if order_depth is None:
            return None, 0.0

        best_bid, best_ask, bid_vol, ask_vol, mid = self.best_bid_ask(order_depth)

        if mid is None:
            return None, 0.0

        imb = self.imbalance(bid_vol, ask_vol)
        micro = self.microprice(best_bid, best_ask, bid_vol, ask_vol)

        spot_fair = 0.75 * mid + 0.25 * micro + 0.35 * imb

        return spot_fair, imb

    def trade_vouchers(self, state, positions, velvet_spot_fair: float):
        t = self.tte_years(state.timestamp)
        orders = []

        for product in self.ACTIVE_VOUCHERS:
            order_depth = state.order_depths.get(product)

            if order_depth is None:
                continue

            best_bid, best_ask, bid_vol, ask_vol, mid = self.best_bid_ask(order_depth)

            if mid is None:
                continue

            strike = self.STRIKES[product]
            sigma = self.sigma_for_product(product)

            fair = self.black_scholes_call(
                velvet_spot_fair,
                strike,
                t,
                sigma,
            )

            spread = best_ask - best_bid
            edge = max(self.OPTION_EDGES[product], self.OPTION_SPREAD_MULT * spread)

            position = positions.get(product, 0)
            soft_limit = min(self.OPTION_SOFT_LIMIT, self.POSITION_LIMITS[product])

            buy_orders, position = self.take_asks(
                product,
                order_depth,
                fair - edge,
                position,
                soft_limit,
                self.OPTION_MAX_CLIP,
            )
            orders.extend(buy_orders)

            sell_orders, position = self.hit_bids(
                product,
                order_depth,
                fair + edge,
                position,
                soft_limit,
                self.OPTION_MAX_CLIP,
            )
            orders.extend(sell_orders)

            positions[product] = position

        return orders

    # ---------- Main ----------

    def run(self, state):
        self.load_memory(getattr(state, "traderData", ""))

        result = {}
        positions = {
            product: state.position.get(product, 0)
            for product in self.POSITION_LIMITS
        }

        predicted_velvet_fair = None

        if self.USE_HYDROGEL:
            hydro_orders = self.trade_hydrogel(state, positions)

            if hydro_orders:
                result[self.HYDROGEL] = hydro_orders

        if self.USE_VELVET_PREDICTIVE:
            predicted_velvet_fair = self.velvet_predictive_fair(state)

            if predicted_velvet_fair is not None:
                velvet_orders = self.trade_velvet_predictive_with_fair(
                    state,
                    positions,
                    predicted_velvet_fair,
                )

                if velvet_orders:
                    result.setdefault(self.VELVET, []).extend(velvet_orders)

        if self.USE_ITM_DIRECTIONAL_OPTIONS:
            if predicted_velvet_fair is None:
                predicted_velvet_fair = self.velvet_predictive_fair(state)

            if predicted_velvet_fair is not None:
                itm_orders = self.trade_itm_directional_vouchers(
                    state,
                    positions,
                    predicted_velvet_fair,
                )

                for order in itm_orders:
                    result.setdefault(order.symbol, []).append(order)

        if self.USE_DIRECTIONAL_OPTIONS:
            if predicted_velvet_fair is None:
                predicted_velvet_fair = self.velvet_predictive_fair(state)

            if predicted_velvet_fair is not None:
                directional_orders = self.trade_directional_vouchers(
                    state,
                    positions,
                    predicted_velvet_fair,
                )

                for order in directional_orders:
                    result.setdefault(order.symbol, []).append(order)

        velvet_spot_fair, velvet_imb = self.velvet_spot_fair_and_signal(state)

        if velvet_spot_fair is not None:
            if self.USE_OPTIONS:
                voucher_orders = self.trade_vouchers(
                    state,
                    positions,
                    velvet_spot_fair,
                )

                for order in voucher_orders:
                    result.setdefault(order.symbol, []).append(order)

        conversions = 0
        traderData = self.save_memory()

        try:
            logger.flush(state, result, conversions, traderData)
        except Exception:
            pass

        return result, conversions, traderData