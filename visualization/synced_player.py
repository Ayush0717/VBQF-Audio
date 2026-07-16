from __future__ import annotations

from typing import Any
import json
import streamlit.components.v1 as components


def render_synced_player(
    audio_url: str, segments: list[dict[str, Any]], duration: float
) -> None:
    """
    Renders a custom HTML/JS component that plays the audio and smoothly animates
    a synced timeline cursor over the diarization segments without causing Streamlit to re-run.
    """
    # Create an HTML block with a timeline and an audio player
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: transparent;
            color: white;
            margin: 0;
            padding: 10px;
        }}
        .player-container {{
            background: #1e1e24;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .timeline-container {{
            position: relative;
            width: 100%;
            height: 60px;
            background: #2a2a35;
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
            border: 1px solid #3a3a45;
        }}
        .segment {{
            position: absolute;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            color: #fff;
            font-weight: bold;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
            border-right: 1px solid rgba(0,0,0,0.5);
            box-sizing: border-box;
            opacity: 0.7;
            transition: opacity 0.2s;
        }}
        .segment.active {{
            opacity: 1.0;
            box-shadow: inset 0 0 10px rgba(255,255,255,0.5);
        }}
        .cursor {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background-color: #ff1744;
            z-index: 10;
            pointer-events: none;
        }}
        .active-speaker-display {{
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 15px;
            min-height: 35px;
            color: #00e676;
        }}
        audio {{
            width: 100%;
            outline: none;
        }}
    </style>
    </head>
    <body>
        <div class="player-container">
            <div class="active-speaker-display" id="spk-display">Silence</div>
            <div class="timeline-container" id="timeline">
                <div class="cursor" id="cursor"></div>
            </div>
            <audio id="audio" controls src="{audio_url}"></audio>
        </div>

        <script>
            const segments = {json.dumps(segments)};
            const duration = {duration};
            const timeline = document.getElementById('timeline');
            const cursor = document.getElementById('cursor');
            const audio = document.getElementById('audio');
            const display = document.getElementById('spk-display');

            // Generate colors for speakers
            const colors = {{
                "Speaker 0": "#00bcd4",
                "Speaker 1": "#ff9800",
                "Speaker 2": "#e91e63",
                "Speaker 3": "#4caf50"
            }};

            // Render segments
            segments.forEach((seg, index) => {{
                const el = document.createElement('div');
                el.className = 'segment';
                el.id = 'seg-' + index;
                const leftPct = (seg.start / duration) * 100;
                const widthPct = (seg.duration / duration) * 100;
                
                el.style.left = leftPct + '%';
                el.style.width = widthPct + '%';
                el.style.backgroundColor = colors[seg.speaker] || '#9c27b0';
                el.innerText = seg.speaker;
                
                timeline.appendChild(el);
            }});

            // Animation loop for smooth cursor
            function updateSync() {{
                const currentTime = audio.currentTime;
                
                // Move cursor
                const cursorPct = (currentTime / duration) * 100;
                cursor.style.left = cursorPct + '%';

                // Find active speaker
                let activeSegIndex = -1;
                let currentSpeaker = "Silence";
                let currentColor = "#a0a0b0";

                for(let i=0; i<segments.length; i++) {{
                    if(currentTime >= segments[i].start && currentTime < segments[i].end) {{
                        activeSegIndex = i;
                        currentSpeaker = segments[i].speaker;
                        currentColor = colors[currentSpeaker] || '#9c27b0';
                        break;
                    }}
                }}

                display.innerText = currentSpeaker;
                display.style.color = currentColor;

                // Highlight active segment
                const allSegs = document.getElementsByClassName('segment');
                for(let i=0; i<allSegs.length; i++) {{
                    if(i === activeSegIndex) {{
                        allSegs[i].classList.add('active');
                    }} else {{
                        allSegs[i].classList.remove('active');
                    }}
                }}

                requestAnimationFrame(updateSync);
            }}

            // Start loop
            requestAnimationFrame(updateSync);

            // Click to seek
            timeline.addEventListener('click', (e) => {{
                const rect = timeline.getBoundingClientRect();
                const clickX = e.clientX - rect.left;
                const pct = clickX / rect.width;
                audio.currentTime = pct * duration;
                if(audio.paused) {{
                    audio.play();
                }}
            }});
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=220)
