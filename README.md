# IMC Prosperity 4
This repository contains research and algorithms for the ZBTraders team in IMC Prosperity 4 (2026). Our team is composed of five students from Northwestern University interested in the intersection of Mathematics, Computer Science, and Trading. 
 
## The Team:

**Wilson Trindade** ('28) | CS + Econ | [Linkedin](https://linkedin.com/in/wilsonftrindade/) | WilsonFerreiraTrindadeNeto2028@u.northwestern.edu  
**Francesco Boccuzzi** ('28) | Math + CS | [Linkedin](https://linkedin.com/in/francesco-ma-boccuzzi/) | FrancescoBoccuzzi2028@u.northwestern.edu  
**Adi Rosenstock**    ('27) | CS + Data Science    | [Linkedin](https://linkedin.com/in/adirosenstock/) | AdiRosenstock2026@u.northwestern.edu  
**Matias Claure** ('29) | Computer Science | [Linkedin](https://linkedin.com/in/matiasclaure/) | MatiasClaure2029@u.northwestern.edu  
**Tal Aizenberg** ('28) | Math + History | [Linkedin](https://linkedin.com/in/tal-aizenberg/) | TalAizenberg2028@u.northwestern.edu


## IMC Prosperity 

Prosperity is IMC's flagship trading competition for STEM students. The challenge mirrors real-world market dynamics, but in a simulated market environment, giving participants the opportunity to compete in realistic manual and algorithmic trading simulations. Participants act as quantitative developers and market makers on a simulated exchange, writing Python algorithms to trade various fictional assets (such as Intarian Pepper Root, Ash-Coated Osmium, and Aether Crystals) to maximize their in-game currency, XIRECs. Alongside the automated algorithmic trading, the competition also features distinct manual challenges consisting of complex game theory, options pricing, and portfolio optimization puzzles.

## Round-by-Round Performance

Our team improved significantly through the middle rounds, reaching #146 overall and #153 in the algorithmic leaderboard in Round 3. After a final-round drawdown, we finished #540 globally out of 18,803 teams.

| Round | Overall Rank | Algorithmic Rank | Manual Rank | Products / Mechanics |
|---|---:|---:|---:|---|
| Round 1 | #1,042 | #1,445 | #7 | `INTARIAN_PEPPER_ROOT`, `ASH_COATED_OSMIUM` |
| Round 2 | #598 | N/A | N/A | Same products as Round 1, plus blind auction for extra market access |
| Round 3 | #146 | #153 | #69 | `HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT`, and 10 `VELVETFRUIT_EXTRACT_VOUCHER` options |
| Round 4 | #247 | #205 | #1,373 | Same products as Round 3, plus counterparty-level trading data |
| Round 5 | #540 | #670 | #654 | 50 new products across 10 product groups, replacing all previous assets |

Note: Scores reset after Round 2, when only teams with 200,000 XIRECs or more advanced to the following rounds. Round 2 algorithmic and manual ranks were not separately tracked.

## Final Performance

The competition included 30,703 competing participants across 18,803 teams from 1,549 universities in 117 countries. We achieved the following results:

| Metric | Result |
|---|---:|
| Final Global Rank | #540 / 18,803 teams |
| Final Percentile | Top 3% |
| Peak Overall Rank | #146 |
| Peak Algorithmic Rank | #153 |
| Brazil Rank | #1 |
| South America Rank | #3 |

## My Contributions

I primarily worked on the algorithmic trading side of the competition from Rounds 1-4, focusing on strategy research, implementation, backtesting, and parameter tuning.

My strongest contribution came in Round 3, where I built the core algorithmic submission, including the main trading logic, product-level analysis, backtesting iterations, and final parameter choices. That submission ranked #153 globally on the algorithmic leaderboard and helped the team reach #146 overall.

I also worked heavily on Round 4, refining our strategies around the newly introduced counterparty-level trading data. 
 
### Strategy Development

I developed and iterated on multiple classes of trading strategies, including:

- **Market making strategies** that placed bid and ask orders around estimated fair values while adjusting for spread, liquidity, inventory, and position limits.
- **Mean-reversion strategies** that traded products when prices deviated from historical or model-based fair values.
- **Relative-value strategies** that compared related products against estimated fair values and traded pricing discrepancies when the spread was large enough.
- **Options-style strategies** for voucher products, using fair value estimates, strike-specific behavior, time-to-expiry assumptions, and implied volatility intuition to identify mispriced contracts.
- **Counterparty-aware refinements** in Round 4, where newly available trade participant data was used to study market behavior and improve execution decisions.

### Backtesting and Research

A large part of my work involved testing strategies on historical competition data before submission. I used backtests to:

- Break down profit and loss by product, round, and trading logic.
- Compare performance across different competition days.
- Continuously iterate to tune thresholds, position limits, order sizes, and quoting behavior.
- Identify when a strategy looked profitable because of a real signal versus when it was likely overfit to historical data.
- Evaluate tradeoffs between maximizing backtest profit and keeping the strategy robust enough for live submission.

### Risk and Execution

I also worked on execution logic and risk controls, including:

- Managing inventory so the algorithm did not accumulate excessive exposure in one direction.
- Adjusting order aggressiveness based on confidence in the signal.
- Limiting trade sizes to avoid unstable behavior near position limits.
- Studying round-by-round performance to understand how drawdowns, overfitting, and execution choices affected leaderboard outcomes.

## Acknowledgments and Reflections

This was my first year participating in IMC Prosperity, and it was one of the most valuable technical quantitative trading projects I have worked on so far. The competition challenged me to learn quickly, iterate under pressure, and improve our strategies across each round under real-time constraints.

Huge thank you to my teammates, Francesco, Adi, Matias, and Tal, for everything they contributed throughout the competition. IMC Prosperity is very much a team competition, and it was really valuable to have a group I could rely on across both the algorithmic and manual challenges.

I also want to credit the open-source [Prosperity backtester](https://github.com/kevin-fu1/imc-prosperity-4-backtester.git) by [@kevin-fu1](https://github.com/kevin-fu1), which helped us test and iterate more effectively.

After learning a lot from this first attempt, I am excited to come back stronger for IMC Prosperity 5!
