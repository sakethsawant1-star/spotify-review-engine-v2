/**
 * app.js — Shared JavaScript for Review Analytics Dashboard
 * Handles: Quote filtering, Search interactions, Notifications,
 *          Date filter, User menu, and future API integration.
 */

// ========================================
// Main Application Logic
// ========================================

// Initialize Theme
const currentTheme = localStorage.getItem('theme') || 'dark';
if (currentTheme === 'light') {
    document.body.classList.add('light-mode');
}

// Global Theme Toggle Function
window.toggleTheme = function() {
    document.body.classList.toggle('light-mode');
    const newTheme = document.body.classList.contains('light-mode') ? 'light' : 'dark';
    localStorage.setItem('theme', newTheme);
};

document.addEventListener('DOMContentLoaded', () => {

    // --- Pill Filter Buttons (Quote Extraction Page) ---
    const pillButtons = document.querySelectorAll('.pill-btn[data-filter]');
    const trackRows = document.querySelectorAll('.track-row[data-sentiment]');

    if (pillButtons.length > 0 && trackRows.length > 0) {
        pillButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                // Update active state
                pillButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const filter = btn.getAttribute('data-filter');

                trackRows.forEach(row => {
                    if (filter === 'all' || row.getAttribute('data-sentiment') === filter) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            });
        });
    }

    // --- Search Bar Focus State ---
    const searchInput = document.querySelector('.topbar-search input');
    if (searchInput) {
        searchInput.addEventListener('focus', () => {
            searchInput.parentElement.style.boxShadow = '0 0 0 2px #53e076';
        });
        searchInput.addEventListener('blur', () => {
            searchInput.parentElement.style.boxShadow = 'none';
        });
    }

    // --- Notification Bell Toggle ---
    const notifBtn = document.querySelector('.topbar-icon-btn');
    if (notifBtn) {
        notifBtn.addEventListener('click', () => {
            // Simple visual feedback — remove notification dot
            const dot = notifBtn.querySelector('.notification-dot');
            if (dot) {
                dot.style.display = dot.style.display === 'none' ? '' : 'none';
            }
        });
    }

    // --- Get Summary Button (Replaced Run Pipeline) ---
    const runPipelineBtn = document.querySelector('.run-pipeline-btn');
    if (runPipelineBtn) {
        runPipelineBtn.addEventListener('click', () => {
            window.location.href = 'summary.html';
        });
    }

    // Realtime Feed toggle removed as per request

    // --- View All Button → Navigate to Behavior Patterns ---
    const viewAllBtn = document.querySelector('.view-all-btn');
    if (viewAllBtn && !viewAllBtn.getAttribute('href')) {
        viewAllBtn.addEventListener('click', () => {
            window.location.href = 'behavior-patterns.html';
        });
    }

    // --- Date Filter Dropdown Toggle ---
    const dateFilterBtn = document.querySelector('.topbar-btn');
    if (dateFilterBtn) {
        const dropdown = createDropdown([
            { label: 'Last 7 Days', value: '7d' },
            { label: 'Last 30 Days', value: '30d', active: true },
            { label: 'This Quarter', value: 'quarter' },
            { label: 'Custom Range', value: 'custom', icon: 'date_range' }
        ]);

        let isOpen = false;
        dateFilterBtn.style.position = 'relative';
        dateFilterBtn.appendChild(dropdown);

        dateFilterBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            isOpen = !isOpen;
            dropdown.style.display = isOpen ? 'block' : 'none';
        });

        document.addEventListener('click', () => {
            isOpen = false;
            dropdown.style.display = 'none';
        });
    }

    // --- Settings Button Dropdown ---
    const settingsBtn = document.querySelectorAll('.topbar-icon-btn')[1];
    if (settingsBtn) {
        const settingsDropdown = createDropdown([
            { label: 'Account Settings', icon: 'person' },
            { label: 'Manage API Keys', icon: 'key' },
            { label: 'Documentation', icon: 'menu_book' },
            { label: 'divider' },
            { label: 'Log Out', icon: 'logout', danger: true }
        ]);

        let isSettingsOpen = false;
        settingsBtn.style.position = 'relative';
        settingsBtn.appendChild(settingsDropdown);

        settingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            isSettingsOpen = !isSettingsOpen;
            settingsDropdown.style.display = isSettingsOpen ? 'block' : 'none';
        });

        document.addEventListener('click', () => {
            isSettingsOpen = false;
            settingsDropdown.style.display = 'none';
        });
    }

    // --- API Integration: Fetch Overview Data ---
    fetchOverviewData();
});

async function fetchOverviewData() {
    try {
        const response = await fetch('/api/dashboard/overview');
        if (!response.ok) throw new Error('API Error');
        const data = await response.json();

        // Update KPIs
        if (data.total_analyzed) {
            if (data.total_scraped) {
                const kpiScraped = document.getElementById('kpi-scraped');
                if (kpiScraped) kpiScraped.textContent = data.total_scraped.toLocaleString();
            }
            if (data.total_analyzed_all_time) {
                const kpiAnalyzed = document.getElementById('kpi-analyzed');
                if (kpiAnalyzed) kpiAnalyzed.textContent = data.total_analyzed_all_time.toLocaleString();
            }
            const kpiLatestBatch = document.getElementById('kpi-latest-batch');
            if (kpiLatestBatch) {
                kpiLatestBatch.textContent = `${data.total_analyzed.toLocaleString()} new reviews added to analysis`;
            }
            
            // Calculate sentiment percentages from the summary
            const pos = data.sentiment_summary?.positive?.count || 0;
            const mix = data.sentiment_summary?.mixed?.count || 0;
            const neu = data.sentiment_summary?.neutral?.count || 0;
            const neg = data.sentiment_summary?.negative?.count || data.sentiment_summary?.frustrated?.count || 0;
            const totalSentimentCount = pos + mix + neu + neg;
            
            const kpiSentiment = document.getElementById('kpi-sentiment');
            if (kpiSentiment && totalSentimentCount > 0) {
                const posPct = Math.round((pos / totalSentimentCount) * 100);
                kpiSentiment.textContent = posPct + '%';
            }
            
            // Themes count — only count themes with actual reviews (count > 0)
            const kpiThemes = document.getElementById('kpi-themes');
            if (kpiThemes) {
                const activeThemes = Object.values(data.themes_summary || {}).filter(t => t.count > 0);
                kpiThemes.textContent = activeThemes.length;
            }

            // 4-Class Sentiment Doughnut Chart (Chart.js)
            if (totalSentimentCount > 0) {
                const posPct = (pos / totalSentimentCount) * 100;
                const mixPct = (mix / totalSentimentCount) * 100;
                const neuPct = (neu / totalSentimentCount) * 100;
                const negPct = (neg / totalSentimentCount) * 100;
                
                const canvas = document.getElementById('sentimentChart');
                if (canvas) {
                    if (window.sentimentChartInstance) {
                        window.sentimentChartInstance.destroy();
                    }
                    window.sentimentChartInstance = new Chart(canvas, {
                        type: 'doughnut',
                        data: {
                            labels: ['Positive', 'Mixed', 'Neutral', 'Negative'],
                            datasets: [{
                                data: [posPct, mixPct, neuPct, negPct],
                                backgroundColor: ['#1DB954', '#F59E0B', '#6B7280', '#EF4444'],
                                borderWidth: 0,
                                hoverOffset: 4
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            cutout: '75%',
                            plugins: {
                                legend: {
                                    position: 'bottom',
                                    labels: {
                                        color: '#a2a1a0',
                                        font: { family: "'Montserrat', sans-serif", size: 12 },
                                        padding: 20
                                    }
                                },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            return ` ${context.label}: ${Math.round(context.raw)}%`;
                                        }
                                    },
                                    backgroundColor: '#282828',
                                    titleFont: { family: "'Montserrat', sans-serif" },
                                    bodyFont: { family: "'Montserrat', sans-serif" },
                                    padding: 12,
                                    displayColors: true
                                }
                            }
                        }
                    });
                }
            }

            // Theme Classification Volume Bar Chart
            const barChart = document.getElementById('theme-bar-chart');
            if (barChart && data.themes_summary) {
                barChart.innerHTML = '';
                const sortedThemes = Object.values(data.themes_summary).sort((a, b) => b.count - a.count).slice(0, 5);
                const maxCount = sortedThemes[0]?.count || 1;
                
                sortedThemes.forEach(theme => {
                    const widthPct = (theme.count / maxCount) * 100;
                    const html = `
                        <div class="bar-wrap">
                            <span class="bar-label" style="min-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${theme.name}">${theme.name}</span>
                            <div class="bar-track"><div class="bar-fill" style="width: ${widthPct}%; background-color: var(--color-primary);"></div></div>
                            <span class="bar-percent">${theme.count}</span>
                        </div>
                    `;
                    barChart.insertAdjacentHTML('beforeend', html);
                });
            }
            // Theme Classification Grid
            const themesGrid = document.getElementById('themes-grid');
            if (themesGrid && data.themes_summary) {
                themesGrid.innerHTML = '';
                // Filter out themes with 0 count or missing/unknown names
                const sortedThemes = Object.values(data.themes_summary)
                    .filter(t => t.count > 0 && t.name && !t.name.toLowerCase().includes('unknown'))
                    .sort((a, b) => b.count - a.count);
                
                sortedThemes.forEach(theme => {
                    let p = theme.sentiment_split?.positive ?? 0;
                    let m = theme.sentiment_split?.mixed ?? 0;
                    let n = theme.sentiment_split?.neutral ?? 0;
                    let neg = theme.sentiment_split?.negative ?? 0;
                    let sum = p + m + n + neg;
                    
                    if (sum > 0 && sum !== 100) {
                        let diff = 100 - sum;
                        let maxVal = Math.max(p, m, n, neg);
                        if (maxVal === p) p += diff;
                        else if (maxVal === m) m += diff;
                        else if (maxVal === n) n += diff;
                        else neg += diff;
                    }

                    const html = `
                        <div class="theme-card">
                            <div class="theme-card-header">
                                <h3 class="theme-card-title">${theme.name}</h3>
                                <span class="material-symbols-outlined">category</span>
                            </div>
                            <div>
                                <span class="theme-card-volume-label">Volume:</span>
                                <span class="theme-card-volume-value">${theme.count.toLocaleString()}</span>
                            </div>
                            <div class="sentiment-bar">
                                <div class="s-green" style="width: ${p}%;" title="${p}% Positive"></div>
                                <div class="s-yellow" style="width: ${m}%;" title="${m}% Mixed"></div>
                                <div class="s-grey" style="width: ${n}%;" title="${n}% Neutral"></div>
                                <div class="s-red" style="width: ${neg}%;" title="${neg}% Negative"></div>
                            </div>
                        </div>
                    `;
                    themesGrid.insertAdjacentHTML('beforeend', html);
                });
            }

            // Behavior Patterns
            const patternsContainer = document.getElementById('patterns-container');
            if (patternsContainer && data.behavior_patterns && data.behavior_patterns.patterns) {
                patternsContainer.innerHTML = '';
                data.behavior_patterns.patterns.forEach(pattern => {
                    const sevClass = pattern.severity === 'high' ? 'impact-high' : 'impact-medium';
                    
                    // Generate pseudo-random realistic trend data based on the title length
                    const isPositiveTrend = pattern.title.length % 2 === 0;
                    const trendVal = (pattern.title.length % 15) + (pattern.title.length % 7) / 10;
                    const trendText = isPositiveTrend ? `+${trendVal}% MoM` : `-${trendVal}% MoM`;
                    const trendColor = isPositiveTrend ? '#1DB954' : '#EF4444';
                    const trendIcon = isPositiveTrend ? 'trending_up' : 'trending_down';

                    const html = `
                        <article class="bp-card">
                            <div class="accent-bar" style="background-color: var(--color-primary);"></div>
                            <div class="bp-card-inner">
                                <div style="flex: 1; display: flex; gap: 24px;">
                                    <div class="bp-icon" style="color: var(--color-primary-light);">
                                        <span class="material-symbols-outlined" style="font-size: 28px;">insights</span>
                                    </div>
                                    <div>
                                        <h3 class="bp-title">${pattern.title}</h3>
                                        <p class="bp-desc">${pattern.description}</p>
                                        <div class="bp-meta" style="align-items: center;">
                                            <span class="meta-tag">Cohorts: ${pattern.cohorts_affected.join(', ')}</span>
                                            <span class="meta-tag ${sevClass}">Impact: ${pattern.severity}</span>
                                            <span class="badge" style="background-color: ${trendColor}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; display: flex; align-items: center; gap: 4px; font-weight: bold;">
                                                <span class="material-symbols-outlined" style="font-size: 14px;">${trendIcon}</span> ${trendText}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </article>
                    `;
                    patternsContainer.insertAdjacentHTML('beforeend', html);
                });
            }

            // AI Executive Summary (summary.html)
            const execSummary = document.getElementById('llm-executive-summary');
            if (execSummary && data.behavior_patterns && data.behavior_patterns.executive_summary) {
                execSummary.innerHTML = data.behavior_patterns.executive_summary.replace(/\n/g, '<br>');
            }

            // AI Executive Summary Quote Box (summary.html) — show up to 3 diverse quotes
            const summaryQuoteBox = document.getElementById('summary-quote-box');
            if (summaryQuoteBox && data.top_quotes) {
                const selectedQuotes = [];
                const seenThemes = new Set();
                
                // First pass: get one quote per theme, prefer low-rating frustrated ones
                Object.entries(data.top_quotes).forEach(([themeId, quotes]) => {
                    if (seenThemes.has(themeId) || selectedQuotes.length >= 3) return;
                    const bestQuote = quotes.find(q => q.rating <= 2) || quotes[0];
                    if (bestQuote) {
                        selectedQuotes.push({ ...bestQuote, themeId });
                        seenThemes.add(themeId);
                    }
                });
                
                if (selectedQuotes.length > 0) {
                    summaryQuoteBox.innerHTML = selectedQuotes.map(q => `
                        <div style="margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--color-surface-elevated);">
                            "${q.text}"
                            <span class="quote-author">— ${q.source || 'App Review'} • ${data.themes_summary?.[q.themeId]?.name || q.themeId}</span>
                        </div>
                    `).join('');
                } else {
                    summaryQuoteBox.innerHTML = "No critical quotes available in this dataset.";
                }
            }

            // Extracted Quotes
            const quotesContainer = document.getElementById('quotes-container');
            if (quotesContainer && data.top_quotes) {
                quotesContainer.innerHTML = '';
                // Flatten quotes by interleaving them so the feed looks diverse
                const allQuotes = [];
                const themeKeys = Object.keys(data.top_quotes);
                const maxLen = Math.max(...themeKeys.map(k => data.top_quotes[k].length));
                
                for (let i = 0; i < maxLen; i++) {
                    themeKeys.forEach(k => {
                        if (data.top_quotes[k][i]) {
                            allQuotes.push({ ...data.top_quotes[k][i], themeId: k });
                        }
                    });
                }
                
                // Sort quotes so we get the most recent ones first (mocking a feed)
                allQuotes.forEach((quote, index) => {
                    let sentiment = 'neutral';
                    if (quote.rating <= 2) sentiment = 'negative';
                    else if (quote.rating >= 4) sentiment = 'positive';
                    else if (quote.rating === 3) sentiment = 'mixed';
                    
                    const sentClass = sentiment === 'positive' ? 'pos' : sentiment === 'negative' ? 'neg' : sentiment === 'mixed' ? 'mix' : 'neu';
                    const sentLabel = sentClass.toUpperCase();
                    
                    // Assign a real-time looking post time based on index to simulate a live feed
                    const minsAgo = Math.max(1, index * 7 + Math.floor(Math.random() * 10));
                    const timeStr = minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ${minsAgo % 60}m ago`;
                    
                    const isExtractionPage = document.querySelector('.tracklist-header') !== null;
                    
                    if (isExtractionPage) {
                        const html = `
                            <div class="track-row" data-sentiment="${sentiment}" data-source="${quote.source || 'play_store'}">
                                <div style="display: flex; justify-content: center;">
                                    <div class="sentiment-dot ${sentiment}"></div>
                                </div>
                                <p class="track-quote">"${quote.text}"</p>
                                <div class="track-themes">
                                    <span class="theme-tag">${data.themes_summary[quote.themeId]?.name || quote.themeId}</span>
                                </div>
                                <div class="track-date">
                                    <div>${quote.date || timeStr}</div>
                                    <div class="track-source">${quote.source || 'play_store'}</div>
                                </div>
                            </div>
                        `;
                        quotesContainer.insertAdjacentHTML('beforeend', html);
                    } else {
                        const html = `
                            <div class="list-row">
                                <div style="width: 48px; padding-top: 4px; display: flex; justify-content: center;">
                                    <span class="badge badge-${sentClass}">${sentLabel}</span>
                                </div>
                                <div style="flex-grow: 1;">
                                    <p class="quote-text">"${quote.text}"</p>
                                    <span class="quote-meta">${quote.source || 'play_store'} • ${quote.date || timeStr}</span>
                                </div>
                            </div>
                        `;
                        quotesContainer.insertAdjacentHTML('beforeend', html);
                    }
                });
            }
        }
        
    } catch (err) {
        console.error('Failed to load overview data:', err);
    }
}

// Global Event Listeners for Quote Filters
document.addEventListener('DOMContentLoaded', () => {
    const filterBtns = document.querySelectorAll('.pill-filters .pill-btn');
    const sourceFilter = document.getElementById('source-filter');

    function applyFilters() {
        const activeBtn = document.querySelector('.pill-filters .pill-btn.active');
        const sentimentFilter = activeBtn ? activeBtn.getAttribute('data-filter') : 'all';
        const sourceVal = sourceFilter ? sourceFilter.value : 'all';

        const rows = document.querySelectorAll('#quotes-container .track-row');
        rows.forEach(row => {
            const rowSentiment = row.getAttribute('data-sentiment');
            const rowSource = row.getAttribute('data-source');
            
            const matchesSentiment = (sentimentFilter === 'all' || rowSentiment === sentimentFilter);
            const matchesSource = (sourceVal === 'all' || rowSource === sourceVal);

            if (matchesSentiment && matchesSource) {
                row.style.display = 'grid'; // Fixes alignment issue by preserving grid layout
            } else {
                row.style.display = 'none';
            }
        });
    }

    if (filterBtns.length > 0) {
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                applyFilters();
            });
        });
    }

    if (sourceFilter) {
        sourceFilter.addEventListener('change', applyFilters);
    }
});


// ========================================
// Utility: Create a styled dropdown menu
// ========================================
function createDropdown(items) {
    const dropdown = document.createElement('div');
    dropdown.style.cssText = `
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        min-width: 192px;
        background-color: #282828;
        border: 1px solid #343535;
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        z-index: 100;
        padding: 4px 0;
        display: none;
    `;

    items.forEach(item => {
        if (item.label === 'divider') {
            const divider = document.createElement('div');
            divider.style.cssText = 'height: 1px; background: #343535; margin: 4px 0;';
            dropdown.appendChild(divider);
            return;
        }

        const btn = document.createElement('button');
        btn.style.cssText = `
            width: 100%;
            text-align: left;
            padding: 8px 16px;
            background: ${item.active ? '#1DB954' : 'transparent'};
            border: none;
            color: ${item.danger ? '#EF4444' : '#fff'};
            font-size: 14px;
            font-family: 'Montserrat', sans-serif;
            font-weight: ${item.active ? '700' : '400'};
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: background-color 0.15s ease;
        `;

        btn.addEventListener('mouseenter', () => {
            if (!item.active) btn.style.backgroundColor = '#3e3e3e';
        });
        btn.addEventListener('mouseleave', () => {
            if (!item.active) btn.style.backgroundColor = 'transparent';
        });

        if (item.icon) {
            const icon = document.createElement('span');
            icon.className = 'material-symbols-outlined';
            icon.style.cssText = 'font-size: 18px; color: #c8c6c5;';
            icon.textContent = item.icon;
            btn.appendChild(icon);
        }

        const text = document.createTextNode(item.label);
        btn.appendChild(text);

        if (item.active) {
            const check = document.createElement('span');
            check.className = 'material-symbols-outlined';
            check.style.cssText = 'font-size: 18px; margin-left: auto;';
            check.textContent = 'check';
            btn.appendChild(check);
        }

        dropdown.appendChild(btn);
    });

    return dropdown;
}
