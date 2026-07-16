const STATE = {
    raw: null,
    metadata: null,
    features: null,
    analysis: null,
    currentFileBase: 'rec8_bad'
};

const ELEMENTS = {
    audio: document.getElementById('audio-player'),
    seekSlider: document.getElementById('seek-slider'),
    timeCurrent: document.getElementById('time-current'),
    timeTotal: document.getElementById('time-total'),
    spinner: document.getElementById('loading-spinner'),
    dashboard: document.getElementById('dashboard'),
    playbackBar: document.getElementById('playback-bar'),
    pillarsGrid: document.getElementById('pillars-grid')
};

// Available files fallback (if dynamic fetch fails)
let files = [
    { value: 'rec8_bad', label: 'rec8_bad_features.json' }
];

async function fetchFileList() {
    try {
        const response = await fetch('../data/outputs/');
        const text = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, 'text/html');
        const links = Array.from(doc.querySelectorAll('a'));
        
        const dynamicFiles = [];
        links.forEach(a => {
            let filename = a.getAttribute('href');
            // Remove trailing slash if present, though files shouldn't have them
            if (filename) {
                // http.server sometimes URL encodes, let's decode
                filename = decodeURIComponent(filename);
                if (filename.endsWith('_features.json') && !filename.includes('copy')) {
                    const value = filename.replace('_features.json', '');
                    dynamicFiles.push({ value, label: filename });
                }
            }
        });
        
        if (dynamicFiles.length > 0) {
            files = dynamicFiles;
        }
    } catch (err) {
        console.warn("Could not auto-fetch directory listing, using fallback.", err);
    }
}

async function init() {
    await fetchFileList();

    const selector = document.getElementById('file-selector');
    selector.innerHTML = ''; // clear existing
    files.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.value;
        opt.textContent = f.label;
        selector.appendChild(opt);
    });

    selector.addEventListener('change', (e) => loadData(e.target.value));
    
    // Select the first available file
    if (files.length > 0) {
        selector.value = files[0].value;
        loadData(files[0].value);
    }

    setupAudio();
    setupSidebar();
    bindExportButtons();
}

function setupSidebar() {
    const toggleBtn = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    
    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = e.currentTarget.dataset.view;
            switchView(viewId);
        });
    });
}

function switchView(viewId) {
    // Update active nav link
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.dataset.view === viewId) item.classList.add('active');
        else item.classList.remove('active');
    });

    // Hide all views
    document.querySelectorAll('.view-section').forEach(view => {
        view.classList.add('hidden');
        view.classList.remove('active');
    });

    // Show target view
    const target = document.getElementById(viewId);
    if (target) {
        target.classList.remove('hidden');
        target.classList.add('active');
    }

    // Trigger resize for charts inside hidden divs
    setTimeout(() => {
        if (viewId === 'view-speaker') {
            try { Plotly.Plots.resize(document.getElementById('pie-chart')); } catch (e) { }
        }
        if (viewId === 'view-timeline') {
            // Resize canvas if needed
            drawWaveform(ELEMENTS.audio.currentTime);
            drawRealtime(ELEMENTS.audio.currentTime);
        }
    }, 50);
}

async function loadData(fileBase) {
    ELEMENTS.spinner.classList.remove('hidden');
    ELEMENTS.dashboard.classList.add('hidden');
    ELEMENTS.playbackBar.classList.add('hidden');

    try {
        const featRes = await fetch(`../data/outputs/${fileBase}_features.json`);

        if (!featRes.ok) throw new Error("Could not load JSON file");

        STATE.raw = await featRes.json();
        STATE.metadata = STATE.raw.metadata;
        STATE.analysis = STATE.raw.analysis_results;

        const timeline = STATE.raw.features.timeline || [];
        STATE.features = {
            timestamps: timeline.map(t => t.timestamp),
            pitch: timeline.map(t => t.raw?.prosody?.pitch_hz || 0),
            rms: timeline.map(t => t.raw?.acoustic?.rms || 0),
            energy: timeline.map(t => t.raw?.acoustic?.energy || 0),
            loudness_db: timeline.map(t => t.raw?.acoustic?.loudness_db || 0),
            snr: timeline.map(t => t.raw?.quality?.snr_db || 0),
            speech_quality: timeline.map(t => t.raw?.quality?.speech_quality_proxy || 0),
            vad_flags: timeline.map(t => t.derived?.speech?.active || false),
            signal_dropouts: timeline.map(t => t.dropout || false)
        };

        renderDashboard();
    } catch (err) {
        console.error("Error loading data:", err);
        alert("Failed to load data for " + fileBase + ". Please check console.");
    } finally {
        ELEMENTS.spinner.classList.add('hidden');
    }
}

function renderDashboard() {
    ELEMENTS.dashboard.classList.remove('hidden');
    ELEMENTS.playbackBar.classList.remove('hidden');

    // Set Audio
    const sourceFile = STATE.metadata.source_file;
    let audioUrl = sourceFile;
    if (audioUrl.includes('audio/')) {
        audioUrl = '../data/audio/' + audioUrl.split('audio/')[1];
    }
    ELEMENTS.audio.src = audioUrl;

    // Render Overview
    const score = STATE.analysis.scores?.overall_call_health || 0;
    const grade = STATE.analysis.explanations?.overall_call_health?.grade || "N/A";
    document.getElementById('gauge-container').innerHTML = gaugeSVG(score, grade);
    
    document.getElementById('gate-multiplier').textContent = `Gate Multiplier: ${STATE.analysis.scores?.gate_multiplier || 1.0}x`;

    document.getElementById('meta-dur').textContent = `${(STATE.metadata.duration_seconds || 0).toFixed(1)}s`;

    const spkStats = STATE.raw.diarization?.statistics || {};
    const spkCount = Object.keys(spkStats).length;
    document.getElementById('meta-spk').textContent = spkCount;
    let dom = "None";
    if (spkCount > 0) {
        dom = Object.entries(spkStats).sort((a, b) => b[1].duration - a[1].duration)[0][0];
    }
    document.getElementById('meta-dom').textContent = dom;

    renderPillars();
    renderBlockAnalysis();
    renderTimeline();
    renderSpeakerAnalysis();
    renderDiarization();
    renderScoreBreakdown();
    setupTabs();
}

function renderPillars() {
    ELEMENTS.pillarsGrid.innerHTML = '';
    const explanations = STATE.analysis.explanations || {};

    const pillars = [
        { key: 'audio_quality', title: 'Audio Quality' },
        { key: 'voice_stability', title: 'Voice Stability' },
        { key: 'conversation_flow', title: 'Conversation Flow' },
        { key: 'conversation_balance', title: 'Conversation Balance' },
        { key: 'speech_activity', title: 'Speech Activity' },
        { key: 'collection_confidence', title: 'Collection Confidence' }
    ];

    pillars.forEach(p => {
        const exp = explanations[p.key] || { value: 0, grade: 'N/A', positives: [], negatives: [] };
        const score = exp.value || 0;

        let color = 'var(--color-fair)';
        if (score >= 85) color = 'var(--color-excellent)';
        else if (score >= 70) color = 'var(--color-good)';
        else if (score < 50) color = 'var(--color-poor)';

        const card = document.createElement('div');
        card.className = 'pillar-card glass-panel';

        // Header
        const header = document.createElement('div');
        header.className = 'pillar-header';
        header.style.borderLeft = `4px solid ${color}`;
        header.innerHTML = `
            <h4>${p.title}</h4>
            <h2 style="color: ${color}">${score}/100</h2>
            <span style="color: #94a3b8">${exp.grade.toUpperCase()}</span>
            <span class="evidence-prompt" style="transition: color 0.2s;">Hover to View Evidence</span>
        `;

        // Drawer
        const drawer = document.createElement('div');
        drawer.className = 'evidence-drawer';

        const drawerContent = document.createElement('div');
        drawerContent.className = 'evidence-content';

        // Render Negatives
        let negs = exp.negatives;
        if (!negs || negs.length === 0) {
            if (score <= 75) negs = [`General degradation detected in ${p.title.toLowerCase()} continuous metrics`];
        }

        if (negs && negs.length > 0) {
            drawerContent.appendChild(createEvidenceSection('🚨 Top Issue', [negs[0]], true));
            if (negs.length > 1) {
                drawerContent.appendChild(createEvidenceSection('⚠ Evidence Requiring Review', negs.slice(1), false));
            }
        } else {
            drawerContent.innerHTML += `<div class="evidence-section"><h5>✨ Top Issue</h5><div class="issue-text issue-green">✓ No critical degradations detected.</div></div>`;
        }

        // Render Positives
        const posSection = document.createElement('div');
        posSection.className = 'evidence-section';
        posSection.innerHTML = `<h5>✅ Strengths</h5>`;
        if (exp.positives && exp.positives.length > 0) {
            exp.positives.forEach(pos => {
                posSection.innerHTML += `<div class="issue-text">✓ ${pos}</div>`;
            });
        } else {
            posSection.innerHTML += `<div class="issue-text" style="color: var(--text-muted)">- No strengths recorded.</div>`;
        }
        drawerContent.appendChild(posSection);

        drawer.appendChild(drawerContent);
        card.appendChild(header);
        card.appendChild(drawer);
        ELEMENTS.pillarsGrid.appendChild(card);
    });
}

function createEvidenceSection(title, items, isTopIssue) {
    const sec = document.createElement('div');
    sec.className = 'evidence-section';
    sec.innerHTML = `<h5>${title}</h5>`;

    items.forEach(item => {
        const itemDiv = document.createElement('div');
        if (item.includes(" at ")) {
            const parts = item.split(" at ");
            const category = parts[0];
            const tsBlock = parts[1].replace("...", "").trim();

            const catDiv = document.createElement('div');
            catDiv.className = `issue-text ${isTopIssue ? 'issue-red' : 'issue-warn'}`;
            catDiv.innerHTML = `${isTopIssue ? '🚨' : '⚠'} ${category}`;
            itemDiv.appendChild(catDiv);

            const btnRow = document.createElement('div');
            btnRow.className = 'btn-row';

            const timestamps = tsBlock.split(",").map(t => t.trim());
            timestamps.forEach(ts => {
                const match = ts.match(/(\d{2}):(\d{2})/);
                if (match) {
                    const startSec = Math.max(0, parseInt(match[1]) * 60 + parseInt(match[2]) - 3);
                    const btn = document.createElement('button');
                    btn.className = 'play-btn';
                    btn.textContent = `▶ ${ts}`;
                    btn.onclick = (e) => {
                        e.stopPropagation(); // prevent drawer toggle if clicked inside
                        seekAudio(startSec);
                    };
                    btnRow.appendChild(btn);
                }
            });
            itemDiv.appendChild(btnRow);
        } else {
            itemDiv.className = `issue-text ${isTopIssue ? 'issue-red' : 'issue-warn'}`;
            itemDiv.innerHTML = `${isTopIssue ? '🚨' : '⚠'} ${item}`;
        }
        sec.appendChild(itemDiv);
    });

    return sec;
}

// ==========================================
// AUDIO & SYNCING
// ==========================================

function formatTime(secs) {
    if (isNaN(secs)) return "0:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function setupAudio() {
    ELEMENTS.audio.addEventListener('loadedmetadata', () => {
        ELEMENTS.seekSlider.max = ELEMENTS.audio.duration;
        ELEMENTS.timeTotal.textContent = formatTime(ELEMENTS.audio.duration);
    });

    ELEMENTS.audio.addEventListener('timeupdate', () => {
        const t = ELEMENTS.audio.currentTime;
        ELEMENTS.seekSlider.value = t;
        ELEMENTS.timeCurrent.textContent = formatTime(t);
        updateInstantAnalysis(t);
    });

    ELEMENTS.seekSlider.addEventListener('input', (e) => {
        ELEMENTS.audio.currentTime = e.target.value;
        ELEMENTS.timeCurrent.textContent = formatTime(e.target.value);
    });

    ELEMENTS.audio.addEventListener('seeked', () => {
        const t = ELEMENTS.audio.currentTime;
        updateInstantAnalysis(t);
        drawWaveform(t);
        drawRealtime(t);
    });

    function loop() {
        if (!ELEMENTS.audio.paused) {
            const t = ELEMENTS.audio.currentTime;
            drawWaveform(t);
            drawRealtime(t);
        }
        requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
}

function seekAudio(seconds) {
    ELEMENTS.audio.currentTime = seconds;
    ELEMENTS.audio.play().catch(err => console.log("Autoplay blocked:", err));
}

function updateInstantAnalysis(t) {
    if (!STATE.features) return;
    document.getElementById('current-t').textContent = t.toFixed(1);

    const blockIdx = Math.floor(t / 0.5);
    const f = STATE.features;

    // Fallbacks
    let pitch = "--", rms = "--", nrg = "--", loud = "--", snr = "--", qual = "--";
    let status = "IDLE", spkInfo = "🔇 No active speaker";

    if (f.pitch && f.pitch[blockIdx] !== undefined) {
        pitch = f.pitch[blockIdx].toFixed(1) + " Hz";
        rms = f.rms[blockIdx].toFixed(4);
        nrg = f.energy[blockIdx].toFixed(2);
        loud = f.loudness_db[blockIdx].toFixed(1) + " dB";
        snr = f.snr[blockIdx].toFixed(1) + " dB";
        qual = (f.speech_quality[blockIdx] * 100).toFixed(0);
    }

    document.getElementById('val-pitch').textContent = pitch;
    document.getElementById('val-rms').textContent = rms;
    document.getElementById('val-energy').textContent = nrg;
    document.getElementById('val-loud').textContent = loud;
    document.getElementById('val-snr').textContent = snr;
    document.getElementById('val-qual').textContent = qual;

    // Status Logic
    const isSpeech = f.vad_flags && f.vad_flags[blockIdx];
    const isDropout = f.signal_dropouts && f.signal_dropouts[blockIdx];

    if (isDropout) status = "Dropout";
    else if (isSpeech) status = "Speech";
    else status = "Pause";

    const badge = document.getElementById('conv-status');
    badge.textContent = status.toUpperCase();
    badge.className = `status-badge ${status.toLowerCase()}`;

    // Update playhead if not playing (since loop handles it when playing)
    if (ELEMENTS.audio.paused) {
        drawWaveform(t);
        drawRealtime(t);
    }

    // Sync Visualizer
    const dur = STATE.metadata.duration_seconds || 1;
    const curLine = document.getElementById('cursor-line');
    if (curLine) {
        curLine.style.left = `${(t / dur) * 100}%`;
    }
}

// ==========================================
// ADVANCED VISUALIZATIONS
// ==========================================

function getAvg(arr, start, end) {
    if (!arr) return 0;
    let sum = 0, count = 0;
    for (let i = start; i < end; i++) {
        if (arr[i] !== null && arr[i] > 0) { sum += arr[i]; count++; }
    }
    return count > 0 ? sum / count : 0;
}

function renderBlockAnalysis() {
    const f = STATE.features;
    if (!f || !f.pitch) return;

    const blockSizeSec = 10;
    const windowSec = STATE.metadata.processing.hop_size_seconds || 0.5;
    const windowsPerBlock = Math.round(blockSizeSec / windowSec);
    const numBlocks = Math.ceil((STATE.metadata.duration_seconds || 0) / blockSizeSec);


    // Populate Select
    const selector = document.getElementById('block-selector');
    selector.innerHTML = '';
    for (let i = 0; i < numBlocks; i++) {
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = `Block #${i} (${(i * blockSizeSec).toFixed(1)}s - ${Math.min((i + 1) * blockSizeSec, STATE.metadata.duration_seconds).toFixed(1)}s)`;
        selector.appendChild(opt);
    }
    selector.onchange = (e) => updateBlockDetails(parseInt(e.target.value));

    const tbody = document.querySelector('#block-table tbody');
    tbody.innerHTML = '';

    for (let i = 0; i < numBlocks; i++) {
        const startIdx = i * windowsPerBlock;
        const endIdx = Math.min((i + 1) * windowsPerBlock, f.pitch.length);

        const pitchAvg = getAvg(f.pitch, startIdx, endIdx);
        const snrAvg = getAvg(f.snr, startIdx, endIdx);
        const qualAvg = getAvg(f.speech_quality, startIdx, endIdx);
        const nrgAvg = getAvg(f.energy, startIdx, endIdx);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>Block #${i}</td>
            <td>${(i * blockSizeSec).toFixed(1)}s - ${Math.min((i + 1) * blockSizeSec, STATE.metadata.duration_seconds).toFixed(1)}s</td>
            <td>${qualAvg > 0 ? (qualAvg * 100).toFixed(0) : '--'}/100</td>
            <td>${pitchAvg > 0 ? pitchAvg.toFixed(1) + ' Hz' : '--'}</td>
            <td>${nrgAvg > 0 ? nrgAvg.toFixed(2) : '--'}</td>
            <td>--</td>
            <td>${snrAvg > 0 ? snrAvg.toFixed(1) + ' dB' : '--'}</td>
        `;
        tbody.appendChild(tr);
    }

    document.getElementById('block-details').classList.remove('hidden');
    updateBlockDetails(0);
}

function updateBlockDetails(blockIdx) {
    const f = STATE.features;
    const blockSizeSec = 10;
    const windowSec = STATE.metadata.processing.hop_size_seconds || 0.5;
    const windowsPerBlock = Math.round(blockSizeSec / windowSec);
    const startIdx = blockIdx * windowsPerBlock;
    const endIdx = Math.min((blockIdx + 1) * windowsPerBlock, f.pitch.length);

    // Tab 1: Scores (Proxy)
    const qualAvg = getAvg(f.speech_quality, startIdx, endIdx);
    document.getElementById('bd-aq').textContent = qualAvg > 0 ? (qualAvg * 100).toFixed(0) + '/100' : '--';
    document.getElementById('bd-vs').textContent = 'N/A'; // Handled via continuous rule engine
    document.getElementById('bd-cf').textContent = 'N/A';
    document.getElementById('bd-cb').textContent = 'N/A';
    document.getElementById('bd-sa').textContent = 'N/A';

    // Tab 2: Stats
    const statsTbody = document.querySelector('#bd-stats-table tbody');
    statsTbody.innerHTML = '';
    const metrics = ['pitch', 'rms', 'energy', 'snr'];
    metrics.forEach(m => {
        if (!f[m]) return;
        let min = Infinity, max = -Infinity, sum = 0, count = 0;
        for (let i = startIdx; i < endIdx; i++) {
            const v = f[m][i];
            if (v !== null && v > 0) {
                if (v < min) min = v;
                if (v > max) max = v;
                sum += v; count++;
            }
        }
        if (count > 0) {
            const avg = sum / count;
            let sqSum = 0;
            for (let i = startIdx; i < endIdx; i++) {
                const v = f[m][i];
                if (v !== null && v > 0) sqSum += (v - avg) * (v - avg);
            }
            const std = Math.sqrt(sqSum / count);
            statsTbody.innerHTML += `<tr><td>${m.toUpperCase()}</td><td>${min.toFixed(2)}</td><td>${max.toFixed(2)}</td><td>${avg.toFixed(2)}</td><td>${std.toFixed(2)}</td></tr>`;
        }
    });

    // Tab 3: Speech Activity
    let spkFrames = 0, silFrames = 0, dropFrames = 0;
    for (let i = startIdx; i < endIdx; i++) {
        if (f.vad_flags && f.vad_flags[i]) spkFrames++;
        else if (f.signal_dropouts && f.signal_dropouts[i]) dropFrames++;
        else silFrames++;
    }
    const totalF = endIdx - startIdx;
    document.getElementById('bd-speech-pct').textContent = ((spkFrames / totalF) * 100).toFixed(1) + '%';
    document.getElementById('bd-silence-pct').textContent = ((silFrames / totalF) * 100).toFixed(1) + '%';
    document.getElementById('bd-drop-c').textContent = dropFrames > 0 ? "Yes" : "0";
    document.getElementById('bd-drop-d').textContent = (dropFrames * windowSec).toFixed(1) + 's';

    // Tab 4: Conv Stats (Approximate using overall diarization intersecting this block)
    let turns = 0;
    let speakers = new Set();
    const share = {};
    const segments = STATE.raw.diarization?.segments || [];
    const bStart = blockIdx * blockSizeSec;
    const bEnd = bStart + blockSizeSec;

    segments.forEach(seg => {
        // If segment overlaps this block
        if (seg.start < bEnd && seg.end > bStart) {
            turns++;
            speakers.add(seg.speaker);
            const overlap = Math.min(seg.end, bEnd) - Math.max(seg.start, bStart);
            share[seg.speaker] = (share[seg.speaker] || 0) + overlap;
        }
    });

    document.getElementById('bd-turns').textContent = turns;
    document.getElementById('bd-changes').textContent = Math.max(0, turns - 1);
    document.getElementById('bd-latency').textContent = 'N/A'; // Need complex backend logic to calculate exact response latency

    const barsContainer = document.getElementById('bd-share-bars');
    barsContainer.innerHTML = '';
    let totalSpeech = 0;
    for (const k in share) totalSpeech += share[k];

    for (const k in share) {
        const pct = (share[k] / totalSpeech) * 100;
        const color = k === 'Speaker 0' ? '#3b82f6' : '#ef4444';
        barsContainer.innerHTML += `
            <div style="font-size: 11px; margin-bottom: 2px; color: #fff;">${k}: ${pct.toFixed(1)}%</div>
            <div style="width: 100%; height: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden; margin-bottom: 8px;">
                <div style="width: ${pct}%; height: 100%; background: ${color};"></div>
            </div>
        `;
    }
    if (Object.keys(share).length === 0) {
        barsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; font-style: italic;">Silent block (no speech segments)</div>';
    }
}

function renderTimeline() {
    const wf = document.getElementById('waveform-canvas');
    const rt = document.getElementById('realtime-canvas');
    if (!wf || !rt) return;

    const seekClick = (cv, ev) => {
        const r = cv.getBoundingClientRect();
        const duration = STATE.metadata.duration_seconds || 1;
        const t = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)) * duration;
        seekAudio(t);
    };

    // Remove old listeners by replacing node if necessary (optional), but we just add them once for simplicity.
    wf.onclick = e => seekClick(wf, e);
    rt.onclick = e => seekClick(rt, e);

    drawWaveform(0);
    drawRealtime(0);
}

function drawWaveform(t) {
    const cv = document.getElementById('waveform-canvas');
    if (!cv) return;
    const g = cv.getContext("2d");
    const W = cv.width = cv.clientWidth;
    const H = cv.height = cv.clientHeight;
    g.clearRect(0, 0, W, H);
    
    const f = STATE.features;
    if (!f || !f.timestamps) return;
    const duration = STATE.metadata.duration_seconds || 1;
    const X = sec => (sec / duration) * W;

    // VAD segments
    const segments = STATE.raw.diarization?.segments || [];
    segments.forEach(seg => {
        g.fillStyle = seg.speaker === 'Speaker 0' ? "rgba(59, 130, 246, 0.10)" : "rgba(239, 68, 68, 0.10)";
        g.fillRect(X(seg.start), 0, X(seg.end) - X(seg.start), H);
    });

    // Decision turn highlight
    const dt = STATE.raw.summary?.decision_turn;
    if (dt) {
        g.fillStyle = "rgba(167, 139, 250, 0.22)";
        g.fillRect(X(dt.start), 0, X(dt.end) - X(dt.start), H);
        g.fillStyle = "#a78bfa"; g.font = "10px sans-serif";
        g.fillText("decision turn", Math.min(X(dt.start) + 3, W - 70), 12);
    }

    // RMS Envelope (Mirrored)
    const mid = H / 2;
    g.strokeStyle = "#38bdf8"; g.lineWidth = 1; g.globalAlpha = 0.9; g.beginPath();
    
    const rmsArr = f.rms || [];
    const times = f.timestamps || [];
    let maxRms = 0;
    for (let i = 0; i < rmsArr.length; i++) if (rmsArr[i] > maxRms) maxRms = rmsArr[i];
    if (maxRms === 0) maxRms = 1;

    for (let i = 0; i < times.length; i++) {
        const x = X(times[i]);
        const a = (rmsArr[i] / maxRms) * (H / 2 - 6);
        g.moveTo(x, mid - a); g.lineTo(x, mid + a);
    }
    g.stroke(); g.globalAlpha = 1;

    // Playhead cursor
    if (isFinite(t)) {
        g.strokeStyle = "#f8fafc"; g.lineWidth = 1.5;
        g.beginPath(); g.moveTo(X(t), 0); g.lineTo(X(t), H); g.stroke();
    }
}

function drawRealtime(t) {
    const cv = document.getElementById('realtime-canvas');
    if (!cv) return;
    const g = cv.getContext("2d");
    const W = cv.width = cv.clientWidth;
    const H = cv.height = cv.clientHeight;
    g.clearRect(0, 0, W, H);
    
    const f = STATE.features;
    if (!f || !f.timestamps) return;
    const duration = STATE.metadata.duration_seconds || 1;
    const X = sec => (sec / duration) * W;

    // Draw area up to playhead
    const cut = isFinite(t) ? X(t) : 0;
    g.save(); g.beginPath(); g.rect(0, 0, cut, H); g.clip();

    // Energy envelope area
    const nrgArr = f.energy || [];
    const times = f.timestamps || [];
    let maxNrg = 0;
    for (let i = 0; i < nrgArr.length; i++) if (nrgArr[i] > maxNrg) maxNrg = nrgArr[i];
    if (maxNrg === 0) maxNrg = 1;

    g.fillStyle = "rgba(56, 189, 248, 0.25)"; g.beginPath(); g.moveTo(0, H);
    for (let i = 0; i < times.length; i++) {
        g.lineTo(X(times[i]), H - (nrgArr[i] / maxNrg) * (H - 14));
    }
    g.lineTo(W, H); g.fill();
    g.restore();

    // Playhead cursor
    if (isFinite(t)) {
        g.strokeStyle = "#f8fafc"; g.lineWidth = 1.5;
        g.beginPath(); g.moveTo(cut, 0); g.lineTo(cut, H); g.stroke();
    }
}

function renderSpeakerAnalysis() {
    const stats = STATE.raw.summary?.speaker_statistics || {};
    const tbody = document.querySelector('#speaker-table tbody');
    tbody.innerHTML = '';

    const labels = [];
    const values = [];

    for (const [spk, info] of Object.entries(stats)) {
        labels.push(spk);
        values.push(info.talk_percentage);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color: ${spk === 'Speaker 0' ? '#60a5fa' : '#f87171'}; font-weight: bold;">${spk}</td>
            <td>${info.talk_time_seconds.toFixed(1)}s (${info.talk_percentage.toFixed(1)}%)</td>
            <td>${info.turn_count}</td>
            <td>${info.average_turn_duration_seconds.toFixed(1)}s</td>
            <td>${(info.avg_speaking_rate_sps || 0).toFixed(1)} sps</td>
        `;
        tbody.appendChild(tr);
    }

    // Conversational Dynamics
    const dynBody = document.querySelector('#speaker-dynamics-table tbody');
    if (dynBody) dynBody.innerHTML = '';
    
    const segs = STATE.raw.diarization?.segments || [];
    const sortedSegs = [...segs].sort((a, b) => a.start - b.start);
    const mergedTurns = [];
    if (sortedSegs.length > 0) {
        let currentTurn = { ...sortedSegs[0] };
        for (let i = 1; i < sortedSegs.length; i++) {
            const s = sortedSegs[i];
            if (s.speaker === currentTurn.speaker) {
                currentTurn.end = Math.max(currentTurn.end, s.end);
                currentTurn.duration = currentTurn.end - currentTurn.start;
            } else {
                mergedTurns.push(currentTurn);
                currentTurn = { ...s };
            }
        }
        mergedTurns.push(currentTurn);
    }
    
    let spkDelays = {};
    let spkLongest = {};
    let spkInterrupts = {};
    Object.keys(stats).forEach(spk => {
        spkDelays[spk] = [];
        spkLongest[spk] = 0;
        spkInterrupts[spk] = 0;
    });

    mergedTurns.forEach((s, idx) => {
        if (s.duration > (spkLongest[s.speaker] || 0)) {
            spkLongest[s.speaker] = s.duration;
        }
        if (idx > 0) {
            const prev = mergedTurns[idx - 1];
            const gap = s.start - prev.end;
            if (gap >= 0) {
                spkDelays[s.speaker].push(gap);
            } else if (gap < -0.2) {
                spkInterrupts[s.speaker]++;
            }
        }
    });

    if (dynBody) {
        Object.keys(stats).forEach(spk => {
            const longest = spkLongest[spk] || 0;
            const interrupts = spkInterrupts[spk] || 0;
            const delays = spkDelays[spk] || [];
            const avgDelay = delays.length > 0 ? (delays.reduce((a,b)=>a+b,0) / delays.length) : 0;
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="color: ${spk === 'Speaker 0' ? '#60a5fa' : '#f87171'}; font-weight: bold;">${spk}</td>
                <td>${longest.toFixed(1)}s</td>
                <td>${avgDelay.toFixed(2)}s</td>
                <td>${interrupts}</td>
            `;
            dynBody.appendChild(tr);
        });
    }

    if (values.length > 0) {
        const data = [{
            values: values,
            labels: labels,
            type: 'pie',
            hole: .4,
            marker: { colors: ['#3b82f6', '#ef4444', '#10b981'] },
            textinfo: 'label+percent',
            hoverinfo: 'label+percent',
        }];
        const layout = {
            plot_bgcolor: 'transparent',
            paper_bgcolor: 'transparent',
            font: { color: '#94a3b8', family: 'Inter' },
            margin: { l: 10, r: 10, t: 10, b: 10 },
            showlegend: true
        };
        Plotly.newPlot('pie-chart', data, layout, { responsive: true });
    }
}

function renderDiarization() {
    const segments = STATE.raw.diarization?.segments || [];
    const dur = STATE.metadata.duration_seconds || 1;

    // Raw Table
    const tbody = document.querySelector('#raw-diarization-table tbody');
    tbody.innerHTML = '';

    // Visualizer
    const vis = document.getElementById('diarization-visualizer');
    vis.innerHTML = '<div id="cursor-line"></div>';

    segments.forEach(seg => {
        // Table row
        tbody.innerHTML += `<tr><td>${seg.speaker}</td><td>${seg.start.toFixed(2)}</td><td>${seg.end.toFixed(2)}</td><td>${seg.duration.toFixed(2)}</td></tr>`;

        // Visualizer block
        const pctStart = (seg.start / dur) * 100;
        const pctWidth = (seg.duration / dur) * 100;
        const color = seg.speaker === 'Speaker 0' ? '#3b82f6' : '#ef4444';

        const block = document.createElement('div');
        block.className = 'seg-box';
        block.style.left = `${pctStart}%`;
        block.style.width = `${pctWidth}%`;
        block.style.background = color;
        block.title = `${seg.speaker}: ${seg.start.toFixed(1)}s - ${seg.end.toFixed(1)}s`;

        block.onclick = () => seekAudio(seg.start);
        vis.appendChild(block);
    });
}

function renderScoreBreakdown() {
    const container = document.getElementById('score-breakdown-container');
    container.innerHTML = '';

    const explanations = STATE.analysis.explanations || {};
    const keys = [
        "overall_call_health",
        "audio_quality",
        "recording_reliability",
        "voice_stability",
        "conversation_flow",
        "conversation_balance",
        "speech_activity"
    ];

    keys.forEach(key => {
        const info = explanations[key];
        if (!info) return;

        const val = info.value || 0;
        const grade = info.grade || "n/a";
        const title = info.name || key;

        let color = '#f59e0b';
        if (val >= 90) color = '#10b981';
        else if (val >= 75) color = '#34d399';
        else if (val < 60) color = '#ef4444';

        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.gap = '30px';
        row.style.alignItems = 'flex-start';
        row.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
        row.style.paddingBottom = '15px';

        // Col 1: Score Block
        const scoreCol = document.createElement('div');
        scoreCol.style.flex = '1.5';
        scoreCol.innerHTML = `
            <div style="background-color: #161920; padding: 15px; border-radius: 8px; border-left: 5px solid ${color};">
                <h5 style="margin: 0; color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">${title}</h5>
                <h2 style="margin: 8px 0 2px 0; color: ${color}; font-weight: bold; font-size: 28px;">${val}/100</h2>
                <span style="color: #94a3b8; font-size: 12px; font-weight: 500;">${grade}</span>
            </div>
        `;
        row.appendChild(scoreCol);

        // Col 2: Positives
        const posCol = document.createElement('div');
        posCol.style.flex = '2';
        let posHTML = `<div style="font-weight: 600; margin-bottom: 8px;">Positives (✓)</div>`;
        if (info.positives && info.positives.length > 0) {
            info.positives.forEach(p => posHTML += `<div style="color: #10b981; font-size: 13px; margin-bottom: 6px;">✓ ${p}</div>`);
        } else {
            posHTML += `<div style="color: var(--text-muted); font-size: 12px;">No positive contributing factors detected.</div>`;
        }
        posCol.innerHTML = posHTML;
        row.appendChild(posCol);

        // Col 3: Negatives
        const negCol = document.createElement('div');
        negCol.style.flex = '2';
        let negHTML = `<div style="font-weight: 600; margin-bottom: 8px;">Negatives (✗)</div>`;

        let negs = info.negatives || [];
        if (negs.length === 0 && val <= 75) {
            negs = [`General degradation detected in ${title.toLowerCase()} continuous metrics`];
        }

        if (negs.length > 0) {
            negs.forEach(n => negHTML += `<div style="color: #ef4444; font-size: 13px; margin-bottom: 6px;">✗ ${n}</div>`);
        } else {
            negHTML += `<div style="color: var(--text-muted); font-size: 12px;">No negative contributing factors detected.</div>`;
        }
        negCol.innerHTML = negHTML;
        row.appendChild(negCol);

        container.appendChild(row);
    });
}

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = (e) => {
            const target = e.target.dataset.tab;

            // Deactivate all
            e.target.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.parentElement.parentElement.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));

            // Activate clicked
            e.target.classList.add('active');
            document.getElementById(target).classList.remove('hidden');
            // If it's a grid tab, make sure display is grid
            if (target === 'tab-scores' || target === 'tab-speech' || target === 'tab-conv') {
                document.getElementById(target).style.display = 'grid';
            } else {
                document.getElementById(target).style.display = 'block';
            }
        };
    });
}

// ==========================================
// SVG GAUGE (FRIEND'S UI PORT)
// ==========================================
function gaugeSVG(score, grade) {
    const GRADE_COLORS = { A: "var(--color-excellent)", B: "#84cc16", C: "var(--color-fair)", D: "#f97316", E: "var(--color-poor)" };
    const ZONES = [[0,25,"#ef4444"],[25,45,"#f97316"],[45,65,"#eab308"],[65,80,"#84cc16"],[80,100,"#10b981"]];
    const cx = 90, cy = 88, r = 70, a0 = -210, a1 = 30; // 240-degree sweep
    const ang = deg => deg * Math.PI / 180;
    const pt = (deg, rad) => [cx + rad * Math.cos(ang(deg)), cy + rad * Math.sin(ang(deg))];
    const arc = (from, to, rad) => {
        const [x1, y1] = pt(from, rad), [x2, y2] = pt(to, rad);
        return `M ${x1} ${y1} A ${rad} ${rad} 0 ${(to - from) > 180 ? 1 : 0} 1 ${x2} ${y2}`;
    };
    const zonePaths = ZONES.map(([lo, hi, col]) => {
        const f = a0 + (a1 - a0) * lo / 100, t = a0 + (a1 - a0) * hi / 100;
        return `<path d="${arc(f, t, r)}" stroke="${col}" stroke-width="12" fill="none" stroke-linecap="butt" opacity="0.85"/>`;
    }).join("");
    const nd = a0 + (a1 - a0) * Math.max(0, Math.min(100, score)) / 100;
    const [nx, ny] = pt(nd, r - 16);
    const ticks = [0,25,45,65,80,100].map(v => {
        const d = a0 + (a1 - a0) * v / 100; const [tx, ty] = pt(d, r + 14);
        return `<text x="${tx}" y="${ty}" fill="#94a3b8" font-size="8" text-anchor="middle">${v}</text>`;
    }).join("");
    return `<svg width="180" height="130" viewBox="0 0 180 130">
        ${zonePaths}${ticks}
        <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="#e2e8f0" stroke-width="3" stroke-linecap="round"/>
        <circle cx="${cx}" cy="${cy}" r="5" fill="#e2e8f0"/>
        <text x="${cx}" y="${cy + 26}" fill="#e2e8f0" font-size="22" font-weight="700" text-anchor="middle">${Number(score).toFixed(1)}</text>
        <text x="${cx}" y="${cy + 40}" fill="${GRADE_COLORS[grade] || '#94a3b8'}" font-size="13" font-weight="700" text-anchor="middle">grade ${grade}</text>
    </svg>`;
}

window.onload = init;
// ==========================================
// EXPORT FUNCTIONALITY (CALL INVESTIGATION PACKAGE)
// ==========================================

function getSeverityAndAction(score) {
    if (score < 60) return { severity: "High", action: "Review" };
    if (score < 75) return { severity: "Medium", action: "Monitor" };
    return { severity: "Low", action: "No Action" };
}

function generateExecutiveSummary() {
    const meta = STATE.metadata || {};
    const scores = STATE.raw.analysis_results?.scores || {};
    const expl = STATE.raw.analysis_results?.explanations || {};
    
    // Find worst pillar for primary finding
    let worstPillar = null;
    let worstScore = 100;
    for (const [key, data] of Object.entries(expl)) {
        if (key !== "overall_call_health" && data.value < worstScore) {
            worstScore = data.value;
            worstPillar = key;
        }
    }
    
    let primaryFinding = "";
    let businessImpact = "";
    let recommendedAction = "";
    
    if (worstPillar && expl[worstPillar]) {
        const worstData = expl[worstPillar];
        primaryFinding = (worstData.negatives && worstData.negatives.length > 0) ? worstData.negatives[0].split(" at ")[0] : "No major issues";
        
        // Map business impact based on pillar
        if (worstPillar === "voice_stability") {
            businessImpact = "Possible customer distress — escalation risk";
            recommendedAction = "Review voice stability segment";
        } else if (worstPillar === "conversation_flow") {
            businessImpact = "Failed/incomplete interaction — possible callback required";
            recommendedAction = "Review response delay/interruption segment";
        } else if (worstPillar === "audio_quality") {
            businessImpact = "Recording unreliable for compliance audit";
            recommendedAction = "Escalate to IT/vendor";
        } else if (worstPillar === "conversation_balance") {
            businessImpact = "One-sided interaction — training opportunity";
            recommendedAction = "Schedule agent coaching";
        } else if (worstPillar === "collection_confidence") {
            businessImpact = "Abrupt termination — possible failed collection";
            recommendedAction = "Flag for re-attempt";
        } else if (worstPillar === "speech_activity") {
            businessImpact = "Excessive dead air — system or connection issue";
            recommendedAction = "Check for connection issues";
        }
    }

    let overallGrade = expl.overall_call_health?.grade || "N/A";
    let priority = "Low";
    if (scores.overall_call_health < 40) priority = "Critical";
    else if (scores.overall_call_health < 60) priority = "High";
    else if (scores.overall_call_health < 75) priority = "Medium";

    let recordingStatus = "Clean";
    const dropouts = STATE.raw.engineered_features?.audio_quality?.dropout_count || 0;
    const cutoff = STATE.raw.engineered_features?.timeline_anomalies?.collection_confidence?.abrupt_cutoff || [];
    if (dropouts > 0 || cutoff.length > 0) recordingStatus = "Degraded";

    let csv = "Section,Field,Value\n";
    csv += `Call Metadata,Call ID,${STATE.currentFileBase.replace('.json', '')}\n`;
    csv += `Call Metadata,Recording Name,${meta.source_file || "N/A"}\n`;
    csv += `Call Metadata,Campaign,\n`;
    csv += `Call Metadata,Call Type,\n`;
    csv += `Call Metadata,Processed At,${meta.processed_at || "N/A"}\n`;
    csv += `Call Metadata,Duration Seconds,${meta.duration_seconds || "0"}\n`;
    
    csv += `Overall Assessment,Overall Health Score,${scores.overall_call_health || "0"}\n`;
    csv += `Overall Assessment,Overall Grade,${overallGrade}\n`;
    csv += `Overall Assessment,Gate Multiplier,${scores.gate_multiplier || "1.0"}\n`;
    csv += `Overall Assessment,Review Required,${overallGrade === "Poor" ? "Yes" : "No"}\n`;
    csv += `Overall Assessment,Recording Status,${recordingStatus}\n`;
    csv += `Overall Assessment,Priority,${priority}\n`;
    
    csv += `Pillar Scores,Audio Quality,${scores.audio_quality || "0"} (${expl.audio_quality?.grade || "N/A"})\n`;
    csv += `Pillar Scores,Voice Stability,${scores.voice_stability || "0"} (${expl.voice_stability?.grade || "N/A"})\n`;
    csv += `Pillar Scores,Conversation Flow,${scores.conversation_flow || "0"} (${expl.conversation_flow?.grade || "N/A"})\n`;
    csv += `Pillar Scores,Conversation Balance,${scores.conversation_balance || "0"} (${expl.conversation_balance?.grade || "N/A"})\n`;
    csv += `Pillar Scores,Speech Activity,${scores.speech_activity || "0"} (${expl.speech_activity?.grade || "N/A"})\n`;
    csv += `Pillar Scores,Collection Confidence,${scores.collection_confidence || "0"} (${expl.collection_confidence?.grade || "N/A"})\n`;
    
    csv += `Business Summary,Primary Finding,"${primaryFinding}"\n`;
    csv += `Business Summary,Business Impact,"${businessImpact}"\n`;
    csv += `Business Summary,Recommended Action,"${recommendedAction}"\n`;
    
    return csv;
}

function parseAnomalyTimes(timeString) {
    if (!timeString) return { start: "", end: "", duration: "" };
    const parts = timeString.split(" - ");
    if (parts.length === 2) {
        // e.g. "01:04 - 01:06"
        const [m1, s1] = parts[0].split(":");
        const [m2, s2] = parts[1].split(":");
        const startSec = parseInt(m1)*60 + parseInt(s1);
        const endSec = parseInt(m2)*60 + parseInt(s2);
        return { start: parts[0], end: parts[1], duration: endSec - startSec };
    } else {
        // e.g. "01:04"
        return { start: parts[0], end: parts[0], duration: 0 };
    }
}

function generateEvidenceRegister() {
    let csv = "evidence_id,pillar,issue_description,start_time,end_time,duration_seconds,observed_value,expected_range,severity,score_impact,recommendation,audio_clip\n";
    let id = 1;
    
    const eng = STATE.raw.engineered_features || {};
    const anomalies = eng.timeline_anomalies || {};
    const scores = STATE.raw.analysis_results?.scores || {};
    
    function addRow(pillar, desc, timeStr, obs, exp, rec) {
        const t = parseAnomalyTimes(timeStr);
        const pScore = scores[pillar.toLowerCase().replace(" ", "_")] || 0;
        const { severity, action } = getSeverityAndAction(pScore);
        if (severity === "Low" || severity === "No Action") return; // Only log issues
        
        // Pseudo score impact (rough estimate based on how far from 100)
        const impact = -Math.round((100 - pScore) / 3); 
        
        csv += `${id++},${pillar},"${desc}",${t.start},${t.end},${t.duration},"${obs}","${exp}",${severity},${impact},"${rec}",\n`;
    }

    // Audio Quality
    (anomalies.audio_quality?.noise_spikes || []).forEach(t => {
        addRow("Audio Quality", "Background noise spike", t, `${eng.audio_quality?.average_snr} dB avg`, "> 22 dB", "Review environment noise");
    });
    (anomalies.audio_quality?.dropouts || []).forEach(t => {
        addRow("Audio Quality", "Audio transmission dropout", t, `${eng.audio_quality?.dropout_count} total`, "0 dropouts", "Escalate to IT");
    });

    // Voice Stability
    (anomalies.voice_stability?.voice_cracks || []).forEach(t => {
        addRow("Voice Stability", "Voice distortion/crack", t, `${eng.voice_stability?.avg_jitter_pct}% jitter`, "< 1.5%", "Review for emotional distress");
    });

    // Conversation Flow
    (anomalies.conversation_flow?.response_delays || []).forEach(t => {
        addRow("Conversation Flow", "Awkward response delay", t, `${eng.conversation_behaviour?.response_latency}s latency`, "< 2.0s", "Investigate system lag");
    });
    (anomalies.conversation_flow?.interruptions || []).forEach(t => {
        addRow("Conversation Flow", "Severe interruption", t, `${eng.response_dynamics?.overlap_count} overlaps`, "0 overlaps", "Review interruption segments");
    });
    (anomalies.conversation_flow?.awkward_pauses || []).forEach(t => {
        addRow("Conversation Flow", "Awkward mid-turn pause", t, `${eng.speech_behaviour?.average_pause_duration}s avg pause`, "< 3.0s", "Investigate hesitation");
    });

    // Conversation Balance
    (anomalies.conversation_balance?.monologues || []).forEach(t => {
        addRow("Conversation Balance", "Prolonged monologue", t, `${eng.conversation_behaviour?.conversation_balance}% imbalance`, "< 60%", "Coach on active listening");
    });

    // Collection Confidence
    (anomalies.collection_confidence?.abrupt_cutoff || []).forEach(t => {
        addRow("Collection Confidence", "Abrupt hang-up/cutoff", t, "Cutoff detected", "Clean termination", "Flag for re-attempt");
    });

    // General pillar explainability negatives that don't have explicit timestamps in anomalies
    const expl = STATE.raw.analysis_results?.explanations || {};
    if (expl.voice_stability?.negatives) {
        expl.voice_stability.negatives.forEach(n => {
            if (n.includes("High pitch fluctuations")) {
                addRow("Voice Stability", "High pitch fluctuations", "", `${eng.voice_stability?.pitch_stability} Hz std`, "< 28 Hz std", "Review for emotional distress");
            }
        });
    }

    return csv;
}

function generateSpeakerAnalysis() {
    let csv = "speaker,talk_time_seconds,talk_time_pct,is_dominant,segment_count,average_turn_seconds,longest_turn_seconds,avg_response_delay_seconds,interruptions_caused,avg_speaking_rate_sps\n";
    
    const diar = STATE.raw.diarization || {};
    const stats = diar.statistics || {};
    const talkTimes = stats.talk_times || {};
    const eng = STATE.raw.engineered_features || {};
    const cb = eng.conversation_behaviour || {};
    const ratios = cb.speaker_talk_ratio || {};
    const segs = diar.segments || [];
    
    // Merge contiguous segments by the same speaker
    const sortedSegs = [...segs].sort((a, b) => a.start - b.start);
    const mergedTurns = [];
    if (sortedSegs.length > 0) {
        let currentTurn = { ...sortedSegs[0] };
        for (let i = 1; i < sortedSegs.length; i++) {
            const s = sortedSegs[i];
            if (s.speaker === currentTurn.speaker) {
                currentTurn.end = Math.max(currentTurn.end, s.end);
                currentTurn.duration = currentTurn.end - currentTurn.start;
            } else {
                mergedTurns.push(currentTurn);
                currentTurn = { ...s };
            }
        }
        mergedTurns.push(currentTurn);
    }
    
    // Calculate interruptions caused and avg delays per speaker
    let spkDelays = {};
    let spkTurns = {};
    let spkLongest = {};
    let spkTotalDur = {};
    let spkInterrupts = {};
    
    Object.keys(talkTimes).forEach(spk => {
        spkDelays[spk] = [];
        spkTurns[spk] = 0;
        spkLongest[spk] = 0;
        spkTotalDur[spk] = 0;
        spkInterrupts[spk] = 0;
    });
    
    mergedTurns.forEach((s, idx) => {
        if (!spkTurns[s.speaker]) {
            spkTurns[s.speaker] = 0;
            spkLongest[s.speaker] = 0;
            spkTotalDur[s.speaker] = 0;
            spkDelays[s.speaker] = [];
            spkInterrupts[s.speaker] = 0;
        }
        spkTurns[s.speaker]++;
        spkTotalDur[s.speaker] += s.duration;
        if (s.duration > spkLongest[s.speaker]) spkLongest[s.speaker] = s.duration;
        
        if (idx > 0) {
            const prev = mergedTurns[idx - 1];
            const gap = s.start - prev.end;
            if (gap >= 0) {
                spkDelays[s.speaker].push(gap);
            } else if (gap < -0.2) {
                spkInterrupts[s.speaker]++;
            }
        }
    });

    // Determine dominant speaker
    let dominant = null;
    let maxT = 0;
    for (const spk in talkTimes) {
        if (talkTimes[spk] > maxT) {
            maxT = talkTimes[spk];
            dominant = spk;
        }
    }

    for (const spk in talkTimes) {
        const pct = ratios[spk] || 0;
        const domStr = spk === dominant ? "Yes" : "No";
        const turns = spkTurns[spk] || 0;
        const avgTurn = turns > 0 ? (spkTotalDur[spk] / turns) : 0;
        const longest = spkLongest[spk] || 0;
        
        const delays = spkDelays[spk] || [];
        const avgDelay = delays.length > 0 ? (delays.reduce((a,b)=>a+b,0) / delays.length) : 0;
        const interrupts = spkInterrupts[spk] || 0;
        const spkStats = stats.speaker_statistics?.[spk] || {};
        const sps = spkStats.avg_speaking_rate_sps || 0;
        
        csv += `${spk},${talkTimes[spk].toFixed(2)},${pct.toFixed(1)}%,${domStr},${turns},${avgTurn.toFixed(2)},${longest.toFixed(2)},${avgDelay.toFixed(2)},${interrupts},${sps.toFixed(2)}\n`;
    }
    
    return csv;
}

function generateRecommendations() {
    let csv = "priority,recommendation,pillar,expected_benefit\n";
    const scores = STATE.raw.analysis_results?.scores || {};
    const eng = STATE.raw.engineered_features || {};
    const anomalies = eng.timeline_anomalies || {};
    
    let hasRec = false;

    if (scores.collection_confidence < 75 || (anomalies.collection_confidence?.abrupt_cutoff?.length > 0)) {
        csv += `Critical,Flag for re-attempt — call terminated abruptly,Collection Confidence,Save potential lost collection\n`;
        hasRec = true;
    }
    if (scores.voice_stability < 60) {
        csv += `High,Review call for customer distress or agitation indicators,Voice Stability,Improved customer experience and compliance\n`;
        hasRec = true;
    }
    if (anomalies.conversation_flow?.response_delays?.length > 0) {
        csv += `High,Investigate bot/agent response latency — possible system lag,Conversation Flow,Faster resolution and better UX\n`;
        hasRec = true;
    }
    if (anomalies.conversation_flow?.interruptions?.length > 0) {
        csv += `High,Review interruption segments — possible aggressive behavior,Conversation Flow,Ensure agent compliance and politeness\n`;
        hasRec = true;
    }
    if (scores.audio_quality < 60) {
        csv += `High,Escalate to IT/vendor — recording quality below compliance threshold,Audio Quality,Maintain auditable records\n`;
        hasRec = true;
    }
    if (scores.conversation_balance < 60) {
        csv += `Medium,Schedule agent coaching — conversation dominated by one party,Conversation Balance,More effective two-way communication\n`;
        hasRec = true;
    }
    if (scores.speech_activity < 60) {
        csv += `Medium,Check for connection issues — excessive silence detected,Speech Activity,Reduce dead air and wasted time\n`;
        hasRec = true;
    }

    if (!hasRec) {
        csv += `Low,No action required — call meets quality standards,All,N/A\n`;
    }

    return csv;
}

function generateDetailedTimeline() {
    let csv = "timestamp_sec,pitch_hz,rms,snr_db,speech_quality_proxy,vad_active\n";
    const timeline = STATE.raw.features?.timeline || [];
    timeline.forEach(row => {
        csv += `${row.timestamp},${row.raw?.prosody?.pitch_hz || ""},${row.raw?.acoustic?.rms || ""},${row.raw?.quality?.snr_db || ""},${row.raw?.quality?.speech_quality_proxy || ""},${row.derived?.speech?.active || false}\n`;
    });
    return csv;
}

async function handleExportZip() {
    if (!STATE.raw) return alert("Please select a file first.");
    
    const zip = new JSZip();
    const baseName = STATE.currentFileBase.replace(".json", "").replace("_features", "");
    const folder = zip.folder(`Call_Investigation_${baseName}`);
    
    folder.file("01_Executive_Summary.csv", generateExecutiveSummary());
    folder.file("02_Evidence_Register.csv", generateEvidenceRegister());
    folder.file("03_Speaker_Analysis.csv", generateSpeakerAnalysis());
    folder.file("04_Recommendations.csv", generateRecommendations());
    
    const content = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(content);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Call_Investigation_${baseName}.zip`;
    a.click();
    URL.revokeObjectURL(url);
}

function handleExportTimeline() {
    if (!STATE.raw) return alert("Please select a file first.");
    const baseName = STATE.currentFileBase.replace(".json", "").replace("_features", "");
    
    const csv = generateDetailedTimeline();
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `05_Detailed_Timeline_${baseName}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// Bind events in init()
function bindExportButtons() {
    const btnZip = document.getElementById("btn-export-report");
    const btnTimeline = document.getElementById("btn-export-timeline");
    const btnBatch = document.getElementById("btn-export-batch");
    if (btnZip) btnZip.addEventListener("click", handleExportZip);
    if (btnTimeline) btnTimeline.addEventListener("click", handleExportTimeline);
    if (btnBatch) btnBatch.addEventListener("click", handleExportBatchCSV);
}

// ==========================================
// BATCH CSV EXPORT — All analyzed calls → single CSV
// ==========================================

/**
 * Safely escape a value for CSV: wrap in quotes if it contains commas, quotes, or newlines.
 */
function csvEscape(val) {
    if (val === null || val === undefined) return "";
    const str = String(val);
    if (str.includes(",") || str.includes('"') || str.includes("\n")) {
        return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
}

/**
 * Determine the business impact and recommended action based on the worst-scoring pillar.
 * Mirrors the logic in generateExecutiveSummary() but operates on raw JSON data.
 */
function deriveBatchBusinessFields(explanations) {
    if (!explanations) return { impact: "", action: "", nextStep: "No action required" };

    let worstPillar = null;
    let worstScore = 100;
    let secondWorstPillar = null;
    let secondWorstScore = 100;

    for (const [key, data] of Object.entries(explanations)) {
        if (key === "overall_call_health") continue;
        const val = data.value ?? 100;
        if (val < worstScore) {
            secondWorstPillar = worstPillar;
            secondWorstScore = worstScore;
            worstPillar = key;
            worstScore = val;
        } else if (val < secondWorstScore) {
            secondWorstPillar = key;
            secondWorstScore = val;
        }
    }

    const impactMap = {
        voice_stability: { impact: "Possible customer distress — escalation risk", action: "Review voice stability segment" },
        conversation_flow: { impact: "Failed/incomplete interaction — possible callback required", action: "Review response delay/interruption segment" },
        audio_quality: { impact: "Recording unreliable for compliance audit", action: "Escalate to IT/vendor" },
        conversation_balance: { impact: "One-sided interaction — training opportunity", action: "Schedule agent coaching" },
        collection_confidence: { impact: "Abrupt termination — possible failed collection", action: "Flag for re-attempt" },
        speech_activity: { impact: "Excessive dead air — system or connection issue", action: "Check for connection issues" },
    };

    const mapped = impactMap[worstPillar] || { impact: "", action: "" };
    const needsReview = worstScore < 75;

    return {
        impact: mapped.impact,
        action: mapped.action,
        nextStep: needsReview ? "Listen to investigation timestamps" : "No action required",
        worstPillar,
        worstScore,
        secondWorstPillar,
        secondWorstScore,
    };
}

/**
 * Extract one row (array of 54 values) from a single parsed JSON file.
 */
function extractBatchRow(data, callId) {
    const meta = data.metadata || {};
    const summary = data.summary || {};
    const scores = (data.analysis_results?.scores) || {};
    const expl = (data.analysis_results?.explanations) || {};
    const eng = data.engineered_features || {};
    const aq = eng.audio_quality || {};
    const vs = eng.voice_stability || {};
    const sb = eng.speech_behaviour || {};
    const cb = eng.conversation_behaviour || {};
    const vq = eng.voice_quality || {};
    const rd = eng.response_dynamics || {};
    const anomalies = eng.timeline_anomalies || {};

    // --- Overall Assessment derived fields ---
    const overallScore = scores.overall_call_health ?? "";
    const overallGrade = expl.overall_call_health?.grade ?? "";

    // Recording Status: FAIL if dropouts > 0 or abrupt cutoff detected
    const dropoutCount = aq.dropout_count ?? 0;
    const cutoffs = anomalies.collection_confidence?.abrupt_cutoff || [];
    const recordingStatus = (dropoutCount > 0 || cutoffs.length > 0) ? "FAIL" : "PASS";

    // Review Required
    const anyPoor = Object.entries(expl).some(([k, v]) => k !== "overall_call_health" && v.grade === "Poor");
    const reviewRequired = (overallScore !== "" && overallScore < 70) || recordingStatus === "FAIL" || anyPoor ? "Yes" : "No";

    // Priority
    let priority = "Low";
    if (overallScore !== "" && overallScore < 40) priority = "Critical";
    else if (overallScore !== "" && overallScore < 60) priority = "High";
    else if (overallScore !== "" && overallScore < 75) priority = "Medium";

    // --- Investigation Summary ---
    const biz = deriveBatchBusinessFields(expl);

    // Primary / Secondary issue: first negative of worst / second-worst pillar
    const primaryIssue = biz.worstPillar && expl[biz.worstPillar]?.negatives?.length
        ? expl[biz.worstPillar].negatives[0].split(" at ")[0]
        : "";
    const secondaryIssue = biz.secondWorstPillar && expl[biz.secondWorstPillar]?.negatives?.length
        ? expl[biz.secondWorstPillar].negatives[0].split(" at ")[0]
        : "";

    // Count all issues across all pillars
    let totalIssues = 0;
    let criticalIssues = 0;
    let highSeverityIssues = 0;
    let mediumSeverityIssues = 0;
    for (const [key, val] of Object.entries(expl)) {
        if (key === "overall_call_health") continue;
        totalIssues += (val.negatives?.length || 0);
        if (val.grade === "Poor") criticalIssues++;
        else if (val.grade === "Fair") highSeverityIssues++;
        else if (val.grade === "Good") mediumSeverityIssues++;
    }

    // --- Evidence Summary ---
    let evidenceCount = 0;
    const evidenceTypeSet = new Set();
    for (const [category, issues] of Object.entries(anomalies)) {
        if (typeof issues !== "object" || issues === null) continue;
        for (const [issueType, timestamps] of Object.entries(issues)) {
            if (Array.isArray(timestamps) && timestamps.length > 0) {
                evidenceCount += timestamps.length;
                evidenceTypeSet.add(issueType.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()));
            }
        }
    }
    const evidenceTypes = Array.from(evidenceTypeSet).join("; ");

    // Interruptions count from timeline anomalies
    const interruptionCount = (anomalies.conversation_flow?.interruptions || []).length;

    // Clipping events — use clipping array from anomalies or fallback to 0
    const clippingEvents = (anomalies.audio_quality?.clipping || []).length;

    // --- Build the row ---
    return [
        // Section 1 — Call Information
        callId,
        meta.source_file ?? "",
        meta.processed_at ?? "",
        meta.duration_seconds ?? "",
        "",  // Call Type — not in current schema
        summary.speaker_count ?? "",
        summary.dominant_speaker ?? "",

        // Section 2 — Overall Assessment
        overallScore,
        overallGrade,
        reviewRequired,
        priority,
        recordingStatus,
        scores.gate_multiplier ?? "",

        // Section 3 — Pillar Scores
        scores.audio_quality ?? "",
        expl.audio_quality?.grade ?? "",
        scores.voice_stability ?? "",
        expl.voice_stability?.grade ?? "",
        scores.conversation_flow ?? "",
        expl.conversation_flow?.grade ?? "",
        scores.conversation_balance ?? "",
        expl.conversation_balance?.grade ?? "",
        scores.speech_activity ?? "",
        expl.speech_activity?.grade ?? "",
        scores.collection_confidence ?? "",
        expl.collection_confidence?.grade ?? "",

        // Section 4 — Key Audio Statistics
        aq.average_snr ?? summary.average_snr_db ?? "",
        vq.avg_speech_quality ?? "",
        summary.average_pitch_hz ?? "",
        summary.average_loudness_db ?? "",
        sb.speech_percentage ?? "",
        sb.silence_percentage ?? "",
        rd.avg_response_latency_seconds ?? "",

        // Section 5 — Conversation Statistics
        cb.speaker_change_count ?? "",
        cb.turn_count ?? "",
        sb.pause_count ?? "",
        sb.longest_pause ?? "",
        aq.dropout_count ?? 0,
        clippingEvents,
        interruptionCount,
        rd.overlap_count ?? "",

        // Section 6 — Investigation Summary
        primaryIssue,
        secondaryIssue,
        totalIssues,
        criticalIssues,
        highSeverityIssues,
        mediumSeverityIssues,

        // Section 7 — AI Recommendations
        biz.impact,
        biz.action,
        biz.nextStep,

        // Section 8 — Evidence Summary
        evidenceCount,
        evidenceTypes,

        // Section 9 — File References
        `${callId}_report.zip`,
        `${callId}_features.json`,
        meta.source_file ?? "",
    ];
}

/**
 * Main batch export handler:
 * 1. Fetch directory listing of all JSON files
 * 2. Load each JSON
 * 3. Build CSV with 54 columns
 * 4. Trigger download
 */
async function handleExportBatchCSV() {
    const btn = document.getElementById("btn-export-batch");
    const originalText = btn.textContent;
    btn.textContent = "⏳ Building CSV...";
    btn.disabled = true;
    btn.style.opacity = "0.7";

    try {
        // Step 1: Fetch directory listing to discover JSON files
        const dirRes = await fetch("../data/outputs/");
        const dirText = await dirRes.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(dirText, "text/html");
        const links = Array.from(doc.querySelectorAll("a"));

        const jsonFiles = [];
        links.forEach(a => {
            let filename = a.getAttribute("href");
            if (filename) {
                filename = decodeURIComponent(filename);
                if (filename.endsWith("_features.json") && !filename.includes("copy")) {
                    jsonFiles.push(filename);
                }
            }
        });

        if (jsonFiles.length === 0) {
            alert("No analyzed JSON files found in data/outputs/.");
            return;
        }

        // Step 2: Load each JSON file
        const rows = [];
        for (let i = 0; i < jsonFiles.length; i++) {
            const fname = jsonFiles[i];
            btn.textContent = `⏳ Processing ${i + 1}/${jsonFiles.length}...`;

            try {
                const res = await fetch(`../data/outputs/${fname}`);
                if (!res.ok) continue;
                const data = await res.json();
                const callId = fname.replace("_features.json", "");
                rows.push(extractBatchRow(data, callId));
            } catch (err) {
                console.warn(`Skipping ${fname}:`, err);
            }
        }

        if (rows.length === 0) {
            alert("No valid JSON files could be parsed.");
            return;
        }

        // Step 3: Build CSV
        const headers = [
            // Section 1 — Call Information
            "Call ID", "Source File", "Processing Timestamp", "Call Duration (sec)",
            "Call Type", "Speaker Count", "Dominant Speaker",
            // Section 2 — Overall Assessment
            "Overall Health Score", "Overall Grade", "Review Required", "Priority",
            "Recording Status", "Gate Multiplier",
            // Section 3 — Pillar Scores
            "Audio Quality Score", "Audio Quality Grade",
            "Voice Stability Score", "Voice Stability Grade",
            "Conversation Flow Score", "Conversation Flow Grade",
            "Conversation Balance Score", "Conversation Balance Grade",
            "Speech Activity Score", "Speech Activity Grade",
            "Collection Confidence Score", "Collection Confidence Grade",
            // Section 4 — Key Audio Statistics
            "Average SNR (dB)", "Average Speech Quality", "Average Pitch (Hz)",
            "Average Loudness (dB)", "Speech Percentage", "Silence Percentage",
            "Average Response Latency (sec)",
            // Section 5 — Conversation Statistics
            "Speaker Changes", "Turns", "Pauses", "Longest Pause (sec)",
            "Dropouts", "Clipping Events", "Interruptions", "Overlaps",
            // Section 6 — Investigation Summary
            "Primary Issue", "Secondary Issue", "Total Issues",
            "Critical Issues", "High Severity Issues", "Medium Severity Issues",
            // Section 7 — Recommendations
            "Business Impact", "Recommended Action", "Next Review Step",
            // Section 8 — Evidence Summary
            "Evidence Count", "Evidence Types",
            // Section 9 — References
            "Investigation Package", "JSON File", "Original Audio File",
        ];

        let csv = headers.map(csvEscape).join(",") + "\n";
        for (const row of rows) {
            csv += row.map(csvEscape).join(",") + "\n";
        }

        // Step 4: Trigger download
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "batch_analysis_report.csv";
        a.click();
        URL.revokeObjectURL(url);

    } catch (err) {
        console.error("Batch CSV export failed:", err);
        alert("Batch export failed. Check console for details.");
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
        btn.style.opacity = "1";
    }
}
