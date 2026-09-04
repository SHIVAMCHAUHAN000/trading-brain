/**
 * Personal Live Quant Brain Frontend Application
 * Pure modern vanilla async JavaScript
 */

const API_BASE = "";
let activeSessionId = "web_session_" + Math.random().toString(36).substring(2, 9);
let currentInstrument = "NIFTY";
let currentTimeframe = "15m";
let chartInstance = null;
let candleSeries = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initChat();
    initWatchlist();
    loadMarketSummary();
    loadInstrumentDeepDive("NIFTY");
    loadConnections();
    loadHealth();

    // Auto-refresh summary every 20 seconds
    setInterval(() => {
        loadMarketSummary();
        loadHealth();
    }, 20000);
});

// --- Tab Navigation ---
function initNavigation() {
    const navButtons = document.querySelectorAll("[data-tab-target]");
    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.getAttribute("data-tab-target");
            
            // Update button states
            navButtons.forEach(b => {
                b.classList.remove("text-blue-400", "border-b-2", "border-blue-500", "bg-gray-800/60");
                b.classList.add("text-gray-400");
            });
            btn.classList.remove("text-gray-400");
            btn.classList.add("text-blue-400", "border-b-2", "border-blue-500", "bg-gray-800/60");

            // Switch view panels
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
            const activePanel = document.getElementById(target);
            if (activePanel) {
                activePanel.classList.remove("hidden");
                if (target === "deepdive-panel") {
                    if (currentChartMode === "tradingview") {
                        renderTradingViewWidget(currentInstrument, currentTimeframe);
                    } else if (chartInstance) {
                        setTimeout(() => {
                            const c = document.getElementById("chart-container");
                            if (c && chartInstance) {
                                chartInstance.applyOptions({ width: c.clientWidth || 800 });
                                chartInstance.timeScale().fitContent();
                            }
                        }, 60);
                    }
                }
            }
        });
    });
}

// --- Market Summary & Tickers ---
async function loadMarketSummary() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/market/summary`);
        if (!res.ok) {
            console.error("Market summary response error:", res.status, res.statusText);
            const container = document.getElementById("ticker-bar-container");
            if (container && (!container.children || container.innerText.includes("Connecting"))) {
                container.innerHTML = `<div class="text-xs text-amber-400 font-mono px-2 py-1 bg-amber-950/40 rounded border border-amber-800/40">⚠️ Feed returned HTTP ${res.status}. Reconnecting...</div>`;
            }
            return;
        }
        const data = await res.json();
        
        renderTickerBar(data.instruments || []);
        renderMarketGrid(data.instruments || []);
        renderMarketBreadth(data.breadth || {});
    } catch (e) {
        console.error("Failed to load market summary:", e);
        const container = document.getElementById("ticker-bar-container");
        if (container && (!container.children || container.innerText.includes("Connecting"))) {
            container.innerHTML = `<div class="text-xs text-rose-400 font-mono px-2 py-1 bg-rose-950/40 rounded border border-rose-800/40">⚠️ Network issue: ${e.message || 'Fetch failed'}. Retrying...</div>`;
        }
    }
}

let currentCurrencyDisplayMode = "native"; // "native" or "inr"
let lastMarketInstruments = [];
let lastUsdInrRate = 94.5;

function setCurrencyDisplayMode(mode) {
    currentCurrencyDisplayMode = mode;
    const nativeBtn = document.getElementById("currency-mode-native-btn");
    const inrBtn = document.getElementById("currency-mode-inr-btn");

    if (mode === "inr") {
        if (inrBtn) inrBtn.className = "px-2.5 py-1 rounded-lg bg-blue-600 text-white font-medium transition";
        if (nativeBtn) nativeBtn.className = "px-2.5 py-1 rounded-lg text-gray-400 hover:text-white transition";
    } else {
        if (nativeBtn) nativeBtn.className = "px-2.5 py-1 rounded-lg bg-blue-600 text-white font-medium transition";
        if (inrBtn) inrBtn.className = "px-2.5 py-1 rounded-lg text-gray-400 hover:text-white transition";
    }

    if (lastMarketInstruments && lastMarketInstruments.length > 0) {
        renderTickerBar(lastMarketInstruments);
        renderMarketGrid(lastMarketInstruments);
    }
    if (currentInstrument) {
        loadInstrumentDeepDive(currentInstrument);
    }
}

function getDomesticUnitLabel(symbol) {
    switch (symbol) {
        case "GOLD": return "per 10g (Domestic)";
        case "SILVER": return "per kg (Domestic)";
        case "CRUDEOIL": return "per bbl (Domestic)";
        case "BTC": return "INR est.";
        default: return "";
    }
}

function getNativeUnitLabel(symbol) {
    switch (symbol) {
        case "GOLD": return "/oz (COMEX USD)";
        case "SILVER": return "/oz (COMEX USD)";
        case "CRUDEOIL": return "/bbl (NYMEX WTI)";
        case "BTC": return "USD";
        case "NIFTY": case "BANKNIFTY": return "Index";
        default: return "INR";
    }
}

function computeDomesticInrPrice(symbol, priceUsd, usdinrRate) {
    if (!priceUsd || isNaN(priceUsd)) return null;
    const rate = usdinrRate || lastUsdInrRate || 94.5;
    const p = Number(priceUsd);
    if (symbol === "GOLD") {
        // 1 troy oz = 31.1034768 grams. Domestic standard quote is per 10 grams
        return (p / 31.1034768) * 10 * rate;
    } else if (symbol === "SILVER") {
        // Domestic standard quote is per 1 kg
        return (p / 31.1034768) * 1000 * rate;
    } else if (symbol === "CRUDEOIL") {
        // Domestic standard quote is per barrel in INR
        return p * rate;
    } else if (symbol === "BTC") {
        return p * rate;
    }
    return p;
}

function formatPriceDisplay(inst, forceInr = false) {
    if (!inst || inst.price === undefined || inst.price === null || isNaN(inst.price)) return "N/A";
    const isUsd = (inst.currency || "").toUpperCase() === "USD";
    const useInr = forceInr || (currentCurrencyDisplayMode === "inr");

    if (isUsd && useInr) {
        const inrVal = computeDomesticInrPrice(inst.symbol, inst.price, lastUsdInrRate);
        if (inrVal !== null) {
            const formatted = Math.round(inrVal).toLocaleString('en-IN');
            return `₹${formatted}`;
        }
    }

    const val = Number(inst.price);
    const sym = isUsd ? "$" : "₹";
    const locale = isUsd ? "en-US" : "en-IN";
    return `${sym}${val.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function renderTickerBar(instruments) {
    const container = document.getElementById("ticker-bar-container");
    if (!container) return;

    // Cache latest USDINR rate for conversions
    const usdinrInst = instruments.find(i => i.symbol === "USDINR");
    if (usdinrInst && usdinrInst.price) {
        lastUsdInrRate = Number(usdinrInst.price);
    }
    lastMarketInstruments = instruments;

    container.innerHTML = instruments.map(inst => {
        const isUp = (inst.change || 0) >= 0;
        const colorClass = isUp ? "text-emerald-400" : "text-rose-400";
        const sign = isUp ? "+" : "";
        const formattedPrice = formatPriceDisplay(inst);
        const unitSuffix = (currentCurrencyDisplayMode === "inr" && inst.currency === "USD")
            ? (inst.symbol === "GOLD" ? " /10g" : (inst.symbol === "SILVER" ? " /kg" : (inst.symbol === "CRUDEOIL" ? " /bbl" : "")))
            : "";
        return `
            <div class="ticker-pill flex items-center space-x-1.5 px-3 py-1.5 bg-gray-900/80 border border-gray-800 rounded-lg cursor-pointer text-xs flex-shrink-0 hover:border-blue-500/40 transition"
                 onclick="selectInstrument('${inst.symbol}')">
                <span class="font-bold text-gray-200">${inst.symbol}</span>
                <span class="font-mono text-gray-100 font-semibold">${formattedPrice}${unitSuffix}</span>
                <span class="font-mono ${colorClass}">${sign}${inst.change_pct}%</span>
            </div>
        `;
    }).join("");
}

function renderMarketGrid(instruments) {
    const grid = document.getElementById("market-cards-grid");
    if (!grid) return;

    grid.innerHTML = instruments.map(inst => {
        const isUp = (inst.change || 0) >= 0;
        const colorClass = isUp ? "text-emerald-400" : "text-rose-400";
        const sign = isUp ? "+" : "";
        const isOpen = inst.session_state === "OPEN";
        const badgeColor = isOpen ? "bg-emerald-950 text-emerald-300 border-emerald-800" : "bg-gray-800 text-gray-400 border-gray-700";
        const isUsd = (inst.currency || "").toUpperCase() === "USD";

        let displayPrice = formatPriceDisplay(inst);
        let currencySub = inst.currency;
        let domesticBadge = "";

        if (currentCurrencyDisplayMode === "inr") {
            if (isUsd) {
                currencySub = `INR (${getDomesticUnitLabel(inst.symbol)})`;
                const nativeVal = `$${Number(inst.price).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                domesticBadge = `<div class="text-[11px] text-gray-400 mt-0.5 font-mono">COMEX Ref: ${nativeVal} ${getNativeUnitLabel(inst.symbol)}</div>`;
            } else {
                currencySub = "INR";
            }
        } else {
            // Native mode
            if (isUsd) {
                currencySub = `${inst.currency} (${getNativeUnitLabel(inst.symbol)})`;
                const inrVal = computeDomesticInrPrice(inst.symbol, inst.price, lastUsdInrRate);
                if (inrVal) {
                    const inrFormatted = Math.round(inrVal).toLocaleString('en-IN');
                    const domUnit = getDomesticUnitLabel(inst.symbol);
                    domesticBadge = `<div class="text-[11px] text-amber-300/90 mt-0.5 font-mono">≈ ₹${inrFormatted} ${domUnit}</div>`;
                }
            } else {
                currencySub = "INR";
            }
        }

        return `
            <div class="glass-panel p-4 flex flex-col justify-between hover:border-blue-500/50 cursor-pointer transition"
                 onclick="selectInstrument('${inst.symbol}')">
                <div>
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <span class="font-bold text-lg text-white">${inst.symbol}</span>
                            <span class="block text-xs text-gray-400 truncate max-w-[140px]">${inst.name}</span>
                        </div>
                        <span class="text-[10px] px-2 py-0.5 rounded-full border ${badgeColor}">
                            ${inst.session_state}
                        </span>
                    </div>
                    <div class="my-2">
                        <div class="flex items-baseline space-x-2">
                            <span class="text-2xl font-bold font-mono text-white">${displayPrice}</span>
                            <span class="text-xs text-gray-400 font-mono">${currencySub}</span>
                        </div>
                        ${domesticBadge}
                    </div>
                    <div class="flex items-center space-x-2 text-sm font-mono ${colorClass}">
                        <span>${sign}${inst.change}</span>
                        <span>(${sign}${inst.change_pct}%)</span>
                    </div>
                </div>
                <div class="mt-4 pt-2 border-t border-gray-800/80 flex justify-between items-center text-xs text-gray-400">
                    <span>H: ${inst.high || '-'} | L: ${inst.low || '-'}</span>
                    <button class="px-2 py-1 bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white rounded transition text-[11px]"
                            onclick="event.stopPropagation(); sendPromptToChat('Analyze ${inst.symbol}')">
                        Ask Quant
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

function renderMarketBreadth(breadth) {
    const container = document.getElementById("breadth-widget");
    if (!container) return;

    const adv = breadth.advances || 0;
    const dec = breadth.declines || 0;
    const ratio = breadth.adv_dec_ratio || 1.0;
    const total = adv + dec || 1;
    const advPct = Math.round((adv / total) * 100);

    container.innerHTML = `
        <div class="flex justify-between items-center text-xs mb-1">
            <span class="text-emerald-400 font-bold">${adv} Advances</span>
            <span class="text-gray-400 font-mono">A/D: ${ratio}</span>
            <span class="text-rose-400 font-bold">${dec} Declines</span>
        </div>
        <div class="w-full h-2 bg-gray-800 rounded-full overflow-hidden flex">
            <div class="h-full bg-emerald-500" style="width: ${advPct}%"></div>
            <div class="h-full bg-rose-500" style="width: ${100 - advPct}%"></div>
        </div>
        <div class="text-[11px] text-gray-400 mt-1 truncate">
            Sentiment: <span class="text-gray-200 font-medium">${breadth.sentiment || 'Neutral'}</span>
        </div>
    `;
}

// --- Deep Dive View & Charts ---
async function selectInstrument(symbol) {
    currentInstrument = symbol;
    
    // Switch tab to deep dive
    const deepDiveBtn = document.querySelector("[data-tab-target='deepdive-panel']");
    if (deepDiveBtn) deepDiveBtn.click();

    await loadInstrumentDeepDive(symbol);
}

async function loadInstrumentDeepDive(symbol) {
    currentInstrument = symbol;
    const headerTitle = document.getElementById("deepdive-symbol-title");
    if (headerTitle) headerTitle.innerText = `${symbol} Deep Dive`;

    try {
        // Load analysis and candles concurrently
        const [analysisRes, candlesRes] = await Promise.all([
            fetch(`${API_BASE}/api/v1/market/instrument/${symbol}?timeframe=${currentTimeframe}`),
            fetch(`${API_BASE}/api/v1/market/candles/${symbol}?interval=${currentTimeframe}`)
        ]);

        if (analysisRes.ok) {
            const data = await analysisRes.json();
            renderDeepDiveMetrics(data);
        }

        if (candlesRes.ok) {
            const candleData = await candlesRes.json();
            lastCandleData = candleData.candles || [];
            if (currentChartMode === "tradingview") {
                renderTradingViewWidget(symbol, currentTimeframe);
            } else {
                renderCandleChart(lastCandleData);
            }
        }
    } catch (e) {
        console.error("Error loading instrument deep dive:", e);
    }
}

function renderDeepDiveMetrics(data) {
    const q = data.quote || {};
    const s = data.structure || {};
    const l = data.liquidity || {};
    const m = data.momentum || {};
    const v = data.volume || {};
    const vol = data.volatility || {};
    const setup = data.setup || {};

    // Top metrics
    const priceEl = document.getElementById("dd-price");
    if (priceEl) {
        priceEl.innerText = formatPriceDisplay(q);
    }

    const domesticEl = document.getElementById("dd-domestic-equiv");
    if (domesticEl) {
        const isUsd = (q.currency || "").toUpperCase() === "USD";
        if (isUsd) {
            const inrVal = computeDomesticInrPrice(q.symbol, q.price, lastUsdInrRate);
            if (inrVal) {
                const inrFormatted = Math.round(inrVal).toLocaleString('en-IN');
                const domUnit = getDomesticUnitLabel(q.symbol);
                domesticEl.innerText = `≈ ₹${inrFormatted} ${domUnit}`;
                domesticEl.classList.remove("hidden");
            } else {
                domesticEl.classList.add("hidden");
            }
        } else {
            domesticEl.classList.add("hidden");
        }
    }

    const chgEl = document.getElementById("dd-change");
    if (chgEl) {
        const sign = (q.change || 0) >= 0 ? "+" : "";
        chgEl.innerText = `${sign}${q.change || 0} (${sign}${q.change_pct || 0}%)`;
        chgEl.className = (q.change || 0) >= 0 ? "text-emerald-400 font-mono" : "text-rose-400 font-mono";
    }

    const regimeEl = document.getElementById("dd-regime");
    if (regimeEl) regimeEl.innerText = s.regime || "RANGE";

    const rsiEl = document.getElementById("dd-rsi");
    if (rsiEl) rsiEl.innerText = `RSI: ${m.rsi || 50} (${m.rsi_state || 'Neutral'})`;

    const rvolEl = document.getElementById("dd-rvol");
    if (rvolEl) rvolEl.innerText = `RVOL: ${v.rvol || 1.0}x (${v.state || 'Average'})`;

    const atrEl = document.getElementById("dd-atr");
    if (atrEl) atrEl.innerText = `ATR: ${vol.atr || 'N/A'} (${vol.regime || 'Normal'})`;

    // Liquidity Pools
    const lqContainer = document.getElementById("dd-liquidity-pools");
    if (lqContainer) {
        const upside = (l.upside_liquidity || []).map(p => `
            <div class="flex justify-between items-center py-1 text-xs border-b border-gray-800/50">
                <span class="text-emerald-400 font-mono">${p.level}</span>
                <span class="text-gray-400">${p.type}</span>
                <span class="text-gray-500 font-mono">+${p.distance_pct}%</span>
            </div>
        `).join("") || "<p class='text-xs text-gray-500'>No immediate overhead pools</p>";

        const downside = (l.downside_liquidity || []).map(p => `
            <div class="flex justify-between items-center py-1 text-xs border-b border-gray-800/50">
                <span class="text-rose-400 font-mono">${p.level}</span>
                <span class="text-gray-400">${p.type}</span>
                <span class="text-gray-500 font-mono">-${p.distance_pct}%</span>
            </div>
        `).join("") || "<p class='text-xs text-gray-500'>No immediate downside pools</p>";

        lqContainer.innerHTML = `
            <div class="mb-2">
                <span class="text-[11px] uppercase tracking-wider text-gray-400 font-semibold">Overhead Buy-Stops</span>
                ${upside}
            </div>
            <div>
                <span class="text-[11px] uppercase tracking-wider text-gray-400 font-semibold">Downside Sell-Stops</span>
                ${downside}
            </div>
        `;
    }

    // Setup Status
    const setupContainer = document.getElementById("dd-setup-box");
    if (setupContainer) {
        const badgeColor = setup.direction === "Long bias" ? "text-emerald-400 border-emerald-800" :
                           (setup.direction === "Short bias" ? "text-rose-400 border-rose-800" : "text-gray-400 border-gray-800");
        setupContainer.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <span class="font-bold text-white text-sm">Setup: ${setup.status || 'No setup'}</span>
                <span class="px-2 py-0.5 rounded text-xs border ${badgeColor}">${setup.direction || 'Neutral'}</span>
            </div>
            <p class="text-xs text-gray-300 mb-1"><strong>Trigger:</strong> ${setup.trigger || 'N/A'}</p>
            <p class="text-xs text-gray-400 mb-1"><strong>Invalidation:</strong> ${setup.invalidation || 'N/A'}</p>
            <p class="text-xs text-gray-400"><strong>Confidence:</strong> ${setup.confidence || 'Low'} (${setup.confidence_reason || ''})</p>
        `;
    }
}

let currentChartMode = "tradingview"; // "tradingview" or "quant"
let lastCandleData = [];
let chartResizeObserver = null;

function switchChartMode(mode) {
    currentChartMode = mode;
    const tvBox = document.getElementById("tradingview-chart-box");
    const quantBox = document.getElementById("chart-container");
    const tvBtn = document.getElementById("chart-mode-tv-btn");
    const quantBtn = document.getElementById("chart-mode-quant-btn");

    if (mode === "tradingview") {
        if (tvBox) tvBox.classList.remove("hidden");
        if (quantBox) quantBox.classList.add("hidden");
        if (tvBtn) tvBtn.className = "px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition flex items-center space-x-1";
        if (quantBtn) quantBtn.className = "px-2.5 py-1 rounded bg-gray-800 text-gray-400 hover:text-white transition flex items-center space-x-1";
        renderTradingViewWidget(currentInstrument, currentTimeframe);
    } else {
        if (tvBox) tvBox.classList.add("hidden");
        if (quantBox) quantBox.classList.remove("hidden");
        if (tvBtn) tvBtn.className = "px-2.5 py-1 rounded bg-gray-800 text-gray-400 hover:text-white transition flex items-center space-x-1";
        if (quantBtn) quantBtn.className = "px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition flex items-center space-x-1";
        if (lastCandleData && lastCandleData.length > 0) {
            renderCandleChart(lastCandleData);
        }
    }
}

function getTradingViewSymbol(symbol) {
    const s = (symbol || "").toUpperCase();
    const map = {
        "NIFTY": "NSE:NIFTY",
        "BANKNIFTY": "NSE:BANKNIFTY",
        "RELIANCE": "NSE:RELIANCE",
        "HDFCBANK": "NSE:HDFCBANK",
        "ICICIBANK": "NSE:ICICIBANK",
        "INFY": "NSE:INFY",
        "TCS": "NSE:TCS",
        "GOLD": "TVC:GOLD",
        "SILVER": "TVC:SILVER",
        "CRUDEOIL": "TVC:USOIL",
        "BTC": "BINANCE:BTCUSDT",
        "USDINR": "FX_IDC:USDINR",
    };
    return map[s] || `NSE:${s}`;
}

function getTradingViewInterval(tf) {
    const map = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "1d": "D",
    };
    return map[tf] || "15";
}

function renderTradingViewWidget(symbol, tf) {
    const container = document.getElementById("tradingview-chart-box");
    if (!container) return;

    const tvSymbol = getTradingViewSymbol(symbol);
    const tvInterval = getTradingViewInterval(tf);

    const badge = document.getElementById("chart-active-symbol-badge");
    if (badge) badge.innerText = `${symbol} (${tvSymbol})`;

    // Check if official tv.js library loaded
    if (window.TradingView && typeof window.TradingView.widget === "function") {
        container.innerHTML = `<div id="tv_chart_inner" class="w-full h-full" style="min-height: 450px;"></div>`;
        try {
            new window.TradingView.widget({
                autosize: true,
                symbol: tvSymbol,
                interval: tvInterval,
                timezone: "Asia/Kolkata",
                theme: "dark",
                style: "1",
                locale: "en",
                toolbar_bg: "#0d131f",
                enable_publishing: false,
                hide_top_toolbar: false,
                hide_legend: false,
                save_image: false,
                container_id: "tv_chart_inner",
            });
            return;
        } catch (err) {
            console.warn("TradingView widget init error, falling back to iframe embed:", err);
        }
    }

    // High-reliability iframe embed (works in all browsers, immune to CDN/adblock script blocks)
    container.innerHTML = `
        <iframe 
            id="tradingview_iframe"
            src="https://www.tradingview.com/widgetembed/?symbol=${encodeURIComponent(tvSymbol)}&interval=${tvInterval}&theme=dark&style=1&timezone=Asia%2FKolkata&locale=en" 
            class="w-full h-full border-0 rounded-lg" 
            style="width: 100%; height: 100%; min-height: 450px;"
            allowfullscreen>
        </iframe>
    `;
}

function renderCandleChart(candles) {
    lastCandleData = candles || [];
    const container = document.getElementById("chart-container");
    if (!container) return;

    container.innerHTML = "";
    const containerWidth = container.clientWidth || container.parentElement?.clientWidth || 800;

    // If Lightweight Charts library is loaded from CDN
    if (window.LightweightCharts) {
        chartInstance = LightweightCharts.createChart(container, {
            width: containerWidth,
            height: 450,
            layout: {
                background: { color: "#0d131f" },
                textColor: "#9ca3af",
            },
            grid: {
                vertLines: { color: "rgba(255, 255, 255, 0.04)" },
                horzLines: { color: "rgba(255, 255, 255, 0.04)" },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: "rgba(255, 255, 255, 0.1)",
            },
            timeScale: {
                borderColor: "rgba(255, 255, 255, 0.1)",
                timeVisible: true,
            },
        });

        candleSeries = chartInstance.addCandlestickSeries({
            upColor: "#10b981",
            downColor: "#ef4444",
            borderDownColor: "#ef4444",
            borderUpColor: "#10b981",
            wickDownColor: "#ef4444",
            wickUpColor: "#10b981",
        });

        const formatted = (candles || []).map(c => ({
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

        if (formatted.length > 0) {
            candleSeries.setData(formatted);
            chartInstance.timeScale().fitContent();
        }

        // Setup ResizeObserver for responsive layout and tab switches
        if (!chartResizeObserver && window.ResizeObserver) {
            chartResizeObserver = new ResizeObserver((entries) => {
                for (let entry of entries) {
                    const width = entry.contentRect.width;
                    if (width > 0 && chartInstance) {
                        chartInstance.applyOptions({ width: width });
                        chartInstance.timeScale().fitContent();
                    }
                }
            });
            chartResizeObserver.observe(container);
        }
    } else {
        container.innerHTML = `
            <div class="h-full flex items-center justify-center text-gray-500 text-sm">
                <p>Interactive chart active (${(candles || []).length} candles loaded)</p>
            </div>
        `;
    }
}

function changeTimeframe(tf) {
    currentTimeframe = tf;
    document.querySelectorAll(".tf-btn").forEach(btn => {
        if (btn.innerText.toLowerCase() === tf.toLowerCase()) {
            btn.classList.add("bg-blue-600", "text-white");
            btn.classList.remove("bg-gray-800", "text-gray-400");
        } else {
            btn.classList.remove("bg-blue-600", "text-white");
            btn.classList.add("bg-gray-800", "text-gray-400");
        }
    });
    loadInstrumentDeepDive(currentInstrument);
}

// --- AI Quant Chat ---
function initChat() {
    const input = document.getElementById("chat-input");
    const sendBtn = document.getElementById("chat-send-btn");

    if (sendBtn && input) {
        sendBtn.addEventListener("click", () => handleSendMessage());
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }
}

function sendPromptToChat(promptText) {
    const chatBtn = document.querySelector("[data-tab-target='chat-panel']");
    if (chatBtn) chatBtn.click();

    const input = document.getElementById("chat-input");
    if (input) {
        input.value = promptText;
        handleSendMessage();
    }
}

async function handleSendMessage() {
    const input = document.getElementById("chat-input");
    const text = input ? input.value.trim() : "";
    if (!text) return;

    input.value = "";
    appendChatMessage("user", text);

    // Typing indicator
    const typingId = appendTypingIndicator();

    try {
        const res = await fetch(`${API_BASE}/api/v1/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                session_id: activeSessionId,
                channel: "web",
            }),
        });

        removeTypingIndicator(typingId);

        if (!res.ok) {
            appendChatMessage("assistant", "⚠️ Error processing question. Please try again.");
            return;
        }

        const data = await res.json();
        appendChatMessage("assistant", data.response, data.tools_called, data.latency_ms, data.engine);
    } catch (e) {
        removeTypingIndicator(typingId);
        appendChatMessage("assistant", `⚠️ Network error: ${e.message}`);
    }
}

function appendChatMessage(role, content, tools = [], latency = null, engine = null) {
    const container = document.getElementById("chat-messages-container");
    if (!container) return;

    const div = document.createElement("div");
    div.className = `flex flex-col ${role === "user" ? "items-end" : "items-start"} mb-4`;

    const formattedContent = content
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/\n/g, "<br/>");

    let badgeStyle = "bg-blue-950/70 text-blue-300 border-blue-700/60";
    if (engine && engine.includes("Quota Exhausted")) {
        badgeStyle = "bg-amber-950/80 text-amber-300 border-amber-700/80";
    } else if (engine && engine.startsWith("OpenAI")) {
        badgeStyle = "bg-emerald-950/70 text-emerald-300 border-emerald-700/60";
    } else if (engine && engine.startsWith("Google Gemini")) {
        badgeStyle = "bg-purple-950/70 text-purple-300 border-purple-700/60";
    }

    const engineBadge = engine
        ? `<span class="px-1.5 py-0.5 ${badgeStyle} rounded border text-[10px] font-mono font-medium">${engine}</span>`
        : '';

    const toolsBadge = ((tools && tools.length > 0) || engine)
        ? `<div class="mt-2 text-[10px] text-gray-400 flex flex-wrap items-center gap-1.5">
             ${engineBadge}
             ${(tools && tools.length > 0) ? `<span class="text-gray-500">Tools:</span>${tools.map(t => `<span class="px-1.5 py-0.5 bg-gray-800 rounded border border-gray-700">${t}</span>`).join("")}` : ''}
             ${latency ? `<span class="text-blue-400 font-mono">(${latency}ms)</span>` : ''}
           </div>`
        : '';

    div.innerHTML = `
        <div class="max-w-[85%] md:max-w-[75%] p-3.5 ${role === "user" ? "chat-user text-white" : "chat-assistant text-gray-200"}">
            <div class="text-sm leading-relaxed">${formattedContent}</div>
            ${toolsBadge}
        </div>
        <span class="text-[10px] text-gray-500 mt-1 px-1">${role === 'user' ? 'You' : (engine ? `Live Quant Brain • <span class="text-blue-400">${engine}</span>` : 'Live Quant Brain')}</span>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function appendTypingIndicator() {
    const container = document.getElementById("chat-messages-container");
    if (!container) return null;

    const id = "typing_" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "flex flex-col items-start mb-4";
    div.innerHTML = `
        <div class="chat-assistant p-3 rounded-xl flex items-center space-x-1.5">
            <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></span>
            <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
            <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
            <span class="text-xs text-gray-400 ml-2 font-mono">Quant Brain analyzing...</span>
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.remove();
}

// --- Watchlist ---
async function initWatchlist() {
    loadWatchlist();
    const addBtn = document.getElementById("add-watchlist-btn");
    const input = document.getElementById("add-watchlist-input");

    if (addBtn && input) {
        addBtn.addEventListener("click", async () => {
            const sym = input.value.trim().toUpperCase();
            if (!sym) return;
            await fetch(`${API_BASE}/api/v1/market/watchlist`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ symbol: sym }),
            });
            input.value = "";
            loadWatchlist();
        });
    }
}

async function loadWatchlist() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/market/watchlist`);
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById("watchlist-table-body");
        if (!container) return;

        container.innerHTML = (data.watchlist || []).map(item => {
            const isUp = (item.change_pct || 0) >= 0;
            const sign = isUp ? "+" : "";
            const colorClass = isUp ? "text-emerald-400" : "text-rose-400";
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800/40 cursor-pointer" onclick="selectInstrument('${item.symbol}')">
                    <td class="py-3 px-4 font-bold text-white">${item.symbol}</td>
                    <td class="py-3 px-4 font-mono font-medium text-gray-200">${formatPriceDisplay(item)}</td>
                    <td class="py-3 px-4 font-mono ${colorClass}">${sign}${item.change_pct || 0}%</td>
                    <td class="py-3 px-4 text-xs text-gray-400">${item.freshness?.status || 'CONNECTED'}</td>
                    <td class="py-3 px-4 text-right">
                        <button class="text-rose-400 hover:text-rose-300 text-xs px-2 py-1 rounded"
                                onclick="event.stopPropagation(); removeFromWatchlist('${item.symbol}')">
                            Remove
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (e) {
        console.error("Failed to load watchlist:", e);
    }
}

async function removeFromWatchlist(symbol) {
    await fetch(`${API_BASE}/api/v1/market/watchlist/${symbol}`, { method: "DELETE" });
    loadWatchlist();
}

// --- Connections & Health ---
async function loadConnections() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/connections`);
        if (!res.ok) return;
        const data = await res.json();

        // Render MCP tools table
        const mcpTable = document.getElementById("mcp-tools-table");
        if (mcpTable) {
            mcpTable.innerHTML = (data.mcp_tools?.tools || []).map(t => `
                <tr class="border-b border-gray-800 text-xs">
                    <td class="py-2.5 px-3 font-mono text-blue-400 font-semibold">${t.name}</td>
                    <td class="py-2.5 px-3 text-gray-300">${t.description}</td>
                    <td class="py-2.5 px-3 text-center">
                        <span class="px-2 py-0.5 rounded-full text-[10px] ${t.is_active ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-gray-800 text-gray-400'}">
                            ${t.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                    </td>
                    <td class="py-2.5 px-3 font-mono text-right text-gray-300">${t.total_calls}</td>
                    <td class="py-2.5 px-3 font-mono text-right text-gray-400">${t.last_latency_ms}ms</td>
                </tr>
            `).join("");
        }

        // Telegram status
        const tgEl = document.getElementById("tg-status-desc");
        if (tgEl) tgEl.innerText = data.telegram?.status || "Unknown";

        // Market data status
        const mdEl = document.getElementById("md-status-desc");
        if (mdEl) mdEl.innerText = `${data.market_data?.primary_provider || 'Connected'} (${data.market_data?.status || 'OK'})`;

        // TradingView status
        const tvEl = document.getElementById("tv-status-desc");
        if (tvEl) tvEl.innerText = `Webhook active on ${data.tradingview?.webhook_endpoint || '/webhook'}`;

        // AI Engine
        const aiEl = document.getElementById("ai-status-desc");
        if (aiEl) {
            const engineInfo = `Provider: ${data.ai_engine?.provider} (Model: ${data.ai_engine?.model || 'Deterministic'})`;
            if (data.ai_engine?.quota_notice) {
                aiEl.innerHTML = `<span class="text-amber-300 font-medium">${engineInfo}</span><br/><span class="text-[10px] text-amber-400 font-mono">⚠️ ${data.ai_engine.quota_notice}</span>`;
            } else {
                aiEl.innerText = engineInfo;
            }
        }
    } catch (e) {
        console.error("Failed to load connections:", e);
    }
}

async function loadHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/health`);
        if (!res.ok) return;
        const h = await res.json();

        const badge = document.getElementById("system-health-badge");
        if (badge) {
            badge.innerText = h.status;
            badge.className = h.status === "HEALTHY"
                ? "text-xs px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center space-x-1"
                : "text-xs px-2.5 py-1 rounded-full bg-amber-950 text-amber-300 border border-amber-800 flex items-center space-x-1";
        }

        const uptimeEl = document.getElementById("uptime-stat");
        if (uptimeEl) {
            const hrs = Math.floor(h.uptime_seconds / 3600);
            const mins = Math.floor((h.uptime_seconds % 3600) / 60);
            const secs = Math.floor(h.uptime_seconds % 60);
            uptimeEl.innerText = `${hrs}h ${mins}m ${secs}s`;
        }

        const memEl = document.getElementById("memory-stat");
        if (memEl) memEl.innerText = `${h.memory_usage_mb} MB`;
    } catch (e) {
        console.error("Failed to load health:", e);
    }
}
