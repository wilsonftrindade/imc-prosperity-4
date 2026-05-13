import csv
import io
import json
import jsonpickle
import collections
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: Dict[Symbol, List[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([self.compress_state(state, ""), self.compress_orders(orders), conversions, "", ""]))
        max_item_length = max(0, (self.max_log_length - base_length) // 3)
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> List[Any]:
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

    def compress_listings(self, listings: Dict[Symbol, Listing]) -> List[List[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: Dict[Symbol, OrderDepth]) -> Dict[Symbol, List[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: Dict[Symbol, List[Trade]]) -> List[List[Any]]:
        out = []
        for arr in trades.values():
            for t in arr:
                out.append([t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp])
        return out

    def compress_observations(self, observations: Observation) -> List[Any]:
        conv = {}
        for product, o in observations.conversionObservations.items():
            conv[product] = [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff,
                             o.importTariff, o.sugarPrice, o.sunlightIndex]
        return [observations.plainValueObservations, conv]

    def compress_orders(self, orders: Dict[Symbol, List[Order]]) -> List[List[Any]]:
        out = []
        for arr in orders.values():
            for o in arr:
                out.append([o.symbol, o.price, o.quantity])
        return out

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if max_length <= 0:
            return ""
        lo, hi, out = 0, min(len(value), max_length), ""
        while lo <= hi:
            mid = (lo + hi) // 2
            cand = value[:mid] + ("..." if mid < len(value) else "")
            if len(json.dumps(cand)) <= max_length:
                out = cand
                lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()


@dataclass(frozen=True)
class PairCfg:
    a: str
    b: str
    alpha: float
    beta: float
    correlation: float
    offline_half_life: float
    offline_p_value: float
    regime: str


@dataclass(frozen=True)
class BasketCfg:
    anchor: str
    peers: Tuple[str, ...]
    beta: float
    intercept: float
    quality: float
    leader: Optional[str] = None
    leader_window: int = 0
    leader_weight: float = 0.0


@dataclass(frozen=True)
class RollingCfg:
    window: int
    min_history: int
    entry_z: float
    exit_z: float
    stop_z: float
    time_stop: int
    base_qty: int
    max_qty: int
    size_step: float


@dataclass
class ActiveRollingState:
    direction: int
    entry_tick: int


@dataclass(frozen=True)
class InformedFlowCfg:
    direction: int          # +1 follow aggressive buy; -1 fade it
    hold_ticks: int         # exit after this many 100ms ticks
    qty: int
    burst_min: int          # min same-side aggressors in window to trigger
    burst_window_ts: int    # in raw timestamp units; 0 = single-trade trigger


@dataclass
class ActiveInformedFlow:
    direction: int
    entry_timestamp: int


@dataclass(frozen=True)
class SignalSnapshot:
    kind: str
    key: str
    raw_z: float
    entry_z: float
    quality: float
    spread: float
    activity: float


@dataclass
class ActivePairState:
    direction: int
    entry_tick: int
    entry_spread: float
    flattening: bool = False


PAIR_SCREEN_DATA = """left_product,right_product,correlation,alpha,beta,adf_pvalue,half_life,label
SNACKPACK_STRAWBERRY,UV_VISOR_AMBER,-0.893629,13285.06123846849,-0.3259039094768698,0.0002165531897455,502.5781549686296,fast_mean_reverting
PANEL_2X4,ROBOT_DISHES,0.790208,2345.4267269987267,0.8903639329938219,0.000242142190669,480.4693827496973,fast_mean_reverting
PEBBLES_S,ROBOT_DISHES,-0.828654,21359.933275317453,-1.2404857170125605,0.0002752724276089,411.30360806802423,fast_mean_reverting
PEBBLES_XL,ROBOT_DISHES,0.802274,-12426.35087824657,2.560504481139162,0.0002996545307143,467.3766382456695,fast_mean_reverting
GALAXY_SOUNDS_DARK_MATTER,UV_VISOR_YELLOW,0.768073,6144.544949131663,0.3725422304191236,0.0004425638270857,534.096206968172,fast_mean_reverting
GALAXY_SOUNDS_BLACK_HOLES,ROBOT_DISHES,0.839101,-3007.586156710715,1.4447996878241518,0.0004557843902418,439.00291617970066,fast_mean_reverting
PANEL_2X4,PEBBLES_XL,0.876256,7173.995980017387,0.3093530961346319,0.0006067892419123,582.0030200619444,fast_mean_reverting
OXYGEN_SHAKE_GARLIC,ROBOT_DISHES,0.798098,-1768.325081483339,1.3668930338923573,0.0008098902790577,537.0154986565879,fast_mean_reverting
OXYGEN_SHAKE_MORNING_BREATH,PEBBLES_M,-0.857646,18354.61846430046,-0.8139888108533703,0.0009825735606155,609.2803572486126,fast_mean_reverting
SLEEP_POD_POLYESTER,SNACKPACK_STRAWBERRY,0.875129,-13351.676309203518,2.3529614685363267,0.0010301037139926,617.2171172379217,fast_mean_reverting
ROBOT_DISHES,UV_VISOR_AMBER,-0.81641,13624.870560364394,-0.4558511280516355,0.0013780164454214,426.55922043109115,fast_mean_reverting
SNACKPACK_STRAWBERRY,TRANSLATOR_VOID_BLUE,0.803797,5228.356743903303,0.5045090695501693,0.0016048263343346,671.7017124721157,fast_mean_reverting
MICROCHIP_TRIANGLE,UV_VISOR_RED,-0.852355,23057.747356190503,-1.2086234693257072,0.0017155660371818,673.3708525642954,fast_mean_reverting
PEBBLES_XS,UV_VISOR_AMBER,0.958298,-3619.460043623333,1.3933927013805667,0.0022297106990935,678.7078308849764,fast_mean_reverting
PEBBLES_M,ROBOT_IRONING,-0.816566,16601.803371835897,-0.728438660408668,0.0031539533702148,727.066137324261,fast_mean_reverting
MICROCHIP_OVAL,ROBOT_DISHES,-0.828457,31319.303012341028,-2.3097401635552863,0.0036808186170891,539.3721957614039,fast_mean_reverting
MICROCHIP_TRIANGLE,ROBOT_DISHES,-0.793864,21593.45157743251,-1.18852926993732,0.0043051549663865,547.4112995342504,fast_mean_reverting
MICROCHIP_RECTANGLE,MICROCHIP_SQUARE,-0.882298,13660.824397335376,-0.362521242657753,0.0044526840158107,755.545073451452,fast_mean_reverting
SLEEP_POD_NYLON,UV_VISOR_RED,0.75711,2386.0618557048783,0.6553573451114423,0.0045970059038149,914.8150491251688,fast_mean_reverting
PANEL_2X4,PEBBLES_S,-0.829305,16840.92809350258,-0.6241975412113429,0.0047726492035759,780.9422043720015,fast_mean_reverting
OXYGEN_SHAKE_GARLIC,PEBBLES_S,-0.884036,20959.966049755116,-1.0114157498182523,0.005294512781663,764.1258966191232,fast_mean_reverting
MICROCHIP_CIRCLE,OXYGEN_SHAKE_CHOCOLATE,0.829621,1683.5693211615917,0.788051816612742,0.0053335540924046,752.19777603246,fast_mean_reverting
PEBBLES_XS,ROBOT_DISHES,-0.77922,27733.51013694493,-2.0291706313082916,0.0060224275638411,668.2671634017476,fast_mean_reverting
MICROCHIP_SQUARE,SLEEP_POD_SUEDE,0.918489,-7695.210416328766,1.8679629167722316,0.0062472053376367,806.6248846216484,fast_mean_reverting
SNACKPACK_STRAWBERRY,UV_VISOR_MAGENTA,0.760847,5696.809750737619,0.4508542225676633,0.007064712415577,844.9618838326998,fast_mean_reverting
TRANSLATOR_VOID_BLUE,UV_VISOR_MAGENTA,0.821676,2238.7021039112897,0.7757413503829831,0.0074891338751925,807.8658143015359,fast_mean_reverting
GALAXY_SOUNDS_SOLAR_WINDS,PEBBLES_M,0.782248,4121.541314747333,0.6154002725158071,0.0078612136266029,812.0774281229822,fast_mean_reverting
ROBOT_LAUNDRY,UV_VISOR_RED,-0.800848,19083.885650636596,-0.8371036961893811,0.0080159192883055,935.721849854634,fast_mean_reverting
SLEEP_POD_POLYESTER,UV_VISOR_AMBER,-0.940922,19140.148570543537,-0.922632440615189,0.0080628753933435,818.224604259228,fast_mean_reverting
MICROCHIP_RECTANGLE,TRANSLATOR_ASTRO_BLACK,0.815988,-3026.985329105004,1.2529728363585548,0.0083988449281131,842.4975720548439,fast_mean_reverting
PEBBLES_M,ROBOT_MOPPING,0.776547,2534.913483394889,0.6962325441398453,0.0087994950650089,878.736235401092,fast_mean_reverting
PEBBLES_XS,SNACKPACK_STRAWBERRY,-0.850454,43707.70175982621,-3.390715369218884,0.0091256023268073,829.4050849926995,fast_mean_reverting
PEBBLES_S,UV_VISOR_RED,-0.805599,21568.90381114824,-1.142204803897788,0.0091492151487078,883.097558107695,fast_mean_reverting
GALAXY_SOUNDS_BLACK_HOLES,MICROCHIP_TRIANGLE,-0.841853,20845.24343900853,-0.9682007751898304,0.0109057935904845,992.956295545504,fast_mean_reverting
MICROCHIP_TRIANGLE,SLEEP_POD_NYLON,-0.791145,22175.339095049058,-1.2960082566847122,0.0109809239282904,941.052257659798,fast_mean_reverting
PEBBLES_M,ROBOT_VACUUMING,-0.752618,19128.69253084436,-0.9671284164743984,0.0114491281278351,905.596679129533,fast_mean_reverting
MICROCHIP_TRIANGLE,PEBBLES_S,0.833615,2239.4651761449923,0.8337022500901992,0.0118797039121362,857.0757318433724,fast_mean_reverting
PEBBLES_XL,TRANSLATOR_VOID_BLUE,0.809369,-13728.647088854868,2.482298611824684,0.0132816095175714,927.44363429753,fast_mean_reverting
GALAXY_SOUNDS_BLACK_HOLES,PEBBLES_S,-0.885004,20559.43341621741,-1.0179353114002825,0.0137994433074148,835.9745282186099,fast_mean_reverting
MICROCHIP_TRIANGLE,ROBOT_LAUNDRY,0.856255,-1723.4146143549478,1.1615680035980394,0.0140689851502154,848.4560658993802,fast_mean_reverting
ROBOT_IRONING,SNACKPACK_PISTACHIO,0.775125,-21566.653828748946,3.187523337687788,0.01468480996743,853.671312688186,fast_mean_reverting
GALAXY_SOUNDS_SOLAR_WINDS,PANEL_1X4,-0.828697,15490.139860945575,-0.5376485821593381,0.0160956571238623,943.2210237334716,fast_mean_reverting
SLEEP_POD_POLYESTER,UV_VISOR_MAGENTA,0.858202,-3352.8405792023987,1.3673222373684086,0.0161794563507797,949.4256315413146,fast_mean_reverting
SLEEP_POD_SUEDE,UV_VISOR_MAGENTA,0.847926,-2422.515231687845,1.2437178940782074,0.0169193931562464,973.330830278142,fast_mean_reverting
PANEL_2X4,PEBBLES_XS,-0.859668,14019.617078963149,-0.3719619296037258,0.0200546153567432,944.3967083053273,fast_mean_reverting
OXYGEN_SHAKE_GARLIC,SNACKPACK_PISTACHIO,-0.756487,48451.20342109561,-3.8464789412051057,0.0237361080531438,986.8815411186788,fast_mean_reverting
MICROCHIP_RECTANGLE,OXYGEN_SHAKE_MORNING_BREATH,0.755915,24.046429083166004,0.8707998143820985,0.0143307127669416,1127.2453897187586,stationary_but_slow
PEBBLES_S,ROBOT_LAUNDRY,0.78089,-1472.0997147642356,1.0592190634226188,0.0151531295037486,1048.6165466839652,stationary_but_slow
OXYGEN_SHAKE_MORNING_BREATH,ROBOT_MOPPING,-0.817304,17720.35933644534,-0.6954736656105746,0.0168283012732562,1079.7794767463038,stationary_but_slow
MICROCHIP_OVAL,MICROCHIP_TRIANGLE,0.870459,-7521.843708079233,1.6209796083664456,0.0177374123891,1059.2486715013958,stationary_but_slow
PANEL_2X2,UV_VISOR_RED,-0.817436,19960.0817081208,-0.9385526287063388,0.0203663911168595,1021.1106440801216,stationary_but_slow
OXYGEN_SHAKE_MORNING_BREATH,ROBOT_VACUUMING,0.791763,1148.651259143784,0.9656396425611512,0.021268758505644,1112.2099505330334,stationary_but_slow
PEBBLES_XL,TRANSLATOR_SPACE_GRAY,-0.75896,38523.24654105285,-2.6821374455865024,0.0217809682474352,1117.7555368236538,stationary_but_slow
UV_VISOR_AMBER,UV_VISOR_MAGENTA,-0.867276,23570.11680733531,-1.4091713819950074,0.0226936720317213,1058.038434188731,stationary_but_slow
OXYGEN_SHAKE_GARLIC,PEBBLES_XL,0.853184,5870.375478501707,0.4578445726070003,0.0237803238695503,1036.601032654876,stationary_but_slow
PANEL_2X2,ROBOT_LAUNDRY,0.843826,471.9769963960098,0.9268901878111656,0.0240091353694437,1044.0618148286926,stationary_but_slow
ROBOT_LAUNDRY,ROBOT_VACUUMING,0.787417,1538.4954985670029,0.9037273734233928,0.0240698201509832,1131.909427459958,stationary_but_slow
SLEEP_POD_SUEDE,TRANSLATOR_ASTRO_BLACK,-0.823154,25593.590550480396,-1.5126093344274123,0.0251875415087963,1060.5958832922008,stationary_but_slow
MICROCHIP_SQUARE,OXYGEN_SHAKE_MORNING_BREATH,-0.754469,34748.56745791274,-2.115286019299589,0.0253462866164191,1553.8805759529075,stationary_but_slow
OXYGEN_SHAKE_GARLIC,PANEL_2X4,0.842836,-2506.832769169996,1.281135791703384,0.0265653756537872,1060.767652365396,stationary_but_slow
OXYGEN_SHAKE_MORNING_BREATH,ROBOT_IRONING,0.800798,4100.714847382321,0.6780084883320383,0.0268727810245632,1195.6758219979463,stationary_but_slow
PEBBLES_XS,SNACKPACK_PISTACHIO,0.767183,-48916.956308109904,5.9311838493810445,0.027895568036279,1024.0714466346394,stationary_but_slow
PANEL_1X4,ROBOT_MOPPING,-0.875148,19958.703124672793,-0.9514342009477488,0.0288599065214486,1101.727127621358,stationary_but_slow
MICROCHIP_RECTANGLE,UV_VISOR_MAGENTA,-0.781963,19382.365013699673,-0.9584344992336632,0.0295664689753457,1079.3828871514224,stationary_but_slow
GALAXY_SOUNDS_SOLAR_WINDS,OXYGEN_SHAKE_MORNING_BREATH,-0.76742,16798.9859395337,-0.6361153589969034,0.0297400693314536,1091.0372321753448,stationary_but_slow
MICROCHIP_SQUARE,SNACKPACK_STRAWBERRY,0.802732,-29670.756911924393,4.041009364629741,0.0310094791592946,1098.337027187517,stationary_but_slow
PANEL_1X4,PEBBLES_M,-0.79981,19351.221388504244,-0.9698338618733572,0.0311605288170276,1123.0161684890256,stationary_but_slow
MICROCHIP_RECTANGLE,SLEEP_POD_SUEDE,-0.814947,16493.98579108974,-0.6809915003565216,0.0311851881444802,1131.034985681792,stationary_but_slow
MICROCHIP_OVAL,PEBBLES_S,0.878076,-6427.809312725031,1.6353363916692314,0.032020472842055,1074.286604228122,stationary_but_slow
PANEL_2X4,ROBOT_VACUUMING,-0.757151,19398.081103664023,-0.887193961383593,0.033297354418118,1156.5896099496567,stationary_but_slow
MICROCHIP_SQUARE,TRANSLATOR_ASTRO_BLACK,-0.817331,42261.76208747132,-3.054485279287616,0.0333256751184965,1176.559151587062,stationary_but_slow
SLEEP_POD_COTTON,SLEEP_POD_POLYESTER,0.875237,2116.8181347846366,0.7947930737083896,0.033497243266141,1131.9812023580964,stationary_but_slow
PANEL_2X4,SNACKPACK_STRAWBERRY,0.756647,-2709.6806113281564,1.305273616258733,0.0340745089583482,1063.411016415136,stationary_but_slow
MICROCHIP_TRIANGLE,OXYGEN_SHAKE_CHOCOLATE,-0.754624,20407.26045935866,-1.1217960619206877,0.0343090173517372,1111.5702516383828,stationary_but_slow
MICROCHIP_OVAL,SNACKPACK_PISTACHIO,0.750898,-50839.3820099192,6.215243346933965,0.0345475154130489,1145.514929592117,stationary_but_slow
GALAXY_SOUNDS_BLACK_HOLES,OXYGEN_SHAKE_GARLIC,0.885327,852.3465478141952,0.890059212184807,0.0351851285509408,1137.0667913506911,stationary_but_slow
TRANSLATOR_VOID_BLUE,UV_VISOR_AMBER,-0.829785,14673.144827403625,-0.4821425612832762,0.0362759725521592,1120.1288050293174,stationary_but_slow
MICROCHIP_OVAL,ROBOT_VACUUMING,0.870972,-14968.978082008798,2.5252692272416315,0.036778476879886,1154.6601645741134,stationary_but_slow
PEBBLES_XS,ROBOT_VACUUMING,0.851941,-13744.59507458243,2.307161791793991,0.0375772482976403,1163.5262942124173,stationary_but_slow
PEBBLES_XS,UV_VISOR_MAGENTA,-0.845636,29604.338868347997,-1.9978503290572784,0.0387696773554007,1157.733151253481,stationary_but_slow
OXYGEN_SHAKE_CHOCOLATE,SLEEP_POD_NYLON,0.750732,1584.802577958857,0.8272816116293975,0.0399766869618882,1062.5888762066609,stationary_but_slow
PEBBLES_XS,TRANSLATOR_VOID_BLUE,-0.83159,30001.353724114237,-2.0810009545245824,0.0404947995933274,1207.5415812510505,stationary_but_slow
MICROCHIP_RECTANGLE,PEBBLES_XS,0.843043,5493.891579932551,0.4373673631830627,0.0412901098646154,1120.1921940343486,stationary_but_slow
PEBBLES_S,ROBOT_IRONING,0.796317,1443.6901181619387,0.8606109455736313,0.0421911102441713,1148.8075257261537,stationary_but_slow
SLEEP_POD_SUEDE,TRANSLATOR_VOID_BLUE,0.818461,-2410.1959869206567,1.2715859042322224,0.0428873078838206,1180.3828011665937,stationary_but_slow
OXYGEN_SHAKE_MORNING_BREATH,PEBBLES_XS,0.774346,7418.2515819175005,0.3487275342828629,0.0451623089275782,1502.7410020783316,stationary_but_slow
OXYGEN_SHAKE_GARLIC,TRANSLATOR_SPACE_GRAY,-0.773219,25756.179079619273,-1.4663574201712055,0.0460530186395646,1379.4739061701675,stationary_but_slow
SLEEP_POD_SUEDE,SNACKPACK_STRAWBERRY,0.770528,-9023.033764607617,1.9072756978029923,0.0463527086332553,1222.9739368549183,stationary_but_slow
PEBBLES_S,UV_VISOR_AMBER,0.813346,3553.6540300433653,0.6798419116873918,0.0478069345422935,1273.6117917058766,stationary_but_slow
"""


def load_screened_pairs(
    max_pvalue: float = 1.0,
    max_halflife: float = float("inf"),
    label_filter: Optional[Tuple[str, ...]] = None,
    excluded_products: Optional[Tuple[str, ...]] = None,
) -> List[PairCfg]:
    pairs: List[PairCfg] = []
    reader = csv.DictReader(io.StringIO(PAIR_SCREEN_DATA.strip()))
    for row in reader:
        if float(row["adf_pvalue"]) > max_pvalue:
            continue
        if float(row["half_life"]) > max_halflife:
            continue
        if label_filter is not None and row["label"] not in label_filter:
            continue
        if excluded_products is not None and (
            row["left_product"] in excluded_products or row["right_product"] in excluded_products
        ):
            continue
        pairs.append(
            PairCfg(
                row["left_product"],
                row["right_product"],
                float(row["alpha"]),
                float(row["beta"]),
                float(row["correlation"]),
                float(row["half_life"]),
                float(row["adf_pvalue"]),
                row["label"],
            )
        )
    return pairs


FAST_PAIR_LABELS: Tuple[str, ...] = ("fast_mean_reverting",)
PAIR_BLACKLIST_PRODUCTS: Tuple[str, ...] = (
    "PANEL_1X4",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "ROBOT_MOPPING",
    "OXYGEN_SHAKE_GARLIC",
)
DISABLED_PRODUCTS: Tuple[str, ...] = PAIR_BLACKLIST_PRODUCTS + (
    "SLEEP_POD_LAMB_WOOL",
    "TRANSLATOR_GRAPHITE_MIST",
)


class Trader:
    DEFAULT_LIMIT = 50
    POSITION_LIMITS: Dict[str, int] = {}

    PAIRS: List[PairCfg] = load_screened_pairs(
        label_filter=FAST_PAIR_LABELS,
        excluded_products=PAIR_BLACKLIST_PRODUCTS,
    )

    BASKETS: List[BasketCfg] = []

    LOOKBACK = 2500
    MIN_HISTORY = 350
    ENTRY_Z = 2.40
    EXIT_Z = 0.85
    STOP_Z = 4.80
    TIME_STOP_STEPS = 1500

    FAST_ENTRY_Z = 2.00
    FAST_EXIT_Z = 0.55
    FAST_STOP_Z = 4.40
    FAST_BASE_QTY = 7
    FAST_MAX_PAIR_QTY = 18
    FAST_HALF_LIFE_MULT = 2.20

    STABLE_ENTRY_Z = 2.60
    STABLE_EXIT_Z = 0.85
    STABLE_STOP_Z = 5.00
    STABLE_BASE_QTY = 4
    STABLE_MAX_PAIR_QTY = 12
    STABLE_HALF_LIFE_MULT = 1.80
    MAX_ACTIVE_PAIRS = 5

    BASE_BASKET_QTY = 4
    MAX_BASKET_QTY = 12
    WALK_LEVELS = 1
    MIN_ENTRY_FILL_FRACTION = 0.80
    FLATTEN_WALK_LEVELS = 2
    MID_HISTORY = 40
    RECENT_MOVE_WINDOW = 24
    ENABLE_SNACKPACK_ACTIVITY_FILTER = False
    SNACKPACK_MIN_ACTIVITY = 0.030
    SNACKPACK_ACTIVITY_BYPASS_Z = 3.35
    ENABLE_SNACKPACK_PROFIT_HOLD = False
    MIN_PROFIT_EXIT_SPREAD = 0.00035
    FORCE_EXIT_Z = 0.35

    MAKER_PRODUCTS: Tuple[str, ...] = ()
    MAKER_POSITION_LIMIT = 4
    MAKER_ORDER_SIZE = 2
    MAKER_MIN_SPREAD = 2
    MAKER_IMB_SHIFT = 1.4
    MAKER_INV_SHIFT = 0.35
    MAKER_SIGNAL_THRESHOLD = 0.10

    INSIDER_TRAP_GROUPS: Tuple[str, ...] = ("PEBBLES", "MICROCHIP")
    INSIDER_POSITION_LIMIT = 10
    INSIDER_SYNC_THRESHOLD = 15

    # Per-asset rolling-mean reversion. Each product is opted in via
    # ROLLING_ENABLED_PRODUCTS. Configs for the other candidates remain in place
    # so they can be A/B-tested individually without re-coding.
    ROLLING_ENABLED_PRODUCTS: frozenset = frozenset({"ROBOT_DISHES"})
    ROLLING_CFG: Dict[str, RollingCfg] = {
        # ROBOT_DISHES: empirical half-life ~32 ticks, much faster than peers.
        "ROBOT_DISHES": RollingCfg(
            window=80, min_history=80, entry_z=1.8, exit_z=0.5, stop_z=4.0,
            time_stop=150, base_qty=8, max_qty=12, size_step=4.0,
        ),
        # Default 200-window family for HL ~70-100.
        "PEBBLES_XL": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=300, base_qty=4, max_qty=12, size_step=2.0,
        ),
        "PEBBLES_XS": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=300, base_qty=4, max_qty=12, size_step=2.0,
        ),
        "MICROCHIP_SQUARE": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=300, base_qty=4, max_qty=12, size_step=2.0,
        ),
        "MICROCHIP_TRIANGLE": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=300, base_qty=4, max_qty=12, size_step=2.0,
        ),
        "MICROCHIP_OVAL": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=300, base_qty=4, max_qty=12, size_step=2.0,
        ),
        "MICROCHIP_RECTANGLE": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=300, base_qty=4, max_qty=12, size_step=2.0,
        ),
        "ROBOT_IRONING": RollingCfg(
            window=200, min_history=180, entry_z=2.0, exit_z=0.5, stop_z=4.0,
            time_stop=240, base_qty=5, max_qty=14, size_step=3.0,
        ),
    }

    # Informed-flow signal: aggressive market trades that consistently lead the
    # mid by ~100 ticks. Validated by walk-forward (train day-2, test days 3+4).
    INFORMED_ENABLED_PRODUCTS: frozenset = frozenset({
        "UV_VISOR_MAGENTA",
        "TRANSLATOR_ASTRO_BLACK",
    })
    INFORMED_FLOW_CFG: Dict[str, InformedFlowCfg] = {
        # Burst filter (≥2 aggressive buys in last 50 ticks) lifts t-stat
        # from +1.0 to +2.5 on this product.
        "SLEEP_POD_LAMB_WOOL": InformedFlowCfg(
            direction=+1, hold_ticks=100, qty=5,
            burst_min=2, burst_window_ts=5000,
        ),
        # Single-trade trigger; burst filter weakens this one.
        "UV_VISOR_MAGENTA": InformedFlowCfg(
            direction=+1, hold_ticks=80, qty=4,
            burst_min=1, burst_window_ts=0,
        ),
        # Aggressive buys here precede price drops — trade against them.
        "TRANSLATOR_ASTRO_BLACK": InformedFlowCfg(
            direction=-1, hold_ticks=100, qty=5,
            burst_min=2, burst_window_ts=5000,
        ),
    }

    def __init__(self):
        self.spread_history = collections.defaultdict(lambda: collections.deque(maxlen=self.LOOKBACK))
        self.spread_sum: Dict[str, float] = collections.defaultdict(float)
        self.spread_sum_sq: Dict[str, float] = collections.defaultdict(float)
        self.spread_diffs: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=self.RECENT_MOVE_WINDOW)
        )
        self.spread_last: Dict[str, float] = {}
        self.mid_history = collections.defaultdict(lambda: collections.deque(maxlen=self.MID_HISTORY))
        self.pairs_by_key = {self._pair_key(pair): pair for pair in self.PAIRS}
        self.baskets_by_key = {self._basket_key(basket): basket for basket in self.BASKETS}
        self.active_pairs: Dict[str, ActivePairState] = {}
        self.insider_extrema: Dict[str, Dict[str, Optional[float]]] = {}
        self.tick_count: int = 0
        self._spread_products_cache: List[str] = list(
            set(self._all_pair_products()) | set(self._all_basket_products())
        )

        # Per-asset rolling-mean state (independent of pair spread_history).
        # Allocate only for enabled products to avoid useless deques.
        active_rolling = {
            product: cfg
            for product, cfg in self.ROLLING_CFG.items()
            if product in self.ROLLING_ENABLED_PRODUCTS
        }
        self.rm_history: Dict[str, collections.deque] = {
            product: collections.deque(maxlen=cfg.window)
            for product, cfg in active_rolling.items()
        }
        self.rm_sum: Dict[str, float] = {p: 0.0 for p in active_rolling}
        self.rm_sum_sq: Dict[str, float] = {p: 0.0 for p in active_rolling}
        self.rm_active: Dict[str, ActiveRollingState] = {}

        # Informed-flow state per product (only allocate for enabled).
        active_informed = {
            product: cfg for product, cfg in self.INFORMED_FLOW_CFG.items()
            if product in self.INFORMED_ENABLED_PRODUCTS
        }
        self.if_recent_buys: Dict[str, collections.deque] = {
            p: collections.deque() for p in active_informed
        }
        self.if_last_seen_ts: Dict[str, int] = {p: -1 for p in active_informed}
        self.if_active: Dict[str, ActiveInformedFlow] = {}

    @staticmethod
    def _best(od: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        if od is None:
            return None, None
        bb = max(od.buy_orders) if od.buy_orders else None
        ba = min(od.sell_orders) if od.sell_orders else None
        return bb, ba

    @staticmethod
    def _mid(od: OrderDepth) -> Optional[float]:
        bb, ba = Trader._best(od)
        if bb is None or ba is None:
            return None
        return (bb + ba) / 2.0

    @staticmethod
    def _pair_key(pair: PairCfg) -> str:
        return pair.a + "__" + pair.b

    @staticmethod
    def _basket_key(basket: BasketCfg) -> str:
        return basket.anchor + "__basket"

    def _limit(self, product: str) -> int:
        return int(self.POSITION_LIMITS.get(product, self.DEFAULT_LIMIT))

    def _pair_spread(self, state: TradingState, pair: PairCfg) -> Optional[float]:
        ma = self._mid(state.order_depths.get(pair.a))
        mb = self._mid(state.order_depths.get(pair.b))
        if ma is None or mb is None:
            return None
        return ma - (pair.alpha + pair.beta * mb)

    def _basket_spread(self, state: TradingState, basket: BasketCfg) -> Optional[float]:
        anchor_mid = self._mid(state.order_depths.get(basket.anchor))
        if anchor_mid is None or anchor_mid <= 0:
            return None

        peer_logs = []
        for product in basket.peers:
            mid = self._mid(state.order_depths.get(product))
            if mid is None or mid <= 0:
                return None
            peer_logs.append(math.log(mid))

        return math.log(anchor_mid) - basket.beta * (sum(peer_logs) / len(peer_logs)) - basket.intercept

    @staticmethod
    def _zscore(value: float, hist: collections.deque) -> Optional[float]:
        n = len(hist)
        if n < 2:
            return None
        mean = sum(hist) / n
        var = sum((x - mean) ** 2 for x in hist) / n
        std = math.sqrt(var)
        if std <= 1e-12:
            return None
        return (value - mean) / std

    def _append_spread(self, key: str, value: float) -> None:
        hist = self.spread_history[key]
        if hist.maxlen is not None and len(hist) == hist.maxlen:
            old = hist[0]
            self.spread_sum[key] -= old
            self.spread_sum_sq[key] -= old * old
        hist.append(value)
        self.spread_sum[key] += value
        self.spread_sum_sq[key] += value * value

        last = self.spread_last.get(key)
        if last is not None:
            self.spread_diffs[key].append(abs(value - last))
        self.spread_last[key] = value

    def _append_rolling_mid(self, product: str, mid: float) -> None:
        hist = self.rm_history.get(product)
        if hist is None:
            return
        if hist.maxlen is not None and len(hist) == hist.maxlen:
            old = hist[0]
            self.rm_sum[product] -= old
            self.rm_sum_sq[product] -= old * old
        hist.append(mid)
        self.rm_sum[product] += mid
        self.rm_sum_sq[product] += mid * mid

    def _running_std(self, key: str) -> Optional[float]:
        hist = self.spread_history.get(key)
        if hist is None:
            return None
        n = len(hist)
        if n < 2:
            return None
        mean = self.spread_sum.get(key, 0.0) / n
        var = self.spread_sum_sq.get(key, 0.0) / n - mean * mean
        if var <= 1e-24:
            return None
        return math.sqrt(var)

    def _all_pair_products(self) -> List[str]:
        products = set()
        for p in self.PAIRS:
            products.add(p.a)
            products.add(p.b)
        return list(products)

    def _all_basket_products(self) -> List[str]:
        products = set()
        for basket in self.BASKETS:
            products.add(basket.anchor)
            products.update(basket.peers)
        return list(products)

    def _all_spread_products(self) -> List[str]:
        return self._spread_products_cache

    @staticmethod
    def _is_fast_pair(pair: PairCfg) -> bool:
        return pair.regime == "fast_mean_reverting"

    def _pair_entry_threshold(self, pair: PairCfg) -> float:
        return self.FAST_ENTRY_Z if self._is_fast_pair(pair) else self.STABLE_ENTRY_Z

    def _pair_exit_threshold(self, pair: PairCfg) -> float:
        return self.FAST_EXIT_Z if self._is_fast_pair(pair) else self.STABLE_EXIT_Z

    def _pair_stop_threshold(self, pair: PairCfg) -> float:
        return self.FAST_STOP_Z if self._is_fast_pair(pair) else self.STABLE_STOP_Z

    def _pair_time_stop(self, pair: PairCfg) -> int:
        multiplier = self.FAST_HALF_LIFE_MULT if self._is_fast_pair(pair) else self.STABLE_HALF_LIFE_MULT
        raw_steps = int(pair.offline_half_life * multiplier)
        return max(350, min(2600, raw_steps))

    def _pair_base_qty(self, pair: PairCfg) -> int:
        return self.FAST_BASE_QTY if self._is_fast_pair(pair) else self.STABLE_BASE_QTY

    def _pair_max_qty(self, pair: PairCfg) -> int:
        return self.FAST_MAX_PAIR_QTY if self._is_fast_pair(pair) else self.STABLE_MAX_PAIR_QTY

    @staticmethod
    def _imbalance(od: OrderDepth) -> float:
        bb = max(od.buy_orders) if od and od.buy_orders else None
        ba = min(od.sell_orders) if od and od.sell_orders else None
        if bb is None or ba is None:
            return 0.0
        bid_vol = max(0, od.buy_orders.get(bb, 0))
        ask_vol = max(0, -od.sell_orders.get(ba, 0))
        denom = bid_vol + ask_vol
        if denom <= 0:
            return 0.0
        return (bid_vol - ask_vol) / denom

    def _update_mid_history(self, state: TradingState) -> None:
        for product, od in state.order_depths.items():
            mid = self._mid(od)
            if mid is not None and mid > 0:
                self.mid_history[product].append(mid)

    def _recent_log_return(self, product: str, window: int = 1) -> Optional[float]:
        hist = self.mid_history.get(product)
        if hist is None or len(hist) <= window:
            return None
        start = hist[-window - 1]
        end = hist[-1]
        if start <= 0 or end <= 0:
            return None
        return math.log(end / start)

    def _leader_bias(self, basket: BasketCfg) -> float:
        if basket.leader is None or basket.leader_weight <= 0 or basket.leader_window <= 0:
            return 0.0

        leader_hist = self.mid_history.get(basket.leader)
        if leader_hist is None or len(leader_hist) < basket.leader_window + 8:
            return 0.0

        ret = self._recent_log_return(basket.leader, basket.leader_window)
        if ret is None:
            return 0.0

        returns = []
        hist = list(leader_hist)
        for idx in range(1, len(hist)):
            prev = hist[idx - 1]
            curr = hist[idx]
            if prev > 0 and curr > 0:
                returns.append(math.log(curr / prev))
        if len(returns) < 6:
            return 0.0

        recent_std = math.sqrt(sum(x * x for x in returns[-12:]) / min(12, len(returns)))
        if recent_std <= 1e-8:
            return 0.0

        return ret / (recent_std * math.sqrt(max(1, basket.leader_window)))

    def _signal_activity(self, key: str, std: Optional[float] = None) -> float:
        diffs = self.spread_diffs.get(key)
        if diffs is None or len(diffs) < self.RECENT_MOVE_WINDOW:
            return 1.0
        if std is None:
            std = self._running_std(key)
        if std is None or std <= 1e-12:
            return 0.0
        return (sum(diffs) / len(diffs)) / std

    def _available_to_trade(self, state: TradingState, product: str, delta: int, levels: Optional[int] = None) -> int:
        if delta == 0:
            return 0
        od = state.order_depths.get(product)
        if od is None:
            return 0

        current_pos = state.position.get(product, 0)
        limit = self._limit(product)
        levels = self.WALK_LEVELS if levels is None else levels

        if delta > 0:
            capacity = max(0, limit - current_pos)
            asks = sorted(od.sell_orders.items(), key=lambda x: x[0])[:levels]
            displayed = sum(max(0, -qty) for _, qty in asks)
            return min(delta, capacity, displayed)
        else:
            capacity = max(0, limit + current_pos)
            bids = sorted(od.buy_orders.items(), key=lambda x: -x[0])[:levels]
            displayed = sum(max(0, qty) for _, qty in bids)
            return min(-delta, capacity, displayed)

    def _walk_to_target(
        self,
        state: TradingState,
        product: str,
        target_pos: int,
        result: Dict[Symbol, List[Order]],
        levels: Optional[int] = None,
    ) -> None:
        od = state.order_depths.get(product)
        if od is None:
            return

        current_pos = state.position.get(product, 0)
        limit = self._limit(product)
        target_pos = max(-limit, min(limit, target_pos))
        delta = target_pos - current_pos
        levels = self.WALK_LEVELS if levels is None else levels

        if delta > 0:
            remaining = min(delta, limit - current_pos)
            for price, vol in sorted(od.sell_orders.items(), key=lambda x: x[0])[:levels]:
                if remaining <= 0:
                    break
                qty = min(remaining, max(0, -vol))
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, price, qty))
                    remaining -= qty

        elif delta < 0:
            remaining = min(-delta, limit + current_pos)
            for price, vol in sorted(od.buy_orders.items(), key=lambda x: -x[0])[:levels]:
                if remaining <= 0:
                    break
                qty = min(remaining, max(0, vol))
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, price, -qty))
                    remaining -= qty

    def _pair_quality(self, pair: PairCfg) -> float:
        regime_bonus = 1.10 if self._is_fast_pair(pair) else 0.94
        corr_bonus = 0.80 + 0.25 * abs(pair.correlation)
        pvalue_bonus = max(0.88, min(1.12, 1.08 - 2.0 * pair.offline_p_value))
        half_life_bonus = max(0.72, min(1.18, 900.0 / max(450.0, pair.offline_half_life)))
        return regime_bonus * corr_bonus * pvalue_bonus * half_life_bonus

    def _build_targets_for_pair(self, state: TradingState, pair: PairCfg, direction: int, z_abs: float) -> Dict[str, int]:
        entry_threshold = self._pair_entry_threshold(pair)
        qty_cap = self._pair_max_qty(pair)
        size_step = 4 if self._is_fast_pair(pair) else 3
        qty_a = min(qty_cap, self._pair_base_qty(pair) + int(max(0.0, z_abs - entry_threshold) * size_step))
        qty_b = max(1, min(qty_cap, int(round(abs(pair.beta) * qty_a))))

        raw_targets = {
            pair.a: direction * qty_a,
            pair.b: int(-direction * math.copysign(qty_b, pair.beta)),
        }

        # Scale target changes down if one leg cannot be filled in top WALK_LEVELS levels.
        fractions = []
        for product, raw_target in raw_targets.items():
            current = state.position.get(product, 0)
            delta = raw_target - current
            if delta == 0:
                continue
            available = self._available_to_trade(state, product, delta)
            fractions.append(available / abs(delta))

        if not fractions:
            return raw_targets

        fill_fraction = max(0.0, min(1.0, min(fractions)))
        if fill_fraction < self.MIN_ENTRY_FILL_FRACTION:
            # Do not enter if one leg is too thin. Keep current positions instead.
            return {p: state.position.get(p, 0) for p in raw_targets}

        scaled_targets = {}
        for product, raw_target in raw_targets.items():
            current = state.position.get(product, 0)
            delta = raw_target - current
            scaled_delta = int(math.copysign(math.floor(abs(delta) * fill_fraction), delta)) if delta != 0 else 0
            scaled_targets[product] = current + scaled_delta
        return scaled_targets

    def _build_targets_for_basket(self, state: TradingState, basket: BasketCfg, direction: int, z_abs: float) -> Dict[str, int]:
        qty_anchor = min(self.MAX_BASKET_QTY, self.BASE_BASKET_QTY + int(max(0.0, z_abs - self.ENTRY_Z) * 2))
        total_peer_qty = max(1, min(self.MAX_BASKET_QTY, int(round(abs(basket.beta) * qty_anchor))))
        peer_sign = -direction * (1 if basket.beta > 0 else -1)

        raw_targets = {basket.anchor: direction * qty_anchor}
        base = total_peer_qty // len(basket.peers)
        remainder = total_peer_qty % len(basket.peers)
        for idx, product in enumerate(basket.peers):
            qty = base + (1 if idx < remainder else 0)
            raw_targets[product] = peer_sign * qty

        fractions = []
        for product, raw_target in raw_targets.items():
            current = state.position.get(product, 0)
            delta = raw_target - current
            if delta == 0:
                continue
            available = self._available_to_trade(state, product, delta)
            fractions.append(available / abs(delta))

        if not fractions:
            return raw_targets

        fill_fraction = max(0.0, min(1.0, min(fractions)))
        if fill_fraction < self.MIN_ENTRY_FILL_FRACTION:
            return {p: state.position.get(p, 0) for p in raw_targets}

        scaled_targets = {}
        for product, raw_target in raw_targets.items():
            current = state.position.get(product, 0)
            delta = raw_target - current
            scaled_delta = int(math.copysign(math.floor(abs(delta) * fill_fraction), delta)) if delta != 0 else 0
            scaled_targets[product] = current + scaled_delta
        return scaled_targets

    def _signal_products(self, kind: str, key: str) -> List[str]:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            if pair is None:
                return []
            return [pair.a, pair.b]
        basket = self.baskets_by_key.get(key)
        if basket is None:
            return []
        return [basket.anchor] + list(basket.peers)

    def _signal_targets(self, state: TradingState, kind: str, key: str, direction: int, z_abs: float) -> Dict[str, int]:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            return {} if pair is None else self._build_targets_for_pair(state, pair, direction, z_abs)
        basket = self.baskets_by_key.get(key)
        return {} if basket is None else self._build_targets_for_basket(state, basket, direction, z_abs)

    def _is_snackpack_signal(self, kind: str, key: str) -> bool:
        if kind != "basket":
            return False
        basket = self.baskets_by_key.get(key)
        return basket is not None and basket.anchor.startswith("SNACKPACK_")

    def _signal_entry_threshold(self, kind: str, key: str) -> float:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            return self.ENTRY_Z if pair is None else self._pair_entry_threshold(pair)
        return self.ENTRY_Z

    def _signal_exit_threshold(self, kind: str, key: str) -> float:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            return self.EXIT_Z if pair is None else self._pair_exit_threshold(pair)
        return self.EXIT_Z

    def _signal_stop_threshold(self, kind: str, key: str) -> float:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            return self.STOP_Z if pair is None else self._pair_stop_threshold(pair)
        return self.STOP_Z

    def _signal_time_stop(self, kind: str, key: str) -> int:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            return self.TIME_STOP_STEPS if pair is None else self._pair_time_stop(pair)
        return self.TIME_STOP_STEPS

    @staticmethod
    def _merge_targets(base: Dict[str, int], extra: Dict[str, int]) -> None:
        for product, target in extra.items():
            base[product] = target

    def _clear_active_pair(self, key: str) -> None:
        self.active_pairs.pop(key, None)

    def _active_pair_products(self) -> set:
        products = set()
        for key in self.active_pairs:
            products.update(self._signal_products("pair", key))
        return products

    @staticmethod
    def _all_zero(state: TradingState, products: List[str]) -> bool:
        return all(state.position.get(product, 0) == 0 for product in products)

    def _entry_score(self, state: TradingState, signal: SignalSnapshot, targets: Dict[str, int]) -> float:
        gross_change = sum(abs(targets[p] - state.position.get(p, 0)) for p in targets)
        leg_penalty = 1.0 if signal.kind == "pair" else 0.88
        activity_bonus = min(1.35, max(0.70, 0.80 + signal.activity))
        return abs(signal.entry_z) * signal.quality * leg_penalty * activity_bonus * max(1.0, gross_change)

    @staticmethod
    def _resulting_position(state: TradingState, result: Dict[Symbol, List[Order]], product: str) -> int:
        return state.position.get(product, 0) + sum(order.quantity for order in result.get(product, []))

    @staticmethod
    def _contains_trap_group(product: str, trap_groups: Tuple[str, ...]) -> bool:
        return any(trap in product for trap in trap_groups)

    @staticmethod
    def _sanitize_extrema_value(value: Any) -> Optional[float]:
        try:
            price = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(price) or price <= 0:
            return None
        return price

    @classmethod
    def _normalize_extrema_payload(cls, payload: Any) -> Dict[str, Dict[str, Optional[float]]]:
        normalized: Dict[str, Dict[str, Optional[float]]] = {}
        if not isinstance(payload, dict):
            return normalized

        for product, values in payload.items():
            if not isinstance(product, str) or not isinstance(values, dict):
                continue
            if "min" not in values and "max" not in values:
                continue

            normalized[product] = {
                "min": cls._sanitize_extrema_value(values.get("min")),
                "max": cls._sanitize_extrema_value(values.get("max")),
            }

        return normalized

    @staticmethod
    def _normalize_int_map(payload: Any) -> Dict[str, int]:
        normalized: Dict[str, int] = {}
        if not isinstance(payload, dict):
            return normalized

        for product, value in payload.items():
            if not isinstance(product, str):
                continue
            try:
                qty = int(value)
            except (TypeError, ValueError):
                continue
            if qty != 0:
                normalized[product] = qty

        return normalized

    def _load_combined_runtime_state(self, trader_data: str) -> Dict[str, Any]:
        runtime = {
            "spread_state": "",
            "insider_state": "",
            "spread_virtual_pos": {},
            "insider_virtual_pos": {},
            "spread_pending": {},
            "insider_pending": {},
            "last_processed_own_trade_ts": -1,
        }
        if not trader_data:
            return runtime

        try:
            data = json.loads(trader_data)
        except Exception:
            runtime["spread_state"] = trader_data
            return runtime

        if not isinstance(data, dict):
            runtime["spread_state"] = trader_data
            return runtime

        if any(
            key in data
            for key in (
                "spread_state",
                "insider_state",
                "spread_virtual_pos",
                "insider_virtual_pos",
                "spread_pending",
                "insider_pending",
                "last_processed_own_trade_ts",
            )
        ):
            runtime["spread_state"] = data.get("spread_state", "") if isinstance(data.get("spread_state"), str) else ""
            runtime["insider_state"] = data.get("insider_state", "") if isinstance(data.get("insider_state"), str) else ""
            runtime["spread_virtual_pos"] = self._normalize_int_map(data.get("spread_virtual_pos"))
            runtime["insider_virtual_pos"] = self._normalize_int_map(data.get("insider_virtual_pos"))
            runtime["spread_pending"] = self._normalize_int_map(data.get("spread_pending"))
            runtime["insider_pending"] = self._normalize_int_map(data.get("insider_pending"))
            try:
                runtime["last_processed_own_trade_ts"] = int(data.get("last_processed_own_trade_ts", -1))
            except (TypeError, ValueError):
                runtime["last_processed_own_trade_ts"] = -1
            return runtime

        if "active_pairs" in data or "tick_count" in data or "active_kind" in data or "active_pair_key" in data:
            spread_payload = {
                key: data[key]
                for key in (
                    "active_pairs",
                    "tick_count",
                    "active_kind",
                    "active_key",
                    "active_pair_key",
                    "active_entry_spread",
                    "active_direction",
                    "active_entry_tick",
                    "flattening",
                )
                if key in data
            }
            runtime["spread_state"] = json.dumps(spread_payload, separators=(",", ":")) if spread_payload else ""
            if "insider_extrema" in data:
                runtime["insider_state"] = jsonpickle.encode(data["insider_extrema"])

            return runtime

        if self._normalize_extrema_payload(data):
            runtime["insider_state"] = trader_data
            return runtime

        runtime["spread_state"] = trader_data
        return runtime

    @staticmethod
    def _combine_trader_data(runtime: Dict[str, Any]) -> str:
        return json.dumps({
            "spread_state": runtime.get("spread_state", ""),
            "insider_state": runtime.get("insider_state", ""),
            "spread_virtual_pos": runtime.get("spread_virtual_pos", {}),
            "insider_virtual_pos": runtime.get("insider_virtual_pos", {}),
            "spread_pending": runtime.get("spread_pending", {}),
            "insider_pending": runtime.get("insider_pending", {}),
            "last_processed_own_trade_ts": runtime.get("last_processed_own_trade_ts", -1),
        }, separators=(",", ":"))

    @staticmethod
    def _extend_orders(base: Dict[Symbol, List[Order]], extra: Dict[Symbol, List[Order]]) -> None:
        for product, orders in extra.items():
            if not orders:
                continue
            base.setdefault(product, []).extend(orders)

    @staticmethod
    def _strategy_state_with_position(state: TradingState, position: Dict[str, int]) -> TradingState:
        return TradingState(
            traderData=state.traderData,
            timestamp=state.timestamp,
            listings=state.listings,
            order_depths=state.order_depths,
            own_trades=state.own_trades,
            market_trades=state.market_trades,
            position=dict(position),
            observations=state.observations,
        )

    @staticmethod
    def _order_sums(orders: Dict[Symbol, List[Order]]) -> Dict[str, int]:
        sums: Dict[str, int] = {}
        for product, product_orders in orders.items():
            qty = sum(order.quantity for order in product_orders)
            if qty != 0:
                sums[product] = qty
        return sums

    @staticmethod
    def _clean_position_map(position: Dict[str, int]) -> Dict[str, int]:
        return {product: qty for product, qty in position.items() if qty != 0}

    @staticmethod
    def _split_fill_quantity(total_fill: int, spread_pending: int, insider_pending: int) -> Tuple[int, int]:
        total_fill = max(0, int(total_fill))
        spread_pending = max(0, int(spread_pending))
        insider_pending = max(0, int(insider_pending))
        total_pending = spread_pending + insider_pending
        if total_fill <= 0 or total_pending <= 0:
            return 0, 0
        if total_fill >= total_pending:
            return spread_pending, insider_pending

        exact_spread = total_fill * spread_pending / total_pending if spread_pending > 0 else 0.0
        exact_insider = total_fill * insider_pending / total_pending if insider_pending > 0 else 0.0

        spread_alloc = min(spread_pending, int(math.floor(exact_spread)))
        insider_alloc = min(insider_pending, int(math.floor(exact_insider)))
        remainder = total_fill - spread_alloc - insider_alloc

        ranked = sorted(
            [
                ("spread", exact_spread - spread_alloc, spread_pending - spread_alloc),
                ("insider", exact_insider - insider_alloc, insider_pending - insider_alloc),
            ],
            key=lambda item: (item[1], item[2]),
            reverse=True,
        )

        for name, _, room in ranked:
            if remainder <= 0:
                break
            if room <= 0:
                continue
            if name == "spread":
                spread_alloc += 1
            else:
                insider_alloc += 1
            remainder -= 1

        return spread_alloc, insider_alloc

    def _apply_virtual_fills(self, state: TradingState, runtime: Dict[str, Any]) -> None:
        spread_virtual = dict(runtime.get("spread_virtual_pos", {}))
        insider_virtual = dict(runtime.get("insider_virtual_pos", {}))
        spread_pending = dict(runtime.get("spread_pending", {}))
        insider_pending = dict(runtime.get("insider_pending", {}))
        last_processed_ts = int(runtime.get("last_processed_own_trade_ts", -1))
        newest_processed_ts = last_processed_ts

        for product, trades in state.own_trades.items():
            buy_fill = 0
            sell_fill = 0
            for trade in trades:
                if trade.timestamp <= last_processed_ts:
                    continue
                newest_processed_ts = max(newest_processed_ts, trade.timestamp)
                if trade.buyer == "SUBMISSION":
                    buy_fill += trade.quantity
                elif trade.seller == "SUBMISSION":
                    sell_fill += trade.quantity

            if buy_fill > 0:
                spread_alloc, insider_alloc = self._split_fill_quantity(
                    buy_fill,
                    max(0, spread_pending.get(product, 0)),
                    max(0, insider_pending.get(product, 0)),
                )
                if spread_alloc:
                    spread_virtual[product] = spread_virtual.get(product, 0) + spread_alloc
                if insider_alloc:
                    insider_virtual[product] = insider_virtual.get(product, 0) + insider_alloc

            if sell_fill > 0:
                spread_alloc, insider_alloc = self._split_fill_quantity(
                    sell_fill,
                    max(0, -spread_pending.get(product, 0)),
                    max(0, -insider_pending.get(product, 0)),
                )
                if spread_alloc:
                    spread_virtual[product] = spread_virtual.get(product, 0) - spread_alloc
                if insider_alloc:
                    insider_virtual[product] = insider_virtual.get(product, 0) - insider_alloc

        all_products = set(state.position) | set(spread_virtual) | set(insider_virtual)
        for product in all_products:
            actual_pos = state.position.get(product, 0)
            spread_pos = spread_virtual.get(product, 0)
            insider_pos = insider_virtual.get(product, 0)
            diff = actual_pos - (spread_pos + insider_pos)
            if diff == 0:
                continue
            if abs(insider_pos) > abs(spread_pos):
                insider_virtual[product] = insider_pos + diff
            else:
                spread_virtual[product] = spread_pos + diff

        runtime["spread_virtual_pos"] = self._clean_position_map(spread_virtual)
        runtime["insider_virtual_pos"] = self._clean_position_map(insider_virtual)
        runtime["spread_pending"] = {}
        runtime["insider_pending"] = {}
        runtime["last_processed_own_trade_ts"] = newest_processed_ts

    def _clip_orders_to_limits(self, state: TradingState, orders: Dict[Symbol, List[Order]]) -> None:
        for product in list(orders.keys()):
            current_pos = state.position.get(product, 0)
            limit = self._limit(product)
            long_room = max(0, limit - current_pos)
            short_room = max(0, limit + current_pos)
            used_long = 0
            used_short = 0
            clipped: List[Order] = []

            for order in orders.get(product, []):
                if order.quantity > 0:
                    available = long_room - used_long
                    if available <= 0:
                        continue
                    qty = min(order.quantity, available)
                    if qty > 0:
                        clipped.append(Order(order.symbol, order.price, qty))
                        used_long += qty
                elif order.quantity < 0:
                    available = short_room - used_short
                    if available <= 0:
                        continue
                    qty = min(-order.quantity, available)
                    if qty > 0:
                        clipped.append(Order(order.symbol, order.price, -qty))
                        used_short += qty

            if clipped:
                orders[product] = clipped
            else:
                orders.pop(product, None)

    def _load_state_from_trader_data(self, trader_data: str) -> None:
        if not trader_data:
            return
        try:
            data = json.loads(trader_data)
            if not isinstance(data, dict):
                return
            self.tick_count = int(data.get("tick_count", self.tick_count or 0))

            self.active_pairs = {}
            active_pairs = data.get("active_pairs", {})
            if isinstance(active_pairs, dict):
                for key, item in active_pairs.items():
                    if key not in self.pairs_by_key or not isinstance(item, dict):
                        continue
                    self.active_pairs[key] = ActivePairState(
                        direction=int(item.get("direction", 0)),
                        entry_tick=int(item.get("entry_tick", self.tick_count)),
                        entry_spread=float(item.get("entry_spread", 0.0)),
                        flattening=bool(item.get("flattening", False)),
                    )

            # Backward compatibility with the prior single-trade state shape.
            active_kind = data.get("active_kind")
            active_key = data.get("active_key") or data.get("active_pair_key")
            if (
                not self.active_pairs
                and active_kind == "pair"
                and isinstance(active_key, str)
                and active_key in self.pairs_by_key
            ):
                entry_spread = data.get("active_entry_spread", 0.0)
                self.active_pairs[active_key] = ActivePairState(
                    direction=int(data.get("active_direction", 0)),
                    entry_tick=int(data.get("active_entry_tick", self.tick_count)),
                    entry_spread=float(0.0 if entry_spread is None else entry_spread),
                    flattening=bool(data.get("flattening", False)),
                )

            self.rm_active = {}
            rm_active = data.get("rm_active", {})
            if isinstance(rm_active, dict):
                for product, item in rm_active.items():
                    if product not in self.ROLLING_CFG or not isinstance(item, dict):
                        continue
                    self.rm_active[product] = ActiveRollingState(
                        direction=int(item.get("direction", 0)),
                        entry_tick=int(item.get("entry_tick", self.tick_count)),
                    )

            self.if_active = {}
            if_active = data.get("if_active", {})
            if isinstance(if_active, dict):
                for product, item in if_active.items():
                    if product not in self.INFORMED_FLOW_CFG or not isinstance(item, dict):
                        continue
                    self.if_active[product] = ActiveInformedFlow(
                        direction=int(item.get("direction", 0)),
                        entry_timestamp=int(item.get("entry_timestamp", 0)),
                    )
        except Exception:
            return

    def _dump_state_to_trader_data(self) -> str:
        return json.dumps({
            "active_pairs": {
                key: {
                    "direction": value.direction,
                    "entry_tick": value.entry_tick,
                    "entry_spread": value.entry_spread,
                    "flattening": value.flattening,
                }
                for key, value in self.active_pairs.items()
            },
            "rm_active": {
                product: {
                    "direction": value.direction,
                    "entry_tick": value.entry_tick,
                }
                for product, value in self.rm_active.items()
            },
            "if_active": {
                product: {
                    "direction": value.direction,
                    "entry_timestamp": value.entry_timestamp,
                }
                for product, value in self.if_active.items()
            },
            "tick_count": self.tick_count,
        }, separators=(",", ":"))

    def _collect_signals(self, state: TradingState) -> Dict[Tuple[str, str], SignalSnapshot]:
        signals: Dict[Tuple[str, str], SignalSnapshot] = {}
        min_history = self.MIN_HISTORY

        for pair in self.PAIRS:
            spread = self._pair_spread(state, pair)
            if spread is None:
                continue
            key = self._pair_key(pair)
            self._append_spread(key, spread)
            n = len(self.spread_history[key])
            if n < min_history:
                continue
            mean = self.spread_sum[key] / n
            var = self.spread_sum_sq[key] / n - mean * mean
            if var <= 1e-24:
                continue
            std = math.sqrt(var)
            z = (spread - mean) / std
            activity = self._signal_activity(key, std)
            signals[("pair", key)] = SignalSnapshot(
                "pair", key, z, z, self._pair_quality(pair), spread, activity
            )

        for basket in self.BASKETS:
            spread = self._basket_spread(state, basket)
            if spread is None:
                continue
            key = self._basket_key(basket)
            self._append_spread(key, spread)
            n = len(self.spread_history[key])
            if n < min_history:
                continue
            mean = self.spread_sum[key] / n
            var = self.spread_sum_sq[key] / n - mean * mean
            if var <= 1e-24:
                continue
            std = math.sqrt(var)
            z = (spread - mean) / std
            entry_z = z - basket.leader_weight * self._leader_bias(basket)
            activity = self._signal_activity(key, std)
            signals[("basket", key)] = SignalSnapshot(
                "basket", key, z, entry_z, basket.quality, spread, activity
            )

        return signals

    def _select_new_pair_entries(
        self,
        state: TradingState,
        signals: Dict[Tuple[str, str], SignalSnapshot],
        targets: Dict[str, int],
        reserved_products: set,
    ) -> None:
        open_pairs = sum(1 for active in self.active_pairs.values() if not active.flattening)
        if open_pairs >= self.MAX_ACTIVE_PAIRS:
            return

        occupied_products = {
            product
            for product in self._all_spread_products()
            if state.position.get(product, 0) != 0 and product not in reserved_products
        }

        candidates = []
        for (kind, key), signal in signals.items():
            if kind != "pair" or key in self.active_pairs:
                continue

            entry_threshold = self._signal_entry_threshold(signal.kind, signal.key)
            if abs(signal.entry_z) < entry_threshold:
                continue

            direction = -1 if signal.entry_z > 0 else 1
            proposed = self._signal_targets(state, signal.kind, signal.key, direction, abs(signal.entry_z))
            if not any(proposed[p] != state.position.get(p, 0) for p in proposed):
                continue

            pair_products = set(self._signal_products(signal.kind, signal.key))
            candidates.append(
                (
                    self._entry_score(state, signal, proposed),
                    signal,
                    direction,
                    proposed,
                    pair_products,
                )
            )

        candidates.sort(key=lambda item: item[0], reverse=True)

        for _, signal, direction, proposed, pair_products in candidates:
            if open_pairs >= self.MAX_ACTIVE_PAIRS:
                break
            if pair_products & reserved_products:
                continue
            if pair_products & occupied_products:
                continue

            self.active_pairs[signal.key] = ActivePairState(
                direction=direction,
                entry_tick=self.tick_count,
                entry_spread=signal.spread,
                flattening=False,
            )
            self._merge_targets(targets, proposed)
            reserved_products.update(pair_products)
            open_pairs += 1

    def _trade_rolling_mean(
        self,
        state: TradingState,
        targets: Dict[str, int],
        reserved_products: set,
    ) -> None:
        if not self.ROLLING_ENABLED_PRODUCTS:
            return

        for product, cfg in self.ROLLING_CFG.items():
            if product not in self.ROLLING_ENABLED_PRODUCTS:
                continue
            if product in DISABLED_PRODUCTS:
                continue
            od = state.order_depths.get(product)
            mid = self._mid(od)
            if mid is None:
                continue

            # Always append history so stats stay current even when gated off.
            self._append_rolling_mid(product, mid)

            # Skip trading if a pair (or earlier strategy) already owns this product.
            if product in reserved_products:
                continue

            n = len(self.rm_history[product])
            if n < cfg.min_history:
                continue

            mean = self.rm_sum[product] / n
            var = self.rm_sum_sq[product] / n - mean * mean
            if var <= 1e-24:
                continue
            std = math.sqrt(var)
            z = (mid - mean) / std

            active = self.rm_active.get(product)
            if active is None:
                if abs(z) < cfg.entry_z:
                    continue
                direction = -1 if z > 0 else 1
                size_bonus = int(max(0.0, abs(z) - cfg.entry_z) * cfg.size_step)
                qty = min(cfg.max_qty, cfg.base_qty + size_bonus)
                targets[product] = direction * qty
                self.rm_active[product] = ActiveRollingState(
                    direction=direction,
                    entry_tick=self.tick_count,
                )
                reserved_products.add(product)
                continue

            age = self.tick_count - active.entry_tick
            signed_z = active.direction * z
            # signed_z is negative when winning; reverts toward 0 / positive on adverse moves.
            should_exit = (
                age > cfg.time_stop
                or signed_z >= -cfg.exit_z
                or signed_z <= -cfg.stop_z
            )
            if should_exit:
                targets[product] = 0
                self.rm_active.pop(product, None)
            else:
                size_bonus = int(max(0.0, abs(z) - cfg.entry_z) * cfg.size_step)
                qty = min(cfg.max_qty, cfg.base_qty + size_bonus)
                targets[product] = active.direction * qty
            reserved_products.add(product)

    def _trade_informed_flow(
        self,
        state: TradingState,
        targets: Dict[str, int],
        reserved_products: set,
    ) -> None:
        if not self.INFORMED_ENABLED_PRODUCTS:
            return

        current_ts = state.timestamp
        for product, cfg in self.INFORMED_FLOW_CFG.items():
            if product not in self.INFORMED_ENABLED_PRODUCTS:
                continue
            if product in DISABLED_PRODUCTS:
                continue
            if product in reserved_products:
                continue

            # Manage open position before considering a new entry.
            active = self.if_active.get(product)
            if active is not None:
                elapsed = current_ts - active.entry_timestamp
                if elapsed >= cfg.hold_ticks * 100:
                    targets[product] = 0
                    self.if_active.pop(product, None)
                else:
                    targets[product] = active.direction * cfg.qty
                reserved_products.add(product)
                continue

            od = state.order_depths.get(product)
            mid = self._mid(od)
            if mid is None:
                continue

            last_seen = self.if_last_seen_ts.get(product, -1)
            new_aggressive_buy = False
            max_seen = last_seen
            for trade in state.market_trades.get(product, []):
                if trade.timestamp <= last_seen:
                    continue
                if trade.timestamp > max_seen:
                    max_seen = trade.timestamp
                if trade.price > mid:
                    new_aggressive_buy = True
                    if cfg.burst_window_ts > 0:
                        self.if_recent_buys[product].append(trade.timestamp)
            if max_seen > last_seen:
                self.if_last_seen_ts[product] = max_seen

            # Burst count over the configured window.
            if cfg.burst_window_ts > 0:
                buys = self.if_recent_buys[product]
                cutoff = current_ts - cfg.burst_window_ts
                while buys and buys[0] < cutoff:
                    buys.popleft()
                burst_count = len(buys)
            else:
                burst_count = 1 if new_aggressive_buy else 0

            if not new_aggressive_buy or burst_count < cfg.burst_min:
                continue

            entry_dir = cfg.direction
            targets[product] = entry_dir * cfg.qty
            self.if_active[product] = ActiveInformedFlow(
                direction=entry_dir,
                entry_timestamp=current_ts,
            )
            reserved_products.add(product)

    def _trade_spreads(self, state: TradingState, result: Dict[Symbol, List[Order]]) -> None:
        signals = self._collect_signals(state)
        targets: Dict[str, int] = {}

        for key in list(self.active_pairs.keys()):
            products = self._signal_products("pair", key)
            if self.active_pairs[key].flattening and self._all_zero(state, products):
                self._clear_active_pair(key)

        reserved_products = set()

        for key in list(self.active_pairs.keys()):
            active_state = self.active_pairs.get(key)
            pair = self.pairs_by_key.get(key)
            if active_state is None or pair is None:
                self._clear_active_pair(key)
                continue

            active_products = self._signal_products("pair", key)
            active_signal = signals.get(("pair", key))

            if active_state.flattening or active_signal is None:
                self._merge_targets(targets, {product: 0 for product in active_products})
                active_state.flattening = True
                reserved_products.update(active_products)
                continue

            age = self.tick_count - active_state.entry_tick
            _spread_pnl = active_state.direction * (active_signal.spread - active_state.entry_spread)
            exit_z = self._pair_exit_threshold(pair)
            stop_z = self._pair_stop_threshold(pair)
            time_stop = self._pair_time_stop(pair)
            should_exit = (
                abs(active_signal.raw_z) > stop_z
                or age > time_stop
                or abs(active_signal.raw_z) < exit_z
            )

            if should_exit:
                self._merge_targets(targets, {product: 0 for product in active_products})
                active_state.flattening = True
            else:
                proposed = self._build_targets_for_pair(state, pair, active_state.direction, abs(active_signal.entry_z))
                self._merge_targets(targets, proposed)

            reserved_products.update(active_products)

        self._select_new_pair_entries(state, signals, targets, reserved_products)

        self._trade_rolling_mean(state, targets, reserved_products)
        self._trade_informed_flow(state, targets, reserved_products)

        active_products = self._active_pair_products()
        rolling_active_products = set(self.rm_active.keys())
        informed_active_products = set(self.if_active.keys())

        flatten_products = (
            set(self._all_spread_products())
            | set(self.ROLLING_CFG.keys())
            | set(self.INFORMED_FLOW_CFG.keys())
        )
        for product in flatten_products:
            if (
                product in active_products
                or product in rolling_active_products
                or product in informed_active_products
            ):
                continue
            if state.position.get(product, 0) != 0:
                targets.setdefault(product, 0)

        for product, target in targets.items():
            levels = self.FLATTEN_WALK_LEVELS if target == 0 else self.WALK_LEVELS
            self._walk_to_target(state, product, target, result, levels=levels)

    def _update_insider_extrema(self, state: TradingState) -> None:
        for product, order_depth in state.order_depths.items():
            if product in DISABLED_PRODUCTS:
                continue
            if self._contains_trap_group(product, self.INSIDER_TRAP_GROUPS):
                continue

            extrema = self.insider_extrema.setdefault(product, {"min": None, "max": None})

            if order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                current_max = extrema.get("max")
                extrema["max"] = best_ask if current_max is None else max(current_max, best_ask)

            if order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                current_min = extrema.get("min")
                extrema["min"] = best_bid if current_min is None else min(current_min, best_bid)

    def _trade_insider_synchronization(self, state: TradingState, result: Dict[Symbol, List[Order]]) -> None:
        self._update_insider_extrema(state)

        insider_trades: Dict[str, int] = {}
        for product, trades in state.market_trades.items():
            if product in DISABLED_PRODUCTS:
                continue
            if self._contains_trap_group(product, self.INSIDER_TRAP_GROUPS):
                continue
            if trades:
                insider_trades[product] = trades[-1].price

        if len(insider_trades) <= self.INSIDER_SYNC_THRESHOLD:
            return

        for product, trade_price in insider_trades.items():
            order_depth = state.order_depths.get(product)
            extrema = self.insider_extrema.get(product)
            if order_depth is None or extrema is None:
                continue

            current_pos = self._resulting_position(state, result, product)
            limit = self._limit(product)
            insider_limit = min(limit, self.INSIDER_POSITION_LIMIT)

            daily_min = extrema.get("min")
            if daily_min is not None and trade_price <= daily_min and order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                displayed = max(0, -order_depth.sell_orders[best_ask])
                desired_qty = insider_limit - current_pos
                capacity = max(0, limit - current_pos)
                qty = min(max(0, desired_qty), capacity, displayed)
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, best_ask, qty))
                continue

            daily_max = extrema.get("max")
            if daily_max is not None and trade_price >= daily_max and order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                displayed = max(0, order_depth.buy_orders[best_bid])
                desired_qty = -insider_limit - current_pos
                capacity = max(0, limit + current_pos)
                qty = min(max(0, -desired_qty), capacity, displayed)
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, best_bid, -qty))

    def _run_insider_strategy(self, state: TradingState, trader_data: str) -> Tuple[Dict[Symbol, List[Order]], str]:
        orders: Dict[Symbol, List[Order]] = {}

        if trader_data:
            try:
                extrema = jsonpickle.decode(trader_data)
            except Exception:
                extrema = {}
        else:
            extrema = {}

        if not isinstance(extrema, dict):
            extrema = {}

        for product, order_depth in state.order_depths.items():
            if product in DISABLED_PRODUCTS:
                continue
            if any(trap in product for trap in self.INSIDER_TRAP_GROUPS):
                continue

            if product not in extrema or not isinstance(extrema[product], dict):
                extrema[product] = {"min": float("inf"), "max": 0}

            if order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                extrema[product]["max"] = max(extrema[product]["max"], best_ask)
            if order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                extrema[product]["min"] = min(extrema[product]["min"], best_bid)

        insider_trades: Dict[str, int] = {}
        for product, trades in state.market_trades.items():
            if product in DISABLED_PRODUCTS:
                continue
            if any(trap in product for trap in self.INSIDER_TRAP_GROUPS):
                continue
            if trades:
                insider_trades[product] = trades[-1].price

        if len(insider_trades) > self.INSIDER_SYNC_THRESHOLD:
            for product, trade_price in insider_trades.items():
                if product not in state.order_depths:
                    continue

                orders[product] = []
                current_pos = state.position.get(product, 0)
                order_depth = state.order_depths[product]

                if trade_price <= extrema[product]["min"]:
                    desired_qty = self.INSIDER_POSITION_LIMIT - current_pos
                    if desired_qty > 0 and len(order_depth.sell_orders) > 0:
                        best_ask = min(order_depth.sell_orders.keys())
                        orders[product].append(Order(product, best_ask, desired_qty))

                elif trade_price >= extrema[product]["max"]:
                    desired_qty = -self.INSIDER_POSITION_LIMIT - current_pos
                    if desired_qty < 0 and len(order_depth.buy_orders) > 0:
                        best_bid = max(order_depth.buy_orders.keys())
                        orders[product].append(Order(product, best_bid, desired_qty))

        return orders, jsonpickle.encode(extrema)

    def _zscore_from_key(self, key: str, state: TradingState, kind: str) -> float:
        if kind == "pair":
            pair = self.pairs_by_key.get(key)
            spread = None if pair is None else self._pair_spread(state, pair)
        else:
            basket = self.baskets_by_key.get(key)
            spread = None if basket is None else self._basket_spread(state, basket)
        if spread is None:
            return 0.0
        hist = self.spread_history.get(key)
        if hist is None:
            return 0.0
        z = self._zscore(spread, hist)
        return 0.0 if z is None else z

    def _quote_market_making(self, state: TradingState, result: Dict[Symbol, List[Order]], reserved_products: set) -> None:
        for product in self.MAKER_PRODUCTS:
            if product in reserved_products:
                continue

            od = state.order_depths.get(product)
            bb, ba = self._best(od)
            if od is None or bb is None or ba is None:
                continue

            spread = ba - bb
            if spread < self.MAKER_MIN_SPREAD:
                continue

            current_pos = state.position.get(product, 0)
            if abs(current_pos) >= self.MAKER_POSITION_LIMIT:
                continue

            mid = (bb + ba) / 2.0
            fair = mid + self.MAKER_IMB_SHIFT * self._imbalance(od) - self.MAKER_INV_SHIFT * current_pos
            bid_price = min(ba - 1, bb + 1)
            ask_price = max(bb + 1, ba - 1)

            target = 0
            if fair >= mid + self.MAKER_SIGNAL_THRESHOLD:
                target = min(self.MAKER_POSITION_LIMIT, 2)
            elif fair <= mid - self.MAKER_SIGNAL_THRESHOLD:
                target = -min(self.MAKER_POSITION_LIMIT, 2)

            if target > current_pos:
                qty = min(self.MAKER_ORDER_SIZE, target - current_pos)
                if qty > 0 and bid_price <= ba - 1:
                    result.setdefault(product, []).append(Order(product, bid_price, qty))
            elif target < current_pos:
                qty = min(self.MAKER_ORDER_SIZE, current_pos - target)
                if qty > 0 and ask_price >= bb + 1:
                    result.setdefault(product, []).append(Order(product, ask_price, -qty))
            elif current_pos > 0:
                qty = min(self.MAKER_ORDER_SIZE, current_pos)
                if qty > 0 and ask_price >= bb + 1:
                    result.setdefault(product, []).append(Order(product, ask_price, -qty))
            elif current_pos < 0:
                qty = min(self.MAKER_ORDER_SIZE, -current_pos)
                if qty > 0 and bid_price <= ba - 1:
                    result.setdefault(product, []).append(Order(product, bid_price, qty))

    def run(self, state: TradingState):
        runtime = self._load_combined_runtime_state(state.traderData)
        self._load_state_from_trader_data(runtime["spread_state"])
        self._apply_virtual_fills(state, runtime)
        self.tick_count += 1

        spread_state = self._strategy_state_with_position(state, runtime["spread_virtual_pos"])
        insider_state = self._strategy_state_with_position(state, runtime["insider_virtual_pos"])

        result: Dict[str, List[Order]] = {}
        spread_orders: Dict[str, List[Order]] = {}
        self._trade_spreads(spread_state, spread_orders)
        insider_orders, next_insider_state = self._run_insider_strategy(insider_state, runtime["insider_state"])

        runtime["spread_state"] = self._dump_state_to_trader_data()
        runtime["insider_state"] = next_insider_state
        runtime["spread_pending"] = self._order_sums(spread_orders)
        runtime["insider_pending"] = self._order_sums(insider_orders)

        self._extend_orders(result, spread_orders)
        self._extend_orders(result, insider_orders)

        reserved_products = set(result.keys())
        reserved_products.update(self._active_pair_products())
        for product in self._all_spread_products():
            if state.position.get(product, 0) != 0:
                reserved_products.add(product)
        self._quote_market_making(state, result, reserved_products)
        self._clip_orders_to_limits(state, result)

        conversions = 0
        trader_data = self._combine_trader_data(runtime)
        try:
            logger.flush(state, result, conversions, trader_data)
        except Exception:
            pass
        return result, conversions, trader_data