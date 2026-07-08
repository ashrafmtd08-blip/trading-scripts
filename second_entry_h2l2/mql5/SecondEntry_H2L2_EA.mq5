//+------------------------------------------------------------------+
//|                                        SecondEntry_H2L2_EA.mq5    |
//|   Second Entry (H2/L2) pull-back strategy — native MT5 Expert     |
//|                                                                  |
//|   Port of the Python engine (second_entry_backtest.py): EMA(20)  |
//|   trend, a failed first break (H1/L1), a deeper pull-back, then   |
//|   the second break as entry, gated by a Fair Value Gap and a      |
//|   trend/ADX + bar-quality + EMA-touch filter. Fixed 2R target,    |
//|   1% risk sizing, break-even at 1R, pending-order expiry.         |
//|                                                                  |
//|   Point-based inputs use the symbol's own _Point, so they scale   |
//|   correctly on FX, Gold and Crypto. Compile in MetaEditor (F7),   |
//|   then TEST IN THE STRATEGY TESTER / ON DEMO before live use.     |
//+------------------------------------------------------------------+
#property copyright "Second Entry (H2/L2)"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- inputs (defaults mirror the backtested configuration) ---------
input int    InpEmaPeriod      = 20;     // EMA period (trend)
input int    InpAdxPeriod      = 14;     // ADX period
input double InpAdxMin         = 15.0;   // min ADX to allow a trade
input int    InpTrendLookback  = 5;      // bars for EMA-slope check
input double InpClosePosRatio  = 0.50;   // signal bar close in upper/lower half
input int    InpEmaTouchPoints = 300;    // pull-back must come within N points of EMA
input int    InpBufferPoints   = 20;     // entry/SL buffer, in points
input double InpRR             = 2.0;    // reward:risk (fixed TP)
input int    InpExpiryBars     = 12;     // pending order auto-cancels after N bars
input double InpRiskPercent    = 1.0;    // % of balance risked per trade
input double InpBreakEvenAtR   = 1.0;    // move SL to entry once +N R
input int    InpMaxSpreadPts   = 25;     // skip a signal if spread wider than this
input bool   InpOnePerSide     = true;   // at most one order/position per side
input int    InpLookbackBars   = 500;    // bars replayed each new bar
input double InpMinLot         = 0.01;   // lot clamp
input double InpMaxLot         = 50.0;   // lot clamp
input long   InpMagic          = 250707; // magic number (isolates this EA's orders)

//--- globals -------------------------------------------------------
int      g_hEMA = INVALID_HANDLE;
int      g_hADX = INVALID_HANDLE;
datetime g_lastBar = 0;
CTrade   g_trade;

//+------------------------------------------------------------------+
int OnInit()
{
   g_hEMA = iMA(_Symbol, _Period, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_hADX = iADX(_Symbol, _Period, InpAdxPeriod);
   if(g_hEMA == INVALID_HANDLE || g_hADX == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles");
      return(INIT_FAILED);
   }
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetDeviationInPoints(20);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(g_hEMA != INVALID_HANDLE) IndicatorRelease(g_hEMA);
   if(g_hADX != INVALID_HANDLE) IndicatorRelease(g_hADX);
}

//+------------------------------------------------------------------+
void OnTick()
{
   ManageBreakEven();                         // every tick

   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 == g_lastBar) return;                // act only on a new closed bar
   g_lastBar = t0;
   OnNewBar();
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
int FvgImpulse(const double &h[], const double &l[], int n, int j, bool bull)
{
   for(int k = 0; k < 2; k++)
   {
      int mid = j + k;
      if(mid - 1 < 0 || mid + 1 >= n) continue;
      if(bull  && l[mid + 1] > h[mid - 1]) return mid;   // bullish gap
      if(!bull && h[mid + 1] < l[mid - 1]) return mid;   // bearish gap
   }
   return -1;
}

bool TrendOK(const double &ema[], const double &adx[], int j, bool bull)
{
   if(adx[j] < InpAdxMin) return false;
   double slope = ema[j] - ema[j - InpTrendLookback];
   return bull ? (slope > 0) : (slope < 0);
}

bool QualityOK(const double &o[], const double &h[], const double &l[],
               const double &c[], int j, bool bull)
{
   double rng = h[j] - l[j];
   if(rng <= 0) return false;
   if(bull)  return (c[j] > o[j] && (c[j] - l[j]) / rng >= InpClosePosRatio);
   return          (c[j] < o[j] && (h[j] - c[j]) / rng >= InpClosePosRatio);
}

//--- scan one direction; keeps the MOST RECENT valid signal --------
bool ScanDir(const double &o[], const double &h[], const double &l[],
             const double &c[], const double &ema[], const double &adx[],
             int n, double touch, double buffer, bool bull,
             double &entry, double &stop, double &tp, int &sigbar)
{
   int warmup = MathMax(InpEmaPeriod, MathMax(InpAdxPeriod, InpTrendLookback)) + 2;
   bool found = false;
   int i = warmup;
   while(i < n - 2)
   {
      bool regime = bull ? (c[i] > ema[i]) : (c[i] < ema[i]);
      if(!regime) { i++; continue; }
      bool started = bull ? (l[i] < l[i - 1]) : (h[i] > h[i - 1]);
      if(!started) { i++; continue; }

      double pb_ext = bull ? l[i] : h[i];
      double pb_gap = bull ? (l[i] - ema[i]) : (ema[i] - h[i]);
      bool h1_seen = false, deeper = false;
      double h1_ref = 0.0;
      int j = i + 1;
      bool resolved = false;

      while(j < n - 1)
      {
         if((bull && c[j] < ema[j] - touch) || (!bull && c[j] > ema[j] + touch)) break;
         if(bull) { if(l[j] < pb_ext) pb_ext = l[j]; double g = l[j] - ema[j]; if(g < pb_gap) pb_gap = g; }
         else     { if(h[j] > pb_ext) pb_ext = h[j]; double g = ema[j] - h[j]; if(g < pb_gap) pb_gap = g; }

         bool brk = bull ? (h[j] > h[j - 1]) : (l[j] < l[j - 1]);

         if(brk && !h1_seen) { h1_seen = true; h1_ref = pb_ext; j++; continue; }
         if(h1_seen && !deeper)
            if((bull && pb_ext < h1_ref) || (!bull && pb_ext > h1_ref)) deeper = true;

         if(brk && h1_seen && deeper)
         {
            int imp = FvgImpulse(h, l, n, j, bull);
            if(imp >= 0 && TrendOK(ema, adx, j, bull) && pb_gap <= touch
               && QualityOK(o, h, l, c, j, bull))
            {
               double e, s, t, risk;
               if(bull) { e = h[j] + buffer; s = l[imp] - buffer; risk = e - s; t = e + InpRR * risk; }
               else     { e = l[j] - buffer; s = h[imp] + buffer; risk = s - e; t = e - InpRR * risk; }
               if(risk > 0)
               {
                  entry = e; stop = s; tp = t; sigbar = j; found = true;
               }
            }
            resolved = true; i = j + 1; break;
         }
         j++;
      }
      if(!resolved) i++;
   }
   return found;
}

//+------------------------------------------------------------------+
void OnNewBar()
{
   int n = InpLookbackBars;
   if(Bars(_Symbol, _Period) < n + 3) return;

   MqlRates rates[];
   double ema[], adx[];
   ArraySetAsSeries(rates, false);
   ArraySetAsSeries(ema, false);
   ArraySetAsSeries(adx, false);

   // closed bars only: start at shift 1
   if(CopyRates(_Symbol, _Period, 1, n, rates) < n) return;
   if(CopyBuffer(g_hEMA, 0, 1, n, ema) < n) return;
   if(CopyBuffer(g_hADX, 0, 1, n, adx) < n) return;   // buffer 0 = main ADX line

   double o[], h[], l[], c[];
   ArrayResize(o, n); ArrayResize(h, n); ArrayResize(l, n); ArrayResize(c, n);
   for(int k = 0; k < n; k++)
   { o[k] = rates[k].open; h[k] = rates[k].high; l[k] = rates[k].low; c[k] = rates[k].close; }

   double touch  = InpEmaTouchPoints * _Point;
   double buffer = InpBufferPoints   * _Point;

   double bE, bS, bT, sE, sS, sT;
   int bBar = -1, sBar = -1;
   bool gotBull = ScanDir(o, h, l, c, ema, adx, n, touch, buffer, true,  bE, bS, bT, bBar);
   bool gotBear = ScanDir(o, h, l, c, ema, adx, n, touch, buffer, false, sE, sS, sT, sBar);

   // only act on a signal confirmed on (or just before) the last closed bar
   int freshLimit = n - 3;
   if(gotBull && bBar >= freshLimit) TryPlace(true,  bE, bS, bT);
   if(gotBear && sBar >= freshLimit) TryPlace(false, sE, sS, sT);
}

//+------------------------------------------------------------------+
void TryPlace(bool bull, double entry, double stop, double tp)
{
   if(InpOnePerSide && HasOpenSide(bull)) return;

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) { PrintFormat("skip: spread %d > %d", spread, InpMaxSpreadPts); return; }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bull && entry <= ask) return;    // buy-stop must be above ask
   if(!bull && entry >= bid) return;   // sell-stop must be below bid

   double lots = LotForRisk(entry, stop);
   if(lots <= 0) return;

   int    dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   entry = NormalizeDouble(entry, dg);
   stop  = NormalizeDouble(stop,  dg);
   tp    = NormalizeDouble(tp,    dg);
   datetime expiry = TimeCurrent() + InpExpiryBars * PeriodSeconds(_Period);

   bool ok;
   if(bull) ok = g_trade.BuyStop(lots, entry, _Symbol, stop, tp, ORDER_TIME_SPECIFIED, expiry, "H2");
   else     ok = g_trade.SellStop(lots, entry, _Symbol, stop, tp, ORDER_TIME_SPECIFIED, expiry, "L2");

   if(!ok)
      PrintFormat("order failed %s: ret=%d %s", bull ? "BUY" : "SELL",
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
   else
      PrintFormat("%s stop placed: lots=%.2f entry=%.5f sl=%.5f tp=%.5f",
                  bull ? "BUY" : "SELL", lots, entry, stop, tp);
}

//+------------------------------------------------------------------+
double LotForRisk(double entry, double stop)
{
   double bal    = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMon = bal * InpRiskPercent / 100.0;
   double dist   = MathAbs(entry - stop);
   double tickSz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(dist <= 0 || tickSz <= 0 || tickVal <= 0) return 0;

   double riskPerLot = (dist / tickSz) * tickVal;
   if(riskPerLot <= 0) return 0;

   double lots = riskMon / riskPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = MathMax(InpMinLot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
   double vmax = MathMin(InpMaxLot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
   if(step > 0) lots = MathFloor(lots / step) * step;
   lots = MathMax(vmin, MathMin(vmax, lots));
   return lots;
}

//+------------------------------------------------------------------+
bool HasOpenSide(bool bull)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      if((bull && type == POSITION_TYPE_BUY) || (!bull && type == POSITION_TYPE_SELL)) return true;
   }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      long type = OrderGetInteger(ORDER_TYPE);
      if((bull && type == ORDER_TYPE_BUY_STOP) || (!bull && type == ORDER_TYPE_SELL_STOP)) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void ManageBreakEven()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      long   type = PositionGetInteger(POSITION_TYPE);
      double rDist = MathAbs(open - sl);
      if(rDist <= 0) continue;

      if(type == POSITION_TYPE_BUY)
      {
         if(sl < open && bid >= open + InpBreakEvenAtR * rDist)
            g_trade.PositionModify(tk, NormalizeDouble(open, _Digits), tp);
      }
      else
      {
         if(sl > open && ask <= open - InpBreakEvenAtR * rDist)
            g_trade.PositionModify(tk, NormalizeDouble(open, _Digits), tp);
      }
   }
}
//+------------------------------------------------------------------+
