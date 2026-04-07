# Advanced High-Fidelity Dashboard with Action Timeline

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Command Center | Evaluation Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Josefin+Sans:wght@300;400;600&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        oled: '#050505',
                        panel: '#0a0a0a',
                        border: '#1a1a1a',
                        accent: {
                            gold: '#d4af37',
                            cyan: '#00e5ff',
                            ruby: '#ff1744',
                            emerald: '#00e676',
                            violet: '#7c3aed',
                        }
                    },
                    fontFamily: {
                        header: ['Cinzel', 'serif'],
                        body: ['Josefin Sans', 'sans-serif'],
                        mono: ['Fira Code', 'monospace']
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #050505; color: #ffffff; font-family: 'Josefin Sans', sans-serif; overflow-x: hidden; }
        .cinzel { font-family: 'Cinzel', serif; }
        .glass { background: rgba(10, 10, 10, 0.8); backdrop-filter: blur(12px); border: 1px solid #1a1a1a; }

        /* Action Timeline Styling */
        .timeline-card {
            background: rgba(26, 26, 26, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }
        .timeline-card:hover {
            border-color: rgba(255, 255, 255, 0.1);
            background: rgba(26, 26, 26, 0.5);
        }

        .reward-pos { color: #00e676; }
        .reward-neg { color: #ff1744; }

        /* State Panel */
        .state-chip {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 10px;
            padding: 6px 12px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .state-chip .label { font-size: 8px; color: rgba(255,255,255,0.25); text-transform: uppercase; letter-spacing: 0.18em; }
        .state-chip .val   { font-size: 11px; font-family: 'Fira Code', monospace; color: #00e5ff; }

        /* SLA bar */
        .sla-bar-track { background: rgba(255,255,255,0.06); border-radius: 4px; height: 4px; overflow: hidden; }
        .sla-bar-fill  { height: 100%; border-radius: 4px; transition: width 0.5s ease; background: #00e676; }
        .sla-bar-fill.warn { background: #f59e0b; }
        .sla-bar-fill.danger { background: #ff1744; }

        /* Auto-predict aura animation */
        @keyframes aura {
            0%   { box-shadow: 0 0 0 0 rgba(0,229,255,0.25); }
            70%  { box-shadow: 0 0 0 10px rgba(0,229,255,0); }
            100% { box-shadow: 0 0 0 0 rgba(0,229,255,0); }
        }
        .aura { animation: aura 1.2s ease-out; }

        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #050505; }
        ::-webkit-scrollbar-thumb { background: #1a1a1a; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #d4af37; }

        #json-monitor { scrollbar-width: thin; }
        pre.json-content { color: #a5b4fc; font-family: 'Fira Code', monospace; font-size: 0.75rem; }
        .string  { color: #00e676; }
        .number  { color: #f59e0b; }
        .boolean { color: #8b5cf6; }
        .null    { color: #ff1744; }
        .key     { color: #00e5ff; }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .animate-slide { animation: slideIn 0.4s ease forwards; }

        /* Skeleton shimmer for auto-fill */
        @keyframes shimmer {
            0%   { background-position: -400px 0; }
            100% { background-position: 400px 0; }
        }
        .skeleton {
            background: linear-gradient(90deg, rgba(0,229,255,0.05) 25%, rgba(0,229,255,0.12) 50%, rgba(0,229,255,0.05) 75%);
            background-size: 800px 100%;
            animation: shimmer 1.4s infinite;
        }
    </style>
</head>
<body class="min-h-screen p-6">
    <div class="max-w-7xl mx-auto space-y-8">

        <!-- Header -->
        <header class="flex justify-between items-end pb-8 border-b border-white/5">
            <div>
                <h1 class="cinzel text-3xl font-bold tracking-widest text-accent-gold uppercase">Neural Dashboard</h1>
                <p class="text-[10px] tracking-[0.4em] text-white/30 uppercase mt-2">Agent Evaluation Console • Phase 5.0</p>
            </div>
            <div class="flex items-center space-x-8">
                <div class="text-right">
                    <p class="text-[8px] text-white/20 uppercase tracking-[0.2em] mb-1">Stream Latency</p>
                    <div class="flex items-center space-x-2 text-accent-cyan font-mono text-xs">
                        <span id="latency">--ms</span>
                        <div class="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                            <div class="w-2/3 h-full bg-accent-cyan opacity-50"></div>
                        </div>
                    </div>
                </div>
                <div class="flex items-center space-x-4 bg-white/5 px-6 py-3 rounded-2xl border border-white/10">
                    <div id="status-indicator" class="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></div>
                    <div class="text-left">
                        <p id="status-text" class="cinzel text-[10px] tracking-widest text-white/90">CONNECTED</p>
                        <p id="episode-id" class="font-mono text-[9px] text-white/30 uppercase mt-0.5">ID: initializing</p>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Grid -->
        <div class="grid grid-cols-12 gap-8 h-[calc(100vh-200px)]">

            <!-- Left Panel: Vitals, State & History (Col 1-4) -->
            <div class="col-span-4 flex flex-col space-y-4 overflow-hidden">

                <!-- Agent Vitals -->
                <section class="glass rounded-3xl p-6 space-y-6 flex-shrink-0">
                    <h2 class="cinzel text-[10px] tracking-[0.3em] text-white/40 uppercase border-b border-white/5 pb-3">Agent Performance</h2>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-white/5 p-4 rounded-2xl border border-white/5">
                            <p class="text-[9px] text-white/30 uppercase tracking-widest mb-1">Last Reward</p>
                            <p id="last-reward" class="text-2xl font-bold tracking-tighter">0.00</p>
                        </div>
                        <div class="bg-white/5 p-4 rounded-2xl border border-white/5 text-accent-gold">
                            <p class="text-[9px] text-white/30 uppercase tracking-widest mb-1">Total Reward</p>
                            <p id="total-reward" class="text-2xl font-bold tracking-tighter">0.00</p>
                        </div>
                        <div class="bg-white/5 p-4 rounded-2xl border border-white/5 text-accent-cyan">
                            <p class="text-[9px] text-white/30 uppercase tracking-widest mb-1">Agent Score</p>
                            <p id="overall-score" class="text-2xl font-bold tracking-tighter">0%</p>
                        </div>
                        <div class="bg-white/5 p-4 rounded-2xl border border-white/5 text-accent-emerald">
                            <p class="text-[9px] text-white/30 uppercase tracking-widest mb-1">Status</p>
                            <p id="env-status" class="text-xs font-bold uppercase tracking-widest mt-2 cinzel">Running</p>
                        </div>
                    </div>
                </section>

                <!-- State Display Panel -->
                <section class="glass rounded-3xl p-5 flex-shrink-0">
                    <h2 class="cinzel text-[10px] tracking-[0.3em] text-white/40 uppercase border-b border-white/5 pb-3 mb-4">Episode State</h2>
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <div class="state-chip">
                            <span class="label">Step</span>
                            <span class="val" id="state-step">—</span>
                        </div>
                        <div class="state-chip">
                            <span class="label">Phase</span>
                            <span class="val" id="state-phase">—</span>
                        </div>
                        <div class="state-chip">
                            <span class="label">Sentiment</span>
                            <span class="val" id="state-sentiment">—</span>
                        </div>
                        <div class="state-chip">
                            <span class="label">SLA Left</span>
                            <span class="val" id="state-sla">—</span>
                        </div>
                    </div>
                    <!-- SLA progress bar -->
                    <div>
                        <div class="flex justify-between mb-1">
                            <span class="text-[8px] text-white/20 uppercase tracking-widest">SLA Budget</span>
                            <span id="sla-pct" class="text-[8px] font-mono text-white/30">—</span>
                        </div>
                        <div class="sla-bar-track">
                            <div id="sla-bar" class="sla-bar-fill" style="width:100%"></div>
                        </div>
                    </div>
                </section>

                <!-- Action Timeline -->
                <section class="glass rounded-3xl flex flex-col overflow-hidden" style="min-height:200px; flex:1 1 0%;">
                    <div class="p-6 border-b border-white/5 flex-shrink-0">
                        <div class="flex justify-between items-center">
                            <h2 class="cinzel text-[10px] tracking-[0.3em] text-white/40 uppercase">Action Timeline</h2>
                            <span id="step-count" class="text-[10px] bg-white/5 px-2 py-1 rounded text-white/60 font-mono">0 STEPS</span>
                        </div>
                    </div>
                    <div id="timeline-container" class="overflow-y-auto p-4 space-y-3" style="flex:1 1 0%; min-height:0;">
                        <div class="flex items-center justify-center text-white/10 italic text-sm" style="height:100%; min-height:80px;">
                            No actions recorded in current session.
                        </div>
                    </div>
                </section>
            </div>

            <!-- Right Panel: Command & Data (Col 5-12) -->
            <div class="col-span-8 flex flex-col space-y-8 overflow-hidden">

                <!-- Scenario Display -->
                <section class="glass rounded-3xl p-6 bg-gradient-to-br from-panel to-oled flex-shrink-0">
                    <div class="flex items-start justify-between">
                        <div class="space-y-4 max-w-2xl">
                            <div class="flex items-center space-x-2">
                                <span class="bg-accent-gold/20 text-accent-gold text-[9px] font-bold px-2 py-0.5 rounded tracking-widest uppercase">Scenario Active</span>
                                <span id="scenario-category" class="bg-white/5 text-white/50 text-[9px] font-bold px-2 py-0.5 rounded tracking-widest uppercase italic">General</span>
                            </div>
                            <p id="scenario-message" class="text-xl font-light leading-relaxed text-white/80 italic">Awaiting neural link to load scenario...</p>
                        </div>
                        <div class="text-right">
                            <select id="scenario-select" class="bg-oled border border-white/10 rounded-xl px-4 py-2 text-[10px] cinzel tracking-widest focus:border-accent-gold outline-none cursor-pointer">
                                <option value="">Random</option>
                                <option value="refund">Refund</option>
                                <option value="replacement">Replacement</option>
                                <option value="payment">Payment</option>
                                <option value="delivery">Delivery</option>
                            </select>
                        </div>
                    </div>
                </section>

                <!-- Command Input -->
                <section class="glass rounded-3xl p-8 space-y-6 flex-shrink-0">
                    <div class="flex justify-between items-center mb-2">
                        <h2 class="cinzel text-[10px] tracking-[0.3em] text-white/40 uppercase">Operational Command</h2>
                        <div class="flex items-center gap-3">
                            <!-- Auto-predict toggle -->
                            <label class="flex items-center gap-2 cursor-pointer select-none">
                                <div class="relative">
                                    <input type="checkbox" id="auto-predict-toggle" class="sr-only" checked>
                                    <div id="toggle-track" class="w-10 h-5 rounded-full bg-accent-cyan/30 border border-accent-cyan/40 transition-colors"></div>
                                    <div id="toggle-thumb" class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-accent-cyan transition-transform translate-x-5"></div>
                                </div>
                                <span class="text-[9px] text-accent-cyan uppercase tracking-widest font-bold">Auto-Fill</span>
                            </label>
                            <button id="auto-draft-btn" class="text-[9px] text-accent-cyan border border-accent-cyan/30 px-4 py-1.5 rounded-full hover:bg-accent-cyan/10 transition-all uppercase tracking-widest font-bold">Auto-Draft Neural Path</button>
                        </div>
                    </div>

                    <div class="grid grid-cols-12 gap-8">
                        <div class="col-span-4 space-y-4">
                            <div class="space-y-2">
                                <label class="text-[9px] text-white/20 uppercase tracking-widest block px-1">Strategy Path</label>
                                <select id="action-type" class="w-full bg-oled border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-accent-gold outline-none transition-all">
                                    <option value="clarify">Clarify</option>
                                    <option value="refund">Issue Refund</option>
                                    <option value="partial_refund">Partial Refund</option>
                                    <option value="replace">Replace</option>
                                    <option value="escalate">Escalate</option>
                                    <option value="deny">Deny</option>
                                </select>
                            </div>
                            <div class="space-y-2">
                                <label class="text-[9px] text-white/20 uppercase tracking-widest block px-1">Mandate Rationale</label>
                                <textarea id="action-reason" rows="3" class="w-full bg-oled border border-white/10 rounded-xl px-4 py-3 text-xs focus:border-accent-gold outline-none transition-all resize-none font-light" placeholder="Explain the decision logic..."></textarea>
                            </div>
                        </div>
                        <div class="col-span-8 space-y-4">
                            <div class="space-y-2">
                                <label class="text-[9px] text-white/20 uppercase tracking-widest block px-1">Neural Output (Agent Response)</label>
                                <textarea id="agent-response" rows="7" class="w-full bg-oled border border-white/10 rounded-2xl px-6 py-5 text-sm focus:border-accent-cyan outline-none transition-all resize-none leading-relaxed" placeholder="Type or generate neural response..."></textarea>
                            </div>
                        </div>
                    </div>

                    <div class="flex items-center space-x-4 pt-4 border-t border-white/5">
                        <button id="reset-btn" class="px-8 py-3.5 border border-white/10 text-white/60 cinzel text-[10px] font-bold rounded-xl tracking-[0.3em] hover:border-white/20 transition-all active:scale-95 uppercase">Protocol Reset</button>
                        <button id="state-btn" class="px-8 py-3.5 border border-white/10 text-white/40 cinzel text-[10px] rounded-xl tracking-[0.2em] hover:text-white transition-all uppercase">Probe State</button>
                        <button id="step-btn" class="flex-grow bg-accent-cyan text-black cinzel text-[11px] font-bold py-4 rounded-xl tracking-[0.4em] hover:bg-cyan-400 transition-all active:scale-95 uppercase shadow-[0_8px_30px_rgba(0,229,255,0.15)]">Execute Step</button>
                    </div>
                </section>

                <!-- Collapsible monitor -->
                <details class="group glass rounded-3xl overflow-hidden transition-all duration-500">
                    <summary class="px-8 py-4 flex justify-between items-center cursor-pointer list-none hover:bg-white/5">
                        <h2 class="cinzel text-[10px] tracking-[0.3em] text-white/40 uppercase">Raw Neural Packets (JSON)</h2>
                        <svg class="w-4 h-4 text-white/20 group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                    </summary>
                    <div id="json-monitor" class="h-[200px] overflow-auto p-8 bg-black/40 font-mono text-xs border-t border-white/5">
                        <pre id="json-output" class="json-content italic text-white/10">Awaiting packet stream...</pre>
                    </div>
                </details>
            </div>
        </div>
    </div>

    <!-- Notifications -->
    <div id="toast-container" class="fixed bottom-12 right-12 z-50 space-y-4"></div>

    <script>
        const ws_protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws_url = `${ws_protocol}//${window.location.host}/ws`;
        let socket = null;
        let isConnected = false;
        let lastPing = Date.now();
        let SLA_MAX = 8;   // default; updated from obs

        // ── Toggle thumb sync ───────────────────────────────────────────────
        const autoToggle = document.getElementById('auto-predict-toggle');
        const toggleTrack = document.getElementById('toggle-track');
        const toggleThumb = document.getElementById('toggle-thumb');
        autoToggle.addEventListener('change', () => {
            if (autoToggle.checked) {
                toggleTrack.classList.add('bg-accent-cyan/30', 'border-accent-cyan/40');
                toggleThumb.classList.add('translate-x-5');
                toggleThumb.classList.remove('translate-x-0');
            } else {
                toggleTrack.classList.remove('bg-accent-cyan/30', 'border-accent-cyan/40');
                toggleThumb.classList.add('translate-x-0');
                toggleThumb.classList.remove('translate-x-5');
            }
        });

        // ── WebSocket ────────────────────────────────────────────────────────
        function connect() {
            socket = new WebSocket(ws_url);

            socket.onopen = () => {
                isConnected = true;
                showNotification("Neural link established", "success");
                socket.send(JSON.stringify({ type: 'reset' }));
                document.getElementById('status-indicator').className = "w-2 h-2 rounded-full bg-accent-emerald animate-pulse";
                document.getElementById('status-text').textContent = 'CONNECTED';
                lastPing = Date.now();
            };

            socket.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type !== 'connected') updateJsonMonitor(msg);

                const latency = Date.now() - lastPing;
                document.getElementById('latency').textContent = latency + 'ms';
                lastPing = Date.now();

                switch(msg.type) {
                    case 'observation':
                        updateUI(msg.data, msg.reward, msg.done);
                        // Auto-fill next step if toggle is ON.
                        // NOTE: this env sets done=True after every step, so we
                        // always request a draft when auto-fill is enabled.
                        if (autoToggle.checked) {
                            requestAutoDraft();
                        } else {
                            // Re-enable button if not auto-filling
                            setStepBtnReady();
                        }
                        break;
                    case 'prediction':
                        populateInputs(msg.data);
                        break;
                    case 'connected':
                        document.getElementById('episode-id').textContent = 'ID: ' + msg.episode_id.slice(0, 12);
                        break;
                    case 'state':
                        showNotification("State Probed Successfully", "info");
                        break;
                }
            };

            socket.onclose = () => {
                isConnected = false;
                document.getElementById('status-indicator').className = "w-2 h-2 rounded-full bg-accent-ruby";
                document.getElementById('status-text').textContent = 'LINK SEVERED';
                showNotification("Neural disconnect", "error");
                setTimeout(connect, 3000);
            };
        }

        // ── UI Update ────────────────────────────────────────────────────────
        function updateUI(obs, lastReward, done) {
            // Vitals
            const rewardEl = document.getElementById('last-reward');
            rewardEl.textContent = (lastReward || 0).toFixed(2);
            rewardEl.className = (lastReward || 0) >= 0
                ? 'text-2xl font-bold tracking-tighter text-accent-emerald'
                : 'text-2xl font-bold tracking-tighter text-accent-ruby';

            document.getElementById('total-reward').textContent = (obs.total_reward || 0).toFixed(2);
            document.getElementById('overall-score').textContent = Math.round(obs.cumulative_score || 0) + '%';
            document.getElementById('env-status').textContent = done ? 'Finished' : 'Running';
            document.getElementById('env-status').className = done
                ? 'text-xs font-bold uppercase tracking-widest mt-2 text-white/30 cinzel'
                : 'text-xs font-bold uppercase tracking-widest mt-2 text-accent-emerald cinzel';

            // Scenario
            document.getElementById('scenario-message').textContent = obs.customer_message;
            document.getElementById('scenario-category').textContent = obs.ticket_info.issue_category;

            // State panel
            updateStatePanel(obs);

            // Timeline
            updateTimeline(obs.action_history);
        }

        function updateStatePanel(obs) {
            const step     = obs.action_history ? obs.action_history.length : 0;
            const slaLeft  = obs.sla_steps_left != null ? obs.sla_steps_left : '—';
            const phase    = obs.phase     || '—';
            const sentiment = obs.sentiment != null
                ? (obs.sentiment > 0.6 ? '😊 positive' : obs.sentiment > 0.35 ? '😐 neutral' : '😠 negative')
                : '—';

            document.getElementById('state-step').textContent      = step;
            document.getElementById('state-phase').textContent     = phase;
            document.getElementById('state-sentiment').textContent = sentiment;
            document.getElementById('state-sla').textContent       = slaLeft !== '—' ? slaLeft + ' steps' : '—';

            // SLA bar
            if (obs.sla_steps_left != null) {
                // Try to derive max from first observation (heuristic)
                if (step === 0) SLA_MAX = obs.sla_steps_left;
                const pct = Math.max(0, Math.min(100, (obs.sla_steps_left / SLA_MAX) * 100));
                const bar = document.getElementById('sla-bar');
                bar.style.width = pct + '%';
                bar.className = 'sla-bar-fill' + (pct < 30 ? ' danger' : pct < 55 ? ' warn' : '');
                document.getElementById('sla-pct').textContent = Math.round(pct) + '%';
            }
        }

        function updateTimeline(history) {
            const container = document.getElementById('timeline-container');
            document.getElementById('step-count').textContent = history.length + ' STEPS';

            if (!history || history.length === 0) {
                container.innerHTML = '<div class="flex items-center justify-center text-white/10 italic text-sm" style="min-height:80px;">No actions recorded.</div>';
                return;
            }

            container.innerHTML = [...history].reverse().map(action => {
                const reward = (action.reward != null) ? Number(action.reward) : 0;
                const rewardStr = (reward >= 0 ? '+' : '') + reward.toFixed(2);
                const rewardCls = reward >= 0 ? 'reward-pos' : 'reward-neg';
                return `
                <div class="timeline-card rounded-2xl p-4 space-y-2 animate-slide">
                    <div class="flex justify-between items-center">
                        <span class="text-[10px] font-bold tracking-widest uppercase text-white/60">Step ${action.step || '?'}: <span class="text-white">${action.action_type || '—'}</span></span>
                        <span class="${rewardCls} font-mono text-xs font-bold">${rewardStr}</span>
                    </div>
                    <p class="text-[11px] text-white/40 leading-relaxed">${action.description || ''}</p>
                </div>`;
            }).join('');
        }

        // ── Auto-Draft / Predict ─────────────────────────────────────────────
        function setStepBtnLoading() {
            const btn = document.getElementById('step-btn');
            btn.disabled = true;
            btn.textContent = 'Processing...';
            btn.classList.add('opacity-60', 'cursor-not-allowed');
        }

        function setStepBtnReady() {
            const btn = document.getElementById('step-btn');
            btn.disabled = false;
            btn.textContent = 'Execute Step';
            btn.classList.remove('opacity-60', 'cursor-not-allowed');
        }

        function requestAutoDraft() {
            // Shimmer the input fields to signal loading
            const responseEl = document.getElementById('agent-response');
            const reasonEl   = document.getElementById('action-reason');
            responseEl.classList.add('skeleton');
            reasonEl.classList.add('skeleton');
            // Keep button disabled until prediction arrives
            setStepBtnLoading();
            socket.send(JSON.stringify({ type: 'predict' }));
        }

        function populateInputs(prediction) {
            const responseEl = document.getElementById('agent-response');
            const reasonEl   = document.getElementById('action-reason');

            // Remove skeleton shimmer
            responseEl.classList.remove('skeleton');
            reasonEl.classList.remove('skeleton');

            responseEl.value = prediction.response;
            document.getElementById('action-type').value = prediction.action_type;
            reasonEl.value   = prediction.reason;

            // Re-enable and pulse the step button
            setStepBtnReady();
            const stepBtn = document.getElementById('step-btn');
            stepBtn.classList.add('aura');
            stepBtn.addEventListener('animationend', () => stepBtn.classList.remove('aura'), { once: true });

            showNotification("Neural path auto-drafted — press Execute to proceed", "success");
        }

        // ── JSON Monitor ─────────────────────────────────────────────────────
        function updateJsonMonitor(msg) {
            const outputEl = document.getElementById('json-output');
            outputEl.classList.remove('italic', 'text-white/10');
            outputEl.innerHTML = syntaxHighlight(JSON.stringify(msg, null, 2));
        }

        function syntaxHighlight(json) {
            json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            // Avoid Python escape-sequence warnings by building the regex from parts
            var strPat  = '"(?:\\\\u[0-9a-fA-F]{4}|\\\\[^u]|[^\\\\"])*"';
            var numPat  = '-?[0-9]+(?:[.][0-9]*)?(?:[eE][+\\-]?[0-9]+)?';
            var boolPat = 'true|false|null';
            var fullPat = '(' + strPat + '([ \\t]*:)?|' + boolPat + '|' + numPat + ')';
            return json.replace(new RegExp(fullPat, 'g'), function (match) {
                var cls = 'number';
                if (match.startsWith('"')) {
                    cls = match.trimEnd().endsWith(':') ? 'key' : 'string';
                } else if (match === 'true' || match === 'false') {
                    cls = 'boolean';
                } else if (match === 'null') {
                    cls = 'null';
                }
                return '<span class="' + cls + '">' + match + '</span>';
            });
        }

        // ── Notifications ─────────────────────────────────────────────────────
        function showNotification(message, type) {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const icons  = { success: '✓', error: '✕', info: 'ℹ' };
            const colors = {
                success: 'border-accent-emerald text-accent-emerald',
                error:   'border-accent-ruby text-accent-ruby',
                info:    'border-accent-cyan text-accent-cyan'
            };

            toast.className = `glass border-x-2 px-6 py-4 min-w-[280px] shadow-2xl transition-all duration-500 transform translate-x-full ${colors[type] || colors.info}`;
            toast.innerHTML = `<div class="flex items-center space-x-4"><span class="text-xl font-bold">${icons[type] || '•'}</span><p class="cinzel text-[10px] tracking-widest uppercase font-bold">${message}</p></div>`;
            container.appendChild(toast);

            setTimeout(() => toast.classList.remove('translate-x-full'), 100);
            setTimeout(() => {
                toast.classList.add('translate-x-full', 'opacity-0');
                setTimeout(() => toast.remove(), 500);
            }, 4000);
        }

        // ── Button Actions ───────────────────────────────────────────────────
        document.getElementById('reset-btn').addEventListener('click', () => {
            const category = document.getElementById('scenario-select').value;
            // If a category is selected, reset within that category scope;
            // if blank ("Random"), the server picks from all categories.
            socket.send(JSON.stringify({ type: 'reset', category: category || null }));
            showNotification("Initializing Reset Protocol", "info");
            // Reset SLA tracking
            SLA_MAX = 8;
        });

        document.getElementById('state-btn').addEventListener('click', () => {
            socket.send(JSON.stringify({ type: 'state' }));
        });

        document.getElementById('auto-draft-btn').addEventListener('click', () => {
            requestAutoDraft();
            showNotification("Requesting neural draft", "info");
        });

        document.getElementById('step-btn').addEventListener('click', () => {
            const response   = document.getElementById('agent-response').value.trim();
            const actionType = document.getElementById('action-type').value;
            const reason     = document.getElementById('action-reason').value.trim();

            if (!response) {
                // If auto-fill is ON, request a draft instead of showing error
                if (autoToggle.checked) {
                    requestAutoDraft();
                    showNotification("Fetching neural draft...", "info");
                } else {
                    showNotification("Incomplete neural output — response required", "error");
                }
                return;
            }

            setStepBtnLoading();
            socket.send(JSON.stringify({
                type:   'step',
                action: { response, action_type: actionType, reason, amount: 0 }
            }));

            // Clear inputs; auto-fill will repopulate for next step
            document.getElementById('agent-response').value = '';
            document.getElementById('action-reason').value  = '';
            showNotification("Step Execution Commenced", "success");
        });

        // ── Also reset when scenario dropdown changes ────────────────────────
        document.getElementById('scenario-select').addEventListener('change', () => {
            const category = document.getElementById('scenario-select').value;
            // Auto-reset into the newly selected category scope
            socket.send(JSON.stringify({ type: 'reset', category: category || null }));
            SLA_MAX = 8;
            showNotification(
                category
                    ? `Scenario scoped to: ${category.toUpperCase()}`
                    : "Scenario set to full random pool",
                "info"
            );
        });

        connect();
    </script>
</body>
</html>
"""
