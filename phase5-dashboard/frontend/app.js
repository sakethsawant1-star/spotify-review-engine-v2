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

    // --- Run Pipeline Button ---
    const runPipelineBtn = document.querySelector('.run-pipeline-btn');
    if (runPipelineBtn) {
        runPipelineBtn.addEventListener('click', () => {
            window.location.href = 'pipeline.html';
        });
    }

    // --- Realtime Feed Toggle ---
    const realtimeBtn = document.querySelector('.realtime-btn');
    if (realtimeBtn) {
        let isActive = true;
        realtimeBtn.addEventListener('click', () => {
            isActive = !isActive;
            const dot = realtimeBtn.querySelector('.realtime-dot');
            if (isActive) {
                dot.classList.add('pulse-dot');
                dot.style.backgroundColor = '#1DB954';
                realtimeBtn.style.color = '#1DB954';
                realtimeBtn.style.borderColor = 'rgba(29, 185, 84, 0.2)';
            } else {
                dot.classList.remove('pulse-dot');
                dot.style.backgroundColor = '#6B7280';
                realtimeBtn.style.color = '#6B7280';
                realtimeBtn.style.borderColor = 'rgba(107, 114, 128, 0.2)';
            }
        });
    }

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
            const kpiTotal = document.getElementById('kpi-total');
            if (kpiTotal) kpiTotal.textContent = data.total_analyzed.toLocaleString();
            
            // Calculate avg sentiment dynamically (Positive + Mixed = % of total)
            const pos = data.sentiment_summary?.positive?.count || 0;
            const mix = data.sentiment_summary?.mixed?.count || 0;
            const neu = data.sentiment_summary?.neutral?.count || 0;
            const neg = data.sentiment_summary?.negative?.count || 0;
            
            const kpiSentiment = document.getElementById('kpi-sentiment');
            if (kpiSentiment) {
                const avgSent = Math.round(((pos + mix) / data.total_analyzed) * 100);
                kpiSentiment.textContent = avgSent + '%';
            }
            
            // Themes count
            const kpiThemes = document.getElementById('kpi-themes');
            if (kpiThemes) {
                const themesCount = Object.keys(data.themes_summary || {}).length;
                kpiThemes.textContent = themesCount;
            }

            // 4-Class Sentiment Doughnut Chart
            const totalSent = pos + mix + neu + neg;
            if (totalSent > 0) {
                const posPct = (pos / totalSent) * 100;
                const mixPct = (mix / totalSent) * 100;
                const neuPct = (neu / totalSent) * 100;
                
                const doughnut = document.getElementById('doughnut-chart');
                if (doughnut) {
                    doughnut.style.background = `conic-gradient(
                        var(--color-primary) 0% ${posPct}%,
                        var(--color-warning) ${posPct}% ${posPct + mixPct}%,
                        var(--color-text-muted) ${posPct + mixPct}% ${posPct + mixPct + neuPct}%,
                        var(--color-danger) ${posPct + mixPct + neuPct}% 100%
                    )`;
                }
                
                const topSent = Object.entries(data.sentiment_summary || {}).sort((a, b) => b[1].count - a[1].count)[0];
                const dValue = document.getElementById('doughnut-value');
                const dLabel = document.getElementById('doughnut-label');
                if (dValue && dLabel && topSent) {
                    dValue.textContent = Math.round((topSent[1].count / totalSent) * 100) + '%';
                    dLabel.textContent = topSent[0].charAt(0).toUpperCase() + topSent[0].slice(1);
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
                const sortedThemes = Object.values(data.themes_summary).sort((a, b) => b.count - a.count);
                
                sortedThemes.forEach(theme => {
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
                                <div class="s-green" style="width: ${theme.sentiment_split?.positive || 25}%;"></div>
                                <div class="s-yellow" style="width: ${theme.sentiment_split?.mixed || 25}%;"></div>
                                <div class="s-grey" style="width: ${theme.sentiment_split?.neutral || 25}%;"></div>
                                <div class="s-red" style="width: ${theme.sentiment_split?.negative || 25}%;"></div>
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
                                        <div class="bp-meta">
                                            <span class="meta-tag">Cohorts: ${pattern.cohorts_affected.join(', ')}</span>
                                            <span class="meta-tag ${sevClass}">Impact: ${pattern.severity}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </article>
                    `;
                    patternsContainer.insertAdjacentHTML('beforeend', html);
                });
            }

            // Extracted Quotes
            const quotesContainer = document.getElementById('quotes-container');
            if (quotesContainer && data.top_quotes) {
                quotesContainer.innerHTML = '';
                // top_quotes is an object mapping theme -> quotes. We'll flatten it.
                const allQuotes = [];
                Object.entries(data.top_quotes).forEach(([themeId, quotes]) => {
                    quotes.forEach(q => allQuotes.push({ ...q, themeId }));
                });
                
                allQuotes.forEach((quote, index) => {
                    // Assign a generic sentiment or determine based on rating
                    let sentiment = 'neutral';
                    if (quote.rating <= 2) sentiment = 'negative';
                    else if (quote.rating >= 4) sentiment = 'positive';
                    else if (quote.rating === 3) sentiment = 'mixed';
                    
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
                                <div>${quote.source}</div>
                            </div>
                        </div>
                    `;
                    quotesContainer.insertAdjacentHTML('beforeend', html);
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
